import asyncio
from devices.pdxc_motor import PDXCMotor


async def main():
    print("--- Initializing PDXC Motor ---")
    motor = PDXCMotor()
    print(f"Initial state: {motor.get_state()}\n")

    print("--- Homing motor ---")
    await motor.home()
    print(f"State after homing: {motor.get_state()}\n")

    print("--- Setting speed to 5 mm/s ---")
    await motor.set_speed(5.0)
    print(f"State after speed set: {motor.get_state()}\n")

    print("--- Moving to 1.0 mm ---")
    pos = await motor.move_to(1.0)
    print(f"move_to returned: {pos}")
    print(f"State after move: {motor.get_state()}\n")

    print("--- Refreshing position ---")
    await motor.refresh()
    print(f"State after refresh: {motor.get_state()}\n")

    print("--- Moving to -1.0 mm ---")
    pos = await motor.move_to(-1.0)
    print(f"move_to returned: {pos}")
    print(f"State after move: {motor.get_state()}\n")

    print("--- Refreshing position ---")
    await motor.refresh()
    print(f"State after refresh: {motor.get_state()}\n")

    motor.close()
    print("--- Motor closed ---")


if __name__ == "__main__":
    asyncio.run(main())
