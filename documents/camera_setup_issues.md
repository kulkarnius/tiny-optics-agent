# Camera-Lens Setup: Known Artifacts & Image Processing Recommendations

## Overview

This document describes known optical and sensor artifacts observed in the current camera-lens setup. Any features described below are **not** representative of the subject being imaged and should be identified, masked, or suppressed during image processing.

---

## Known Artifacts

### 1. Bright Overexposed Blobs (Right Side of Frame)
Two large, irregular white shapes appear consistently on the right-center portion of the frame. These are fully saturated (pixel value = 255) and appear in every image regardless of the scene. They are likely caused by:
- Stray ambient light or reflections entering the optical path from the side
- Internal lens reflections or flare from nearby light sources
- Unshielded optical elements within the setup reflecting into the sensor

**Impact:** High — these blobs occupy a significant portion of the right half of the frame and can easily be mistaken for or obscure real signal.

---

### 2. Vertical Line Artifact (Far Right Edge)
A thin, bright vertical line runs along or near the right edge of the frame. This is a persistent artifact present across all captures. Likely causes include:
- A gap or seam in the optical housing allowing a sliver of external light to reach the sensor
- A dead column or charge bleed artifact on the camera sensor itself
- Edge reflection from a lens element or aperture

**Impact:** Medium — confined to the far right edge but may affect any signal present in that region.

---

### 3. Small Bright Specks / Hot Pixels
Several small, isolated bright points are scattered across the frame, particularly in the lower-center region. These are consistent in position across captures, which strongly suggests they are:
- **Hot pixels** — sensor pixels with elevated dark current that register as bright even without illumination
- Minor fixed-pattern noise inherent to the sensor

**Impact:** Low individually, but could be misidentified as real signal if the subject of interest is also small and point-like.

---

### 4. Non-Uniform Dark Background (Vignetting / Uneven Illumination)
The background is not uniformly black — it exhibits a slightly uneven grey tone with subtle variations across the frame. This is caused by:
- **Vignetting** — light falloff toward the edges due to the lens geometry
- Sensor dark current / thermal noise producing a non-zero background floor
- Ambient light leakage into the imaging enclosure

**Impact:** Medium — makes thresholding and background subtraction more difficult if a flat background level is assumed.

---

### 5. Small Streak / Slash Artifacts
A small diagonal streak or slash shape appears on the left-center of the frame. This may be caused by:
- A particle or piece of debris on the sensor or a lens element
- A scratch on an optical surface catching stray light

**Impact:** Low — small and localized, but worth monitoring as it could grow or shift over time.

---

## Image Processing Recommendations

### 1. Background / Dark Frame Subtraction
Capture a **dark frame** — an image taken with no subject present and under identical exposure conditions (as done here with the laser off). Subtract this dark frame from all subsequent subject images pixel-by-pixel. This will:
- Remove hot pixels
- Eliminate fixed-pattern noise
- Suppress the persistent blobs and vertical line artifact
- Flatten the uneven background

```
corrected_image = subject_image - dark_frame
```
Clip negative values to zero after subtraction.

---

### 2. Static Artifact Masking
Since the blobs, vertical line, and hot pixels appear in consistent, known positions, create a **binary bad-pixel / artifact mask** from the dark frame by thresholding bright regions. Apply this mask to all processed images, zeroing out or ignoring those regions entirely.

```
mask = dark_frame > threshold  # True where artifacts exist
corrected_image[mask] = 0
```

---

### 3. Flat-Field Correction
To correct for vignetting and non-uniform sensitivity across the sensor, capture a **flat-field image** using a known uniform illumination source. Divide subject images by the normalized flat-field:

```
corrected_image = raw_image / normalized_flat_field
```

This corrects for both lens vignetting and pixel-to-pixel sensitivity variation.

---

### 4. Region of Interest (ROI) Cropping
Given that the right side of the frame is heavily contaminated by the bright blobs and vertical line artifact, consider **cropping the active ROI** to exclude the rightmost portion of the frame. Restricting analysis to a known-clean region reduces the risk of artifact contamination entirely.

---

### 5. Hot Pixel Correction
Identify hot pixel locations from the dark frame and replace their values in subject images using interpolation from neighboring pixels:

```
for each hot pixel at (x, y):
    corrected_image[x, y] = mean(neighbors(x, y))
```

Most scientific imaging libraries (e.g., `astropy`, `scikit-image`) include utilities for this.

---

### 6. Thresholding Strategy
When trying to isolate real signal from background, use an **adaptive or percentile-based threshold** rather than a fixed value, since the background level is non-uniform. For example, set the threshold at mean + N×std of the background region to flag only statistically significant signal.

---

### 7. Repeated Averaging
If the subject allows it, capture **multiple frames and average them**. This reduces random noise while preserving consistent real signal, and further suppresses non-repeatable noise sources.

---

## Summary Table

| Artifact | Location | Severity | Recommended Fix |
|---|---|---|---|
| Bright overexposed blobs | Right-center | High | Dark frame subtraction + masking |
| Vertical line | Far right edge | Medium | Masking or ROI crop |
| Hot pixels / bright specks | Scattered | Low | Hot pixel correction |
| Uneven background / vignetting | Global | Medium | Flat-field correction |
| Diagonal streak | Left-center | Low | Masking; inspect optics for debris |

---

## Recommended Processing Pipeline

1. Capture dark frame (no subject)
2. Generate artifact mask from dark frame
3. Capture flat-field image
4. For each subject image:
   - Subtract dark frame
   - Divide by normalized flat-field
   - Apply artifact mask
   - Crop to clean ROI
   - Apply threshold to isolate signal
   - (Optional) Average multiple frames
