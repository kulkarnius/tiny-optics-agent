import logging
import os
import json
from mcp.server.fastmcp import FastMCP, Image
from dotenv import load_dotenv

load_dotenv()

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

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

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

# ==========================================
# RESOURCES (Data the LLM can read)
# ==========================================

#@mcp.resource("hardware://inventory")
@mcp.tool()
def get_inventory() -> str:
    """Returns a JSON snapshot of all hardware devices and their current states."""
    inventory = {
        "motor": motor.get_state().model_dump(),
        "camera": camera.get_state().model_dump()
    }
    return json.dumps(inventory, indent=2)

#@mcp.resource("camera://latest")
@mcp.tool()
def get_latest_image() -> Image:
    """Returns the raw binary data of the most recently captured image."""
    image_path = camera.state.last_image_path

    if not image_path or not os.path.exists(image_path):
        raise FileNotFoundError("No image has been captured yet. Run 'capture_image' tool first.")

    # FastMCP's Image class handles reading the bytes and setting the correct mime type
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    return Image(data=image_bytes, format="jpeg")


# ==========================================
# TOOLS (Actions the LLM can take)
# ==========================================

@mcp.tool()
async def move_motor(target_position: float) -> str:
    """
    Moves the motor to an absolute target position.

    Args:
        target_position: The target position in mm (for PDXC) or degrees (0-360) for mock motor.
    """
    try:
        final_pos = await motor.move_to(target_position)
        return f"Success: Motor movement completed. Current position is {final_pos}."
    except Exception as e:
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
async def configure_camera(exposure_ms: int) -> str:
    """
    Adjusts the camera sensor settings.

    Args:
        exposure_ms: Exposure time in milliseconds.
                     Use 10-100 for well-lit/motion scenes, 100-500 for low light.
    """
    if not (1 <= exposure_ms <= 2000):
         return "Error: exposure_ms out of bounds. Must be 1-2000."

    camera.state.exposure = exposure_ms
    return f"Success: Camera exposure updated to {exposure_ms}ms."

@mcp.tool()
async def capture_image() -> str:
    """
    Triggers the camera to capture a new image and saves it to local disk.

    Returns:
        Instructions on how to view the newly captured image.
    """
    filepath = await camera.capture()
    return (f"Success: Image captured and saved to disk at {filepath}. "
            f"To view the image, read the resource: 'camera://latest'")


if __name__ == "__main__":
    # Runs the server using standard input/output (the default for MCP)
    mcp.run()
