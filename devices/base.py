from pydantic import BaseModel, ConfigDict
from enum import Enum
from abc import ABC

class Status(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    ERROR = "ERROR"

class DeviceState(BaseModel):
    """Base state that all devices share."""
    model_config = ConfigDict(validate_assignment=True)
    status: Status = Status.IDLE

class BaseDevice(ABC):
    """Abstract base class for all hardware devices."""
    def __init__(self):
        self.state = DeviceState()

    def get_state(self) -> DeviceState:
        """Returns the current Pydantic state model."""
        return self.state