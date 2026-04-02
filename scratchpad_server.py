import json
import logging
import os
import shutil
from pathlib import Path
from uuid import uuid4

import psutil
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

from scratchpad.docker_backend import DockerScratchpad
from scratchpad import versioning

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _kill_existing_instances() -> None:
    """Kill any stale instances of this server left over from a previous session."""
    current_pid = os.getpid()
    script = os.path.abspath(__file__)
    for proc in psutil.process_iter(["pid", "cmdline"]):
        if proc.pid == current_pid:
            continue
        try:
            cmdline = proc.info.get("cmdline") or []
            if any(script in arg for arg in cmdline):
                logger.info("Killing stale %s instance (PID %s).", os.path.basename(script), proc.pid)
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


_kill_existing_instances()

# Initialize the FastMCP server
mcp = FastMCP("Python Scratchpad")

# Set up paths relative to this file
BASE_DIR = Path(__file__).parent
SHARED_DIR = BASE_DIR / "shared"
RESULTS_DIR = BASE_DIR / "results"

# Initialize the Docker backend
scratchpad = DockerScratchpad(shared_dir=SHARED_DIR)

# Session ID groups all run_code calls until reset_session is called
_session_id: str = str(uuid4())
# Reset the executor namespace on the first run_code call after server start,
# so each server process begins with a clean slate matching the new session ID.
_first_run: bool = True


class RunCodeParams(BaseModel):
    code: str = Field(min_length=1, description="Python code to execute")
    timeout: int = Field(default=30, ge=1, le=120, description="Max execution time in seconds (1-120)")


# ==========================================
# RESOURCES (Data the LLM can read)
# ==========================================

#@mcp.resource("scratchpad://status")
@mcp.tool()
async def get_status() -> str:
    """Returns JSON status of the scratchpad: container state, session info, and saved figures."""
    container_running = await scratchpad._is_container_running()
    executor_alive = scratchpad._is_executor_alive()

    figures = []
    if SHARED_DIR.exists():
        for f in sorted(SHARED_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}:
                figures.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                })

    status = {
        "container_running": container_running,
        "executor_alive": executor_alive,
        "figures": figures,
    }
    return json.dumps(status, indent=2)


# ==========================================
# TOOLS (Actions the LLM can take)
# ==========================================

@mcp.tool()
async def run_code(code: str, timeout: int = 30) -> str:
    """
    Execute Python code in a persistent sandboxed session.

    Variables and functions defined in previous calls persist across calls.
    Pre-installed libraries: numpy (as np), scipy, sympy, matplotlib.pyplot (as plt), cv2.
    Plots are auto-saved to the shared directory. Use plt.plot(), plt.savefig(), etc.
    Images written with cv2.imwrite("/shared/name.png", img) are also detected.

    File Output:
        Write files to /shared/ inside the sandbox. Both
        plt.savefig('/shared/name.png') and cv2.imwrite('/shared/name.png', img) are
        supported. Writing to any other path (e.g. /home/claude/, /tmp/) raises
        FileNotFoundError with guidance. Saved figure paths are returned as host
        filesystem paths — use the Read tool on them directly to present figures.

    Session persistence:
        All names (variables, imports, functions) defined in prior run_code calls in the
        same conversation are available in later calls. An exception in one call does NOT
        clear names defined before the exception line. reset_session is the only way to
        clear state. State does NOT persist across conversations.

    Partial execution on error:
        If a call raises an exception mid-way, names bound before the failing line are
        retained and available in the next call.

    Note: If this tool is not yet loaded, call tool_search(query='scratchpad run code') first.

    Args:
        code: Python code to execute. Can reference variables from previous calls.
        timeout: Maximum execution time in seconds (default 30, max 120).
    """
    global _first_run, _session_id
    if _first_run:
        _first_run = False
        await scratchpad.reset_session()
        _session_id = str(uuid4())

    try:
        params = RunCodeParams(code=code, timeout=timeout)
    except ValidationError as e:
        return f"Invalid parameters:\n{e}"

    result = await scratchpad.execute(params.code, timeout=params.timeout)

    try:
        versioning.record_run(RESULTS_DIR, _session_id, params.code, result, SHARED_DIR)
    except Exception as e:
        logger.warning("Failed to record run: %s", e)

    parts = []
    if result.stdout:
        parts.append(f"stdout:\n{result.stdout}")
    if result.stderr:
        parts.append(f"stderr:\n{result.stderr}")
    if result.error:
        parts.append(f"error:\n{result.error}")
    if result.figures:
        host_paths = [
            str(SHARED_DIR / Path(f).name) for f in result.figures
        ]
        parts.append(f"figures saved: {', '.join(host_paths)}")

    if not parts:
        return "Code executed successfully (no output)."

    status = "Success" if result.success else "Error"
    return f"[{status}]\n" + "\n".join(parts)


@mcp.tool()
async def reset_session() -> str:
    """
    Reset the Python session, clearing all variables, functions, and imports.

    Use this to start fresh if the namespace is cluttered or in a bad state.
    """
    global _session_id
    await scratchpad.reset_session()
    _session_id = str(uuid4())
    return "Session reset. All variables and state have been cleared."


@mcp.tool()
async def list_figures() -> str:
    """
    List all figure and image files saved in the shared output directory.

    Returns host filesystem paths and sizes for images generated by matplotlib or OpenCV.
    Use as a fallback when the run_code result figures list is unavailable.
    Use the Read tool on the returned paths to present figures to the user.
    """
    if not SHARED_DIR.exists():
        return "No shared directory found. Run some code first."

    image_exts = {".png", ".jpg", ".jpeg", ".svg"}
    files = []
    for f in sorted(SHARED_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in image_exts:
            size_kb = f.stat().st_size / 1024
            files.append(f"{f}  ({size_kb:.1f} KB)")

    if not files:
        return "No figures saved yet."

    return "Saved figures (use Read tool on these paths to present them):\n" + "\n".join(files)


@mcp.tool()
async def copy_file_to_scratchpad(source_path: str, dest_filename: str | None = None) -> str:
    """
    Copy any file from the host filesystem into the scratchpad shared directory.

    Makes the file accessible inside the sandbox at /shared/<filename>, so it can
    be read by run_code (e.g. cv2.imread('/shared/capture.jpg'), np.load('/shared/data.npy')).

    Args:
        source_path: Absolute path to the file on the host filesystem.
        dest_filename: Filename to use inside the shared directory. Defaults to the
                       source file's basename.

    Returns:
        The sandbox path (/shared/<filename>) where the file is now accessible.
    """
    src = Path(source_path)
    if not src.exists():
        return f"Error: source file not found: {source_path}"
    if not src.is_file():
        return f"Error: source path is not a file: {source_path}"

    filename = dest_filename if dest_filename else src.name
    dest = SHARED_DIR / filename
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return f"Copied to /shared/{filename} ({dest.stat().st_size / 1024:.1f} KB). Access it in run_code at '/shared/{filename}'."


if __name__ == "__main__":
    mcp.run()
