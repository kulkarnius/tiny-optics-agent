import json
import logging
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

from scratchpad.docker_backend import DockerScratchpad
from scratchpad import versioning

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

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


class RunCodeParams(BaseModel):
    code: str = Field(min_length=1, description="Python code to execute")
    timeout: int = Field(default=30, ge=1, le=120, description="Max execution time in seconds (1-120)")


# ==========================================
# RESOURCES (Data the LLM can read)
# ==========================================

@mcp.resource("scratchpad://status")
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
        Write files to /shared/ for use with present_files. Both
        plt.savefig('/shared/name.png') and cv2.imwrite('/shared/name.png', img) are
        supported. The /shared/ directory inside the sandbox maps to the same path seen
        by present_files. Writing to any other path (e.g. /home/claude/, /tmp/) raises
        FileNotFoundError with guidance. Saved figure paths are included in the tool
        result so no list_figures call is needed.

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
        parts.append(f"figures saved: {', '.join(result.figures)}")

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

    Returns full /shared/ paths and sizes for images generated by matplotlib or OpenCV.
    Use as a fallback when the run_code result figures list is unavailable.
    """
    if not SHARED_DIR.exists():
        return "No shared directory found. Run some code first."

    image_exts = {".png", ".jpg", ".jpeg", ".svg"}
    files = []
    for f in sorted(SHARED_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in image_exts:
            size_kb = f.stat().st_size / 1024
            files.append(f"/shared/{f.name}  ({size_kb:.1f} KB)")

    if not files:
        return "No figures saved yet."

    return "Saved figures:\n" + "\n".join(files)


if __name__ == "__main__":
    mcp.run()
