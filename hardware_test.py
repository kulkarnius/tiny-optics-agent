import asyncio
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

    print("\n--- Executing Camera Capture ---")
    filepath = await camera.capture()
    print(f"Camera State after capture: {camera.get_state()}")
    print(f"Image saved successfully to: {filepath}\n")

if __name__ == "__main__":
    asyncio.run(main())