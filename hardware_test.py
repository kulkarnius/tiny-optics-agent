import asyncio
import os
import tempfile
from devices.motor import MockMotor
from devices.camera import MockCamera

async def main():
    print("--- Initializing Hardware ---")
    motor = MockMotor()
    camera = MockCamera()

    print(f"Initial Motor State:  {motor.get_state()}")
    print(f"Initial Camera State: {camera.get_state()}\n")

    print("--- Executing Motor Move ---")
    try:
        # This should succeed
        await motor.move_to(90.5)
        print(f"Motor State after valid move: {motor.get_state()}")
    except Exception as e:
        print(f"Motor Error: {e}")

    print("\n--- Testing Motor Validation (out-of-range position) ---")
    try:
        await motor.move_to(400)  # 400 degrees exceeds the 0-360 Field constraint
        print("ERROR: expected ValidationError but got none")
    except Exception as e:
        print(f"Caught expected validation error: {type(e).__name__}")

    print("\n--- Executing Camera Capture (default path) ---")
    filepath = await camera.capture()
    print(f"Camera State after capture: {camera.get_state()}")
    print(f"Image saved successfully to: {filepath}")
    assert os.path.exists(filepath), f"File not found: {filepath}"

    print("\n--- Executing Camera Capture (custom dest_path) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "custom_capture.jpg")
        filepath2 = await camera.capture(dest_path=dest)
        assert filepath2 == dest, f"Expected {dest}, got {filepath2}"
        assert os.path.exists(filepath2), f"File not found: {filepath2}"
        assert camera.state.last_image_path == dest
        print(f"dest_path capture succeeded: {filepath2}")

    print("\nAll tests passed!")

if __name__ == "__main__":
    asyncio.run(main())