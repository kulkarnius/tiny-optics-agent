import logging
import os
import json
from mcp.server.fastmcp import FastMCP, Image

# Import our hardware classes from the devices folder
from devices.motor import MockMotor
from devices.camera import MockCamera

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Initialize the FastMCP server
# This automatically handles stdio communication and routing
mcp = FastMCP("Hardware Controller")

# Instantiate our "live" hardware singletons
logger.info("Initializing hardware devices...")
try:
    motor = MockMotor()
    logger.info("Motor initialized.")
except Exception as e:
    logger.error("Failed to initialize motor: %s", e)
    raise

try:
    camera = MockCamera()
    logger.info("Camera initialized.")
except Exception as e:
    logger.error("Failed to initialize camera: %s", e)
    raise

# ==========================================
# RESOURCES (Data the LLM can read)
# ==========================================

@mcp.resource("hardware://inventory")
def get_inventory() -> str:
    """Returns a JSON snapshot of all hardware devices and their current states."""
    inventory = {
        "motor": motor.get_state().model_dump(),
        "camera": camera.get_state().model_dump()
    }
    return json.dumps(inventory, indent=2)

@mcp.resource("camera://latest")
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
async def move_motor(target_position_deg: float) -> str:
    """
    Moves the motor to an absolute target position.

    Args:
        target_position_deg: The target angle in degrees (0.0 to 360.0).
    """
    # FastMCP automatically surfaces the arg description to Gemini
    if not (0.0 <= target_position_deg <= 360.0):
        return "Error: target_position_deg out of bounds. Must be 0-360."

    # Async execution: The motor moves while the server stays responsive
    final_pos = await motor.move_to(target_position_deg)
    return f"Success: Motor movement completed. Current position is {final_pos} deg."

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
