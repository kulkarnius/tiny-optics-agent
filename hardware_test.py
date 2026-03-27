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
        
        # Uncommenting the next line would cause a Pydantic ValidationError
        # await motor.move_to(400) 
        
    except Exception as e:
        print(f"Motor Error: {e}")

    print("\n--- Executing Camera Capture ---")
    filepath = await camera.capture()
    print(f"Camera State after capture: {camera.get_state()}")
    print(f"Image saved successfully to: {filepath}\n")

if __name__ == "__main__":
    asyncio.run(main())