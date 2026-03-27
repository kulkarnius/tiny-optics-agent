import os
import cv2
import numpy as np
from pydantic import Field
from typing import Optional
from .base import BaseDevice, DeviceState, Status

class CameraState(DeviceState):
    exposure: int = Field(default=100, ge=1, le=2000)
    last_image_path: Optional[str] = None

class MockCamera(BaseDevice):
    def __init__(self, data_dir="data"):
        super().__init__()
        self.state = CameraState()
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