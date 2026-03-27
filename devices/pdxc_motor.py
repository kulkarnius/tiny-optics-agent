import asyncio
import time
import logging
from pydantic import Field
from .base import BaseDevice, DeviceState, Status

try:
    from .vendor.PDXC_COMMAND_LIB import pdxc
except ImportError:
    pdxc = None

logger = logging.getLogger(__name__)


class PDXCMotorState(DeviceState):
    position: float = 0.0
    speed: float = 1.0
    is_homed: bool = False


class PDXCMotor(BaseDevice):
    """Thorlabs PDXC piezo motor controller — single device, closed-loop mode."""

    HOMING_TIMEOUT_S = 60
    HOMING_POLL_INTERVAL_S = 0.5

    def __init__(self, serial_number: str | None = None):
        super().__init__()
        self.state = PDXCMotorState()

        if pdxc is None:
            raise ImportError(
                "Thorlabs PDXC SDK not available. "
                "Ensure PDXC_COMMAND_LIB.py and its DLL are installed."
            )

        self._pdxc = pdxc()

        # Auto-detect first device if no serial number given
        if serial_number is None:
            devices = pdxc.ListDevices()
            if not devices:
                raise RuntimeError("No PDXC devices found.")
            serial_number = devices[0][0]
            logger.info("Auto-detected PDXC device: %s", serial_number)

        self._serial_number = serial_number
        hdl = self._pdxc.Open(serial_number, 115200, 3)
        if hdl < 0:
            raise ConnectionError(
                f"Failed to open PDXC device {serial_number} (handle={hdl})."
            )
        logger.info("Opened PDXC device %s (handle=%d)", serial_number, hdl)

        # Single device mode, closed-loop
        self._pdxc.SetDaisyChain(0)
        self._pdxc.SetLoop(0, 0)  # 0 = closed loop

    def _refresh_sync(self) -> None:
        """Read current position and error status from hardware."""
        pos = [0]
        ret = self._pdxc.GetCurrentPosition(0, pos)
        if ret == 0:
            self.state.position = pos[0]

        err = [0]
        ret = self._pdxc.GetErrorMessage(0, err)
        if ret == 0 and err[0] != 0:
            logger.error("PDXC error code: %s", err[0])
            self.state.status = Status.ERROR

    async def refresh(self) -> None:
        """Async wrapper: sync state.position with the real hardware position."""
        await asyncio.to_thread(self._refresh_sync)

    def _home_sync(self) -> None:
        """Synchronous homing with polling."""
        self._pdxc.SetPositionCalibration(0, 1)

        deadline = time.monotonic() + self.HOMING_TIMEOUT_S
        while time.monotonic() < deadline:
            homed = [0]
            self._pdxc.GetCalibrationIsCompleted(0, homed)
            if "Yes" in str(homed[0]):
                return
            time.sleep(self.HOMING_POLL_INTERVAL_S)

        raise TimeoutError("PDXC homing did not complete within timeout.")

    async def home(self) -> None:
        """Home the motor (required before closed-loop moves)."""
        self.state.status = Status.BUSY
        try:
            await asyncio.to_thread(self._home_sync)
            self.state.is_homed = True
            self._refresh_sync()
            self.state.status = Status.IDLE
        except Exception:
            self.state.status = Status.ERROR
            raise

    def _move_sync(self, target_position: float) -> None:
        """Synchronous absolute move."""
        ret = self._pdxc.SetTargetPosition(0, target_position)
        if ret < 0:
            raise RuntimeError(f"SetTargetPosition failed (ret={ret}).")

    async def move_to(self, target_position: float) -> float:
        """Move motor to an absolute position (mm)."""
        self.state.status = Status.BUSY
        try:
            await asyncio.to_thread(self._move_sync, target_position)
            self._refresh_sync()
            return self.state.position
        finally:
            if self.state.status != Status.ERROR:
                self.state.status = Status.IDLE

    async def set_speed(self, speed: float) -> None:
        """Set the closed-loop target speed (mm/s or deg/s depending on stage)."""
        ret = await asyncio.to_thread(self._pdxc.SetTargetSpeed, 0, speed)
        if ret == 0:
            self.state.speed = speed

    def close(self) -> None:
        """Release the PDXC device."""
        self._pdxc.Close()
        logger.info("Closed PDXC device %s", self._serial_number)
