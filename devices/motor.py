from pydantic import Field
from typing import ClassVar
from .base import BaseMotor, DeviceState, Status

class MotorState(DeviceState):
    # Enforce constraints: position must be between 0 and 360
    position: float = Field(default=0.0, ge=0.0, le=360.0)
    speed: float = Field(default=10.0, ge=1.0, le=100.0)

class MockMotor(BaseMotor):
    POSITION_MIN: ClassVar[float] = 0.0
    POSITION_MAX: ClassVar[float] = 360.0
    POSITION_UNITS: ClassVar[str] = "degrees"
    def __init__(self):
        super().__init__()
        self.state = MotorState()

    async def move_to(self, target_position: float) -> float:
        """Mocks an instant motor movement."""
        self.state.status = Status.BUSY
        
        # In a real motor, we would await a serial command here.
        # For the mock, it's instant.
        self.state.position = target_position
        
        self.state.status = Status.IDLE
        return self.state.position