import asyncio
import logging
import os
import cv2
import numpy as np
from pathlib import Path
from pydantic import Field
from typing import Optional
from harvesters.core import Harvester
from .base import BaseCamera, DeviceState, Status

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = str(Path(__file__).parent.parent / "data")


class ImagingSourceCameraState(DeviceState):
    exposure: int = Field(default=100, ge=1, le=2000)
    last_image_path: Optional[str] = None
    um_per_pixel: Optional[float] = Field(
        default=None,
        description="Microns per pixel at the sample plane. None if uncalibrated.",
    )


class ImagingSourceCamera(BaseCamera):
    def __init__(self, serial_number: str, cti_path: str, data_dir: str = _DEFAULT_DATA_DIR):
        """
        Args:
            serial_number: The serial number of the target Imaging Source GigE camera.
            cti_path:      Absolute path to the GenTL producer (.cti file) supplied
                           with the camera (e.g. the IDS/TIS GenTL producer).
            data_dir:      Directory where captured images are saved.
        """
        super().__init__()
        um_per_pixel_env = os.environ.get("CAMERA_UM_PER_PIXEL")
        um_per_pixel = float(um_per_pixel_env) if um_per_pixel_env is not None else None
        self.state = ImagingSourceCameraState(um_per_pixel=um_per_pixel)
        self.serial_number = serial_number
        self.cti_path = cti_path
        self.data_dir = data_dir
        self._capture_count = 0

        os.makedirs(self.data_dir, exist_ok=True)

        self._harvester = Harvester()
        self._harvester.add_file(cti_path)
        self._harvester.update()

        self._ia = self._harvester.create(search_key={"serial_number": serial_number})

    def _do_capture(self, dest_path: str | None = None) -> str:
        """Synchronous capture executed in a thread pool to avoid blocking the event loop.

        Args:
            dest_path: If provided, save the image to this path instead of
                       the default data directory.
        """
        try:
            # Set exposure (GenICam ExposureTime node expects microseconds).
            # ExposureAuto must be Off or the ExposureTime node is read-only.
            node_map = self._ia.remote_device.node_map
            logger.info("Setting ExposureAuto=Off, ExposureTime=%s µs", self.state.exposure * 1000)
            node_map.ExposureAuto.value = "Off"
            node_map.ExposureTime.value = float(self.state.exposure * 1000)

            logger.info("Starting image acquirer...")
            self._ia.start()
            try:
                logger.info("Fetching frame (timeout=2.0s)...")
                with self._ia.fetch(timeout=2.0) as buffer:
                    component = buffer.payload.components[0]
                    logger.info("Got frame: %sx%s", component.width, component.height)
                    frame = np.array(component.data).reshape(component.height, component.width)

                    if dest_path is not None:
                        filepath = dest_path
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    else:
                        self._capture_count += 1
                        filename = f"capture_{self._capture_count:03d}.jpg"
                        filepath = os.path.join(self.data_dir, filename)

                    cv2.imwrite(filepath, frame)
                    logger.info("Saved image to %s", filepath)
                    return filepath
            finally:
                self._ia.stop()
        except Exception as e:
            logger.exception("_do_capture failed: %s: %r", type(e).__name__, e)
            raise RuntimeError(f"{type(e).__name__}: {repr(e)}") from e

    async def capture(self, dest_path: str | None = None) -> str:
        """Captures a frame from the camera and saves it to disk.

        Args:
            dest_path: If provided, save the image to this path instead of
                       the default data directory.
        """
        self.state.status = Status.BUSY
        try:
            filepath = await asyncio.to_thread(self._do_capture, dest_path)
            self.state.last_image_path = filepath
            self.state.status = Status.IDLE
            return filepath
        except Exception:
            self.state.status = Status.ERROR
            raise

    def close(self) -> None:
        """Release the image acquirer and GenTL producer resources."""
        self._ia.destroy()
        self._harvester.reset()
