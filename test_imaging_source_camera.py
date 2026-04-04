import asyncio
import os
from dotenv import load_dotenv
from devices.imaging_source_camera import ImagingSourceCamera

load_dotenv()

SERIAL_NUMBER = os.environ["CAMERA_SERIAL_NUMBER"]
CTI_PATH = os.environ["GENTL_CTI_PATH"]


async def main():
    print("--- Initializing Imaging Source Camera ---")
    camera = ImagingSourceCamera(serial_number=SERIAL_NUMBER, cti_path=CTI_PATH)
    print(f"Initial Camera State: {camera.get_state()}\n")

    print("--- Configuring Exposure ---")
    camera.state.exposure = 200
    print(f"Camera State after exposure update: {camera.get_state()}\n")

    print("--- Configuring Gain ---")
    camera.state.gain = 12.0
    print(f"Camera State after gain update: {camera.get_state()}\n")

    print("--- Capturing Image ---")
    filepath = await camera.capture()
    print(f"Camera State after capture: {camera.get_state()}")
    print(f"Image saved to: {filepath}\n")

    camera.close()
    print("--- Camera released ---")


if __name__ == "__main__":
    asyncio.run(main())
