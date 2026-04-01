from pydantic import BaseModel, ConfigDict, create_model, Field as PydanticField
from enum import Enum
from abc import ABC
from typing import ClassVar, Optional, Type

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


class BaseMotor(BaseDevice, ABC):
    """Intermediate base class for all motor devices.

    Subclasses declare their physical travel limits as class-level attributes.
    The MCP server calls make_move_params() to get a Pydantic validator with
    the correct constraints before issuing any hardware command.
    """
    POSITION_MIN: ClassVar[Optional[float]] = None
    POSITION_MAX: ClassVar[Optional[float]] = None
    POSITION_UNITS: ClassVar[str] = "units"

    @classmethod
    def make_move_params(cls) -> Type[BaseModel]:
        """Return a Pydantic model whose target_position field carries the
        ge/le constraints derived from this class's POSITION_MIN/MAX."""
        lo, hi = cls.POSITION_MIN, cls.POSITION_MAX
        if lo is not None and hi is not None:
            desc = f"Target position in {cls.POSITION_UNITS} (hardware range: {lo} to {hi})"
        elif lo is not None:
            desc = f"Target position in {cls.POSITION_UNITS} (minimum: {lo})"
        elif hi is not None:
            desc = f"Target position in {cls.POSITION_UNITS} (maximum: {hi})"
        else:
            desc = f"Target position in {cls.POSITION_UNITS}"
        field_kwargs: dict = {"description": desc}
        if lo is not None:
            field_kwargs["ge"] = lo
        if hi is not None:
            field_kwargs["le"] = hi
        return create_model(
            f"{cls.__name__}MoveParams",
            target_position=(float, PydanticField(**field_kwargs)),
        )


class BaseCamera(BaseDevice, ABC):
    """Intermediate base class for all camera devices.

    Subclasses declare their exposure limits as class-level attributes.
    The MCP server calls make_configure_params() to get a Pydantic validator
    with the correct constraints.
    """
    EXPOSURE_MIN: ClassVar[int] = 1
    EXPOSURE_MAX: ClassVar[int] = 2000
    EXPOSURE_UNITS: ClassVar[str] = "ms"

    @classmethod
    def make_configure_params(cls) -> Type[BaseModel]:
        """Return a Pydantic model whose exposure_ms field carries the
        ge/le constraints derived from this class's EXPOSURE_MIN/MAX."""
        desc = f"Exposure time in {cls.EXPOSURE_UNITS} ({cls.EXPOSURE_MIN}-{cls.EXPOSURE_MAX})"
        return create_model(
            f"{cls.__name__}ConfigureParams",
            exposure_ms=(int, PydanticField(ge=cls.EXPOSURE_MIN, le=cls.EXPOSURE_MAX, description=desc)),
        )