"""
Host-side Docker backend for the Python scratchpad.

Manages container lifecycle and communicates with the persistent executor
process via stdin/stdout pipes over `docker exec -i`.
"""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    figures: list[str] = field(default_factory=list)
    success: bool = True


class DockerScratchpad:
    def __init__(
        self,
        image_name: str = "scratchpad-sandbox",
        container_name: str = "scratchpad-session",
        shared_dir: Path | None = None,
        timeout: int = 30,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
    ):
        self.image_name = image_name
        self.container_name = container_name
        self.shared_dir = shared_dir or (BASE_DIR / "shared")
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self._process: asyncio.subprocess.Process | None = None

    async def build_image(self) -> None:
        """Build the Docker image from Dockerfile.scratchpad."""
        logger.info("Building Docker image '%s'...", self.image_name)
        proc = await asyncio.create_subprocess_exec(
            "docker", "build",
            "-f", str(BASE_DIR / "Dockerfile.scratchpad"),
            "-t", self.image_name,
            str(BASE_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Docker build failed (exit {proc.returncode}):\n{stderr.decode()}"
            )
        logger.info("Docker image '%s' built successfully.", self.image_name)

    async def _is_container_running(self) -> bool:
        """Check if the named container is currently running."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f", "{{.State.Running}}", self.container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return proc.returncode == 0 and stdout.decode().strip() == "true"

    async def _start_container(self) -> None:
        """Start the Docker container with security constraints."""
        self.shared_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting container '%s'...", self.container_name)
        proc = await asyncio.create_subprocess_exec(
            "docker", "run", "-d",
            "--name", self.container_name,
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:size=64m",
            "--memory", self.memory_limit,
            "--cpus", str(self.cpu_limit),
            "--mount", f"type=bind,source={self.shared_dir.resolve()},target=/shared",
            self.image_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to start container (exit {proc.returncode}):\n{stderr.decode()}"
            )
        logger.info("Container '%s' started.", self.container_name)

    async def _kill_container_executors(self) -> None:
        """Kill any lingering executor.py processes inside the container.

        Killing the host-side docker exec process does NOT immediately kill
        the container-side Python process — it stays alive (blocked on imports
        or I/O) until it tries to read EOF on stdin.  After many reset_session
        calls these orphaned processes accumulate and starve the real executor.
        """
        kill_script = (
            "import os, signal\n"
            "for pid in os.listdir('/proc'):\n"
            "    if not pid.isdigit(): continue\n"
            "    try:\n"
            "        with open(f'/proc/{pid}/cmdline', 'rb') as f: c = f.read()\n"
            "        if b'executor.py' in c and int(pid) != os.getpid():\n"
            "            os.kill(int(pid), signal.SIGKILL)\n"
            "    except OSError: pass\n"
        )
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", self.container_name,
            "python", "-c", kill_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    async def _start_executor(self) -> None:
        """Start the persistent executor process via docker exec."""
        logger.info("Starting executor process...")
        self._process = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", self.container_name,
            "python", "/app/executor.py",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for the executor to signal readiness ("READY\n") instead of a
        # fixed sleep.  This handles slow container starts (e.g. font-cache
        # rebuild on a read-only filesystem) without an arbitrary timeout.
        try:
            ready_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=60,
            )
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()
            raise RuntimeError("Executor did not become ready within 60 s")

        if not ready_line or ready_line.strip() != b"READY":
            self._process.kill()
            await self._process.wait()
            raise RuntimeError(
                f"Unexpected executor startup message: {ready_line!r}"
            )

        if self._process.returncode is not None:
            stderr = await self._process.stderr.read()
            raise RuntimeError(
                f"Executor process exited immediately:\n{stderr.decode()}"
            )
        logger.info("Executor process started (PID %s).", self._process.pid)

    def _is_executor_alive(self) -> bool:
        """Check if the executor subprocess is still running."""
        return self._process is not None and self._process.returncode is None

    async def ensure_running(self) -> None:
        """Ensure both container and executor are running."""
        if not await self._is_container_running():
            # Remove stale container if it exists (must await communicate so
            # the rm completes before we try to start a new container)
            rm_proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", self.container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await rm_proc.communicate()
            await self._start_container()

        if not self._is_executor_alive():
            await self._start_executor()

    async def execute(self, code: str, timeout: int | None = None) -> ExecutionResult:
        """Execute Python code in the persistent session."""
        await self.ensure_running()

        timeout = timeout or self.timeout
        request = json.dumps({"code": code, "timeout": timeout}) + "\n"

        try:
            self._process.stdin.write(request.encode())
            await self._process.stdin.drain()

            raw_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=timeout + 5,  # host-side grace period
            )
        except asyncio.TimeoutError:
            logger.warning("Host-side timeout exceeded, restarting executor.")
            await self._restart_executor()
            return ExecutionResult(
                error="Execution timed out (host-side timeout exceeded)",
                success=False,
            )
        except (BrokenPipeError, ConnectionResetError):
            logger.warning("Executor process died, restarting.")
            await self._restart_executor()
            return ExecutionResult(
                error="Executor process crashed, session was restarted",
                success=False,
            )

        if not raw_line:
            logger.warning("Empty response from executor, restarting.")
            await self._restart_executor()
            return ExecutionResult(
                error="Executor returned empty response, session was restarted",
                success=False,
            )

        try:
            data = json.loads(raw_line.decode())
            return ExecutionResult(
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                error=data.get("error"),
                figures=data.get("figures", []),
                success=data.get("success", True),
            )
        except json.JSONDecodeError as e:
            return ExecutionResult(
                error=f"Failed to parse executor response: {e}\nRaw: {raw_line.decode()[:500]}",
                success=False,
            )

    async def _restart_executor(self) -> None:
        """Kill and restart the executor process."""
        if self._process and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()
        self._process = None
        await self._kill_container_executors()
        await self._start_executor()

    async def reset_session(self) -> None:
        """Reset the Python session by restarting the executor process."""
        logger.info("Resetting session...")
        if self._is_executor_alive():
            self._process.kill()
            await self._process.wait()
        self._process = None

        # Kill any lingering executor processes left inside the container from
        # previous reset_session / _restart_executor calls.  Killing the
        # host-side docker exec process does NOT immediately kill the
        # container-side Python process, so these accumulate over time.
        await self._kill_container_executors()

        # Clean up generated figures
        if self.shared_dir.exists():
            for f in self.shared_dir.iterdir():
                if f.is_file():
                    f.unlink()

        await self._start_executor()
        logger.info("Session reset complete.")

    async def stop(self) -> None:
        """Stop the executor and container."""
        logger.info("Stopping scratchpad...")

        if self._process and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()
        self._process = None

        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", self.container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        logger.info("Scratchpad stopped.")
