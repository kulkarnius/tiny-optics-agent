import asyncio
import atexit
import logging
import os
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import psutil
from mcp.server.fastmcp import FastMCP, Image
from pydantic import ValidationError
from dotenv import load_dotenv

load_dotenv()

# Configure logging early so the kill message is visible
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# shared/ is the volume bind-mounted into the scratchpad Docker container at
# /shared/.  All file outputs (camera captures and scratchpad figures) live
# under this tree so both the host process and the sandbox can reach them
# without any copy step.
SHARED_DIR = Path(__file__).resolve().parent / "shared"
SHARED_DATA_DIR = SHARED_DIR / "data"
SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
logger.info("Shared directory: %s", SHARED_DIR)
logger.info("Capture output directory: %s", SHARED_DATA_DIR)


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

# Import our hardware classes from the devices folder
from devices.camera import MockCamera
from devices.motor import MockMotor

try:
    from devices.pdxc_motor import PDXCMotor
    _PDXCMotor = PDXCMotor
except Exception:
    _PDXCMotor = None

try:
    from devices.imaging_source_camera import ImagingSourceCamera
    _ImagingSourceCamera = ImagingSourceCamera
except Exception:
    _ImagingSourceCamera = None

from devices.laser import Laser, LaserError

# Initialize the FastMCP server
# This automatically handles stdio communication and routing
mcp = FastMCP("Hardware Controller")

# Instantiate our "live" hardware singletons
# Set MOTOR_TYPE in .env to "pdxc", "mock", or leave unset for auto-detection.
MOTOR_TYPE = os.environ.get("MOTOR_TYPE", "auto").lower()
CAMERA_TYPE = os.environ.get("CAMERA_TYPE", "auto").lower()
logger.info("Initializing hardware devices (MOTOR_TYPE=%s, CAMERA_TYPE=%s)...", MOTOR_TYPE, CAMERA_TYPE)

motor = None
if MOTOR_TYPE == "pdxc":
    if _PDXCMotor is None:
        raise ImportError("MOTOR_TYPE=pdxc but PDXC SDK is unavailable.")
    motor = _PDXCMotor()
    logger.info("PDXC motor initialized.")
elif MOTOR_TYPE == "mock":
    motor = MockMotor()
    logger.info("Mock motor initialized.")
else:  # auto
    if _PDXCMotor is not None:
        try:
            motor = _PDXCMotor()
            logger.info("PDXC motor initialized.")
        except Exception as e:
            logger.warning("PDXC motor unavailable (%s), falling back to MockMotor.", e)
    if motor is None:
        motor = MockMotor()
        logger.info("Mock motor initialized.")

camera = None
if CAMERA_TYPE == "imaging_source":
    if _ImagingSourceCamera is None:
        raise ImportError("CAMERA_TYPE=imaging_source but harvesters SDK is unavailable.")
    camera = _ImagingSourceCamera(
        serial_number=os.environ["CAMERA_SERIAL_NUMBER"],
        cti_path=os.environ["GENTL_CTI_PATH"],
    )
    logger.info("ImagingSource camera initialized.")
elif CAMERA_TYPE == "mock":
    camera = MockCamera()
    logger.info("Mock camera initialized.")
else:  # auto
    if _ImagingSourceCamera is not None:
        try:
            camera = _ImagingSourceCamera(
                serial_number=os.environ["CAMERA_SERIAL_NUMBER"],
                cti_path=os.environ["GENTL_CTI_PATH"],
            )
            logger.info("ImagingSource camera initialized.")
        except Exception as e:
            logger.warning("ImagingSource camera unavailable (%s), falling back to MockCamera.", e)
    if camera is None:
        camera = MockCamera()
        logger.info("Mock camera initialized.")

laser = Laser()
logger.info("Laser controller initialized.")


# ==========================================
# RESOURCES (Data the LLM can read)
# ==========================================

#@mcp.resource("hardware://inventory")
@mcp.tool()
def get_inventory() -> str:
    """Returns a JSON snapshot of all hardware devices and their current states."""
    try:
        laser_on = laser.get_state()
        laser_info = {"on": laser_on}
    except LaserError as e:
        logger.warning("Could not read laser state for inventory: %s", e)
        laser_info = {"on": None, "error": str(e)}

    inventory = {
        "motor": {
            **motor.get_state().model_dump(),
            "position_min": motor.POSITION_MIN,
            "position_max": motor.POSITION_MAX,
            "position_units": motor.POSITION_UNITS,
        },
        "camera": {
            **camera.get_state().model_dump(),
            "exposure_min": camera.EXPOSURE_MIN,
            "exposure_max": camera.EXPOSURE_MAX,
            "exposure_units": camera.EXPOSURE_UNITS,
            "gain_min": camera.GAIN_MIN,
            "gain_max": camera.GAIN_MAX,
            "gain_units": camera.GAIN_UNITS,
        },
        "laser": laser_info,
    }
    return json.dumps(inventory, indent=2)

@mcp.tool()
def display_image(filename: str) -> Image:
    """
    Loads an image from the shared directory and returns it for inline rendering.

    Claude renders the returned image directly inline in the conversation —
    no separate viewer, no path translation, and no present_files call needed.

    Use this tool to display:
    - Camera captures: pass the filename reported by capture_image
      (e.g. "data/capture_20260403T150432_123.jpg")
    - Scratchpad figures: pass the basename of any file saved to /shared/
      inside scratchpad code (e.g. "my_plot.png" for plt.savefig('/shared/my_plot.png'))

    Args:
        filename: Path relative to the shared directory root.
    """
    image_path = (SHARED_DIR / filename).resolve()
    # Prevent path traversal outside the shared directory
    if not str(image_path).startswith(str(SHARED_DIR.resolve())):
        raise ValueError(f"filename must be relative to the shared directory: {filename!r}")
    if not image_path.exists():
        raise FileNotFoundError(
            f"No file found at shared/{filename}. "
            "For camera captures, call capture_image first. "
            "For scratchpad figures, ensure the file was saved to /shared/<filename>."
        )
    fmt = "png" if image_path.suffix.lower() == ".png" else "jpeg"
    return Image(data=image_path.read_bytes(), format=fmt)


@mcp.tool()
def get_latest_image_path() -> str:
    """
    Returns the filename of the most recently captured image, relative to the
    shared directory.

    Use this when you need the path for programmatic access in scratchpad code
    (e.g. cv2.imread('/shared/' + filename)) rather than displaying the image.
    To display it inline, pass the returned filename to display_image instead.
    """
    image_path = camera.state.last_image_path
    if not image_path or not os.path.exists(image_path):
        raise FileNotFoundError(
            "No image has been captured yet. Run 'capture_image' first."
        )
    rel = Path(image_path).relative_to(SHARED_DIR)
    return str(rel)


# ==========================================
# TOOLS (Actions the LLM can take)
# ==========================================

@mcp.tool()
async def move_motor(target_position: float) -> str:
    """
    Moves the motor to an absolute target position.

    Args:
        target_position: Target position. Call get_inventory to see valid units and range.
    """
    MoveParams = motor.make_move_params()
    try:
        params = MoveParams(target_position=target_position)
    except ValidationError as e:
        return f"Invalid parameters:\n{e}"

    try:
        final_pos = await motor.move_to(params.target_position)
        return f"Success: Motor movement completed. Current position is {final_pos} {motor.POSITION_UNITS}."
    except (ValidationError, Exception) as e:
        return f"Error: {e}"


@mcp.tool()
async def home_motor() -> str:
    """Homes the motor. Required before closed-loop moves on real hardware."""
    if hasattr(motor, "home"):
        await motor.home()
        return f"Success: Motor homed. State: {motor.get_state().model_dump()}"
    return "Home not supported on this motor type."


@mcp.tool()
async def refresh_motor() -> str:
    """Reads the current hardware position and syncs the internal state."""
    if hasattr(motor, "refresh"):
        await motor.refresh()
    return json.dumps(motor.get_state().model_dump())

@mcp.tool()
async def configure_camera(exposure_ms: int | None = None, gain: float | None = None) -> str:
    """
    Adjusts the camera sensor settings. At least one parameter must be provided.

    Args:
        exposure_ms: Exposure time in milliseconds. Omit to leave unchanged.
                     Use 10-100 for well-lit/motion scenes, 100-500 for low light.
        gain:        Sensor gain in dB. Omit to leave unchanged.
                     Higher values brighten dark images but increase noise.
    """
    if exposure_ms is None and gain is None:
        return "Error: at least one of exposure_ms or gain must be provided."

    messages = []

    if exposure_ms is not None:
        ConfigureParams = camera.make_configure_params()
        try:
            params = ConfigureParams(exposure_ms=exposure_ms)
        except ValidationError as e:
            return f"Invalid exposure_ms:\n{e}"
        try:
            camera.state.exposure = params.exposure_ms
        except ValidationError as e:
            return f"Error setting exposure: {e}"
        messages.append(f"exposure updated to {params.exposure_ms} {camera.EXPOSURE_UNITS}")

    if gain is not None:
        GainParams = camera.make_gain_params()
        try:
            params = GainParams(gain=gain)
        except ValidationError as e:
            return f"Invalid gain:\n{e}"
        try:
            camera.state.gain = params.gain
        except ValidationError as e:
            return f"Error setting gain: {e}"
        messages.append(f"gain updated to {params.gain} {camera.GAIN_UNITS}")

    return f"Success: Camera {', '.join(messages)}."

@mcp.tool()
async def capture_image() -> str:
    """
    Triggers the camera to capture a new image and saves it to local disk.

    Returns:
        Instructions on how to view the newly captured image.
    """
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")[:-3]
        filename = f"capture_{timestamp}.jpg"
        dest_path = str(SHARED_DATA_DIR / filename)
        filepath = await camera.capture(dest_path=dest_path)
        return (
            f"Success: Image captured and saved to {filepath}. "
            f"To display it inline, call display_image with filename=\"data/{filename}\". "
            f"The scratchpad can access it at /shared/data/{filename}."
        )
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def set_laser(on: bool) -> str:
    """
    Turn the laser on or off via the relay controller.

    Args:
        on: True to turn the laser on, False to turn it off.
    """
    logger.info("MCP set_laser called: on=%s", on)
    try:
        await asyncio.to_thread(laser.set_state, on)
    except LaserError as e:
        logger.error("MCP set_laser failed: %s", e)
        return f"Error: {e}"
    state = "ON" if on else "OFF"
    logger.info("MCP set_laser succeeded: laser is %s", state)
    return f"Laser turned {state}."


def _close_devices() -> None:
    """Release all hardware resources on exit."""
    for name, device in (("motor", motor), ("camera", camera)):
        if device is not None and hasattr(device, "close"):
            try:
                device.close()
                logger.info("%s closed.", name)
            except Exception as e:
                logger.warning("Error closing %s: %s", name, e)


atexit.register(_close_devices)


def _signal_handler(sig, frame) -> None:
    logger.info("Received signal %s, shutting down...", sig)
    sys.exit(0)  # triggers atexit


for _sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(_sig, _signal_handler)

# SIGBREAK is Windows-only (Ctrl+Break)
if hasattr(signal, "SIGBREAK"):
    signal.signal(signal.SIGBREAK, _signal_handler)


if __name__ == "__main__":
    # Runs the server using standard input/output (the default for MCP)
    mcp.run()
