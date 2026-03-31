import os
import cv2
import numpy as np
from pathlib import Path
from pydantic import Field
from typing import Optional
from .base import BaseDevice, DeviceState, Status

_DEFAULT_DATA_DIR = str(Path(__file__).parent.parent / "data")

class CameraState(DeviceState):
    exposure: int = Field(default=100, ge=1, le=2000)
    last_image_path: Optional[str] = None
    um_per_pixel: Optional[float] = Field(
        default=None,
        description="Microns per pixel at the sample plane. None if uncalibrated.",
    )

class MockCamera(BaseDevice):
    def __init__(self, data_dir=_DEFAULT_DATA_DIR):
        super().__init__()
        um_per_pixel_env = os.environ.get("CAMERA_UM_PER_PIXEL")
        um_per_pixel = float(um_per_pixel_env) if um_per_pixel_env is not None else None
        self.state = CameraState(um_per_pixel=um_per_pixel)
        self.data_dir = data_dir
        self._capture_count = 0

        # Ensure the data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

    async def capture(self) -> str:
        """Mocks capturing a frame and saving it to disk."""
        self.state.status = Status.BUSY
        self._capture_count += 1
        
        # Generate a blank 2D grayscale array (480x640)
        blank_frame = np.zeros((480, 640), dtype=np.uint8)
        
        # Add a mock label so we know it's working
        cv2.putText(blank_frame, f"Mock Capture #{self._capture_count}", 
                    (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,), 2)
        
        # Save to disk
        filename = f"capture_{self._capture_count:03d}.jpg"
        filepath = os.path.join(self.data_dir, filename)
        cv2.imwrite(filepath, blank_frame)
        
        self.state.last_image_path = filepath
        self.state.status = Status.IDLE
        
        return filepath