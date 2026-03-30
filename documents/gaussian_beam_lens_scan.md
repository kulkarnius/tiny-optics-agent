---
title: "Gaussian Beam Waist Measurement via Moving Lens and CCD Camera"
authors: ["Rao, A. Srinivasa", "Sharan, Alok"]
year: 2018
arxiv_id: "1807.10739"
source_pdf: "rao_2018_beam_waist_spot_size.pdf"
ingested_at: "2026-03-29T00:00:00Z"
sha256: "test-fixture-no-pdf"
supplementary: ["Self (1983) Appl. Opt. 22(5)", "Siegman Lasers (1986) Ch.17"]
---

# Gaussian Beam Waist Measurement via Moving Lens and CCD Camera

## Abstract

From the standard TEM00 Gaussian beam profile equations, equations for beam waist at
lens focus are derived as a function of variable spot size measured at different
positions along the optical axis. Two closed-form equations for beam waist are obtained
and their physical validity is established with respect to the Rayleigh length. The
method is experimentally verified with a He-Ne laser at 632 nm. The technique enables
beam waist estimation by measuring spot sizes at accessible positions — particularly
useful when the true waist is too small or too intense to measure directly. By
translating a focusing lens and recording the resulting spot size on a fixed CCD camera,
the beam caustic can be reconstructed to recover w0, z0, and M².

---

## 1. Introduction and Physical Setup

### 1.1 Motivation

In many laser experiments the beam waist is too small to measure directly (damage
threshold of detectors), or located inside optical elements. An indirect method is
needed: measure the beam spot size w(z) at one or more accessible positions z after a
focusing lens, then invert the propagation equations to recover the waist w0.

The complementary approach — scanning the lens position while keeping a CCD camera
fixed — achieves the same goal. As the lens moves along the optical axis, the image of
the focused waist sweeps through positions relative to the fixed camera. The camera
records a different spot size at each lens position. Fitting the resulting w_CCD(z_lens)
curve to the Gaussian propagation model recovers w0 and the Rayleigh range z_R.

### 1.2 Physical Setup: Fixed Camera, Moving Lens

The experimental arrangement consists of:
- A collimated laser beam of known input radius W_in propagating along z
- A thin converging lens of focal length f, mounted on a translation stage
- A fixed CCD camera at distance L from the start of the rail

As the lens translates to position d (distance from the camera), the spot size on the
CCD changes because the lens images the beam waist to a different axial location.

---

## 2. Gaussian Beam Propagation Equations

### 2.1 Free-Space Propagation

A TEM00 Gaussian beam propagating along z with waist w0 at position z = 0 has radius:

    w(z)^2 = w0^2 * [1 + (z / z_R)^2]                        (Eq. 1)

where the Rayleigh range is:

    z_R = pi * w0^2 / lambda                                   (Eq. 2)

At z = z_R the beam radius has grown to w0 * sqrt(2). The far-field half-angle
divergence is:

    theta = lambda / (pi * w0)     [M^2 = 1 case]             (Eq. 3)

### 2.2 Beam Waist After a Thin Lens (Self 1983)

For a collimated input beam of radius W_in striking a thin lens of focal length f,
the focused spot radius at the lens back focal plane is:

    w0_focused = (lambda * f) / (pi * W_in)                   (Eq. 4)

This is the diffraction-limited spot size (M^2 = 1). For a real beam with M^2 > 1:

    w0_focused = M^2 * (lambda * f) / (pi * W_in)             (Eq. 5)

The depth of focus (twice the Rayleigh range of the focused spot) is:

    DOF = 2 * z_R_focused = 2 * pi * w0_focused^2 / lambda    (Eq. 6)

### 2.3 Generalised Thin Lens Equation for Gaussian Beams

When the input beam has waist w_in at distance s from the lens (object distance,
measured as positive when beam waist is to the left of the lens), the output waist w_out
is located at image distance s' given by the modified thin lens equation:

    1/(s' - f) = 1/(s - f) + 1/(z_R_in^2 / (s - f))

For the important special case of a collimated input beam (s → ∞, i.e. the input waist
is at infinity), the waist is formed at the back focal plane:

    s' = f
    w_out = (lambda * f) / (pi * W_in)                        (Eq. 7)

For a non-collimated input beam with waist at distance u from the lens:

    w_out^2 = w_in^2 / [(1 - u/f)^2 + (z_R_in/f)^2]         (Eq. 8)

    s' = f + (u - f) / [(1 - u/f)^2 + (z_R_in/f)^2]         (Eq. 9)

### 2.4 Spot Size as a Function of CCD Distance from Lens

After the lens forms a focused waist w0' at image distance s' from the lens, the beam
continues to propagate. A CCD camera at distance d_cam from the lens measures spot size:

    w_CCD^2 = w0'^2 * [1 + ((d_cam - s') / z_R')^2]          (Eq. 10)

where z_R' = pi * w0'^2 / lambda is the Rayleigh range of the focused beam.

---

## 3. Inversion: Recovering Waist from Measured Spot Size

### 3.1 Forward Problem

Given w0 and z_R, compute w(z) at any position using Eq. 1. This is straightforward.

### 3.2 Inverse Problem: Two Closed-Form Solutions

Given a measured spot size w(z) at known position z relative to the waist, recover w0.
Substituting Eq. 2 into Eq. 1 and rearranging yields a fourth-order polynomial in w0
(Rao & Sharan 2018, Eq. 3):

    w0^4 - w(z)^2 * w0^2 + (lambda * z / pi)^2 = 0            (Eq. 11)

This biquadratic has two physically meaningful solutions:

    w0_+ = sqrt[ w(z)^2/2 * (1 + sqrt(1 - (2*lambda*z / (pi*w(z)^2))^2)) ]   (Eq. 12)

    w0_- = sqrt[ w(z)^2/2 * (1 - sqrt(1 - (2*lambda*z / (pi*w(z)^2))^2)) ]   (Eq. 13)

The discriminant condition for real solutions requires:

    2 * lambda * z / (pi * w(z)^2) <= 1                        (Eq. 14)

which is equivalent to requiring that the measurement be taken within the valid
propagation regime. At the Rayleigh position (z = z_R), both solutions converge to the
same value w0 = w(z_R) / sqrt(2).

### 3.3 Choosing the Correct Branch

- For z <= z_R (measurement taken in near field or at waist): Eq. 12 (w0_+) gives the
  physical solution.
- For z >= z_R (measurement taken in far field): Eq. 13 (w0_-) gives the physical
  solution.

In practice, when scanning the lens position, multiple (z, w) pairs are measured and a
full hyperbolic fit is used, making branch selection unnecessary.

---

## 4. Moving-Lens Scan Methodology

### 4.1 Principle

With a fixed CCD camera and a translating lens, varying the lens position d from the
camera sweeps the focused waist position relative to the camera. The spot size recorded
by the camera w_CCD(d) traces a hyperbolic caustic as a function of lens position.

For a collimated input beam of radius W_in, a lens at distance d from the camera
focuses a waist of:

    w0'(d) ≈ lambda * d / (pi * W_in)                         (Eq. 15, far-field limit)

More precisely, using the thin lens formula (Eq. 7-9), the full expression accounts
for the Rayleigh range of the input beam. In the paraxial limit where d >> z_R_in:

    w0_focused ≈ (lambda * f) / (pi * W_in)                   (Eq. 16)

independent of d. The waist position shifts with d, producing the caustic shape.

### 4.2 Fitting Procedure

The camera records spot sizes w_i at N lens positions d_i. A nonlinear least-squares
fit of the propagation model to the data (w_i^2 vs d_i) recovers:

- w0: the minimum beam waist at focus
- z0: the axial position of the beam waist
- z_R: the Rayleigh range of the focused beam
- M^2: the beam quality factor (if multiple wavelengths or reference measurement available)

The fit model is:

    w_model(d)^2 = w0^2 * [1 + (M^2 * (d - z0) / z_R)^2]    (Eq. 17)

where z_R = pi * w0^2 / lambda is the Rayleigh range of the embedded ideal Gaussian.

### 4.3 ISO 11146 Sampling Requirements

Per ISO 11146, for an unambiguous fit the scan should include:
- At least 5 camera frames within one Rayleigh range of the focused waist
- At least 5 camera frames beyond two Rayleigh ranges from the waist
- Total minimum of 10 distinct lens positions

For a focused spot with z_R_focused = pi * w0_focused^2 / lambda, the total scan
range should span at least 4 * z_R_focused centred on the waist.

---

## 5. CCD Camera Spot Size Extraction

### 5.1 2D Gaussian Fit

The beam spot size at each lens position is extracted from the CCD image by fitting a
2D Gaussian intensity model to the pixel data:

    I(x, y) = A * exp(-2 * ((x - x0)^2 / w_x^2 + (y - y0)^2 / w_y^2)) + B  (Eq. 18)

where A is peak intensity, (x0, y0) is beam centroid, w_x and w_y are 1/e^2 half-widths,
and B is background level. For a circular beam, w_x ≈ w_y = w.

### 5.2 Second-Moment (D4sigma) Width

The ISO 11146 standard requires beam width to be defined using the second moment
(D4sigma method):

    d_x = 4 * sigma_x = 4 * sqrt( sum(I_ij * (x_i - x_bar)^2) / sum(I_ij) )  (Eq. 19)

For a Gaussian beam, D4sigma equals the 1/e^2 diameter: d_x = 2 * w_x.

### 5.3 Minimum CCD Resolution Requirement

Per ISO 11146, the beam must cover at least 10 pixels in diameter at all measurement
positions. The camera pixel size p_x and magnification must satisfy:

    2 * w_min / p_x >= 10    (pixel coverage requirement)

For a typical CCD with 5.5 µm pixels, the minimum measurable w is ~28 µm.

---

## 6. Experimental Validation (He-Ne Laser, 632 nm)

### 6.1 Setup Parameters

- Laser: He-Ne CW, 632.8 nm, 5 mW, TEM00
- Input beam radius at lens: W_in ≈ 4.3 mm (expanded beam)
- Focusing lens: f = 100 mm, mounted on 300 mm translation stage
- Fixed CCD camera: pixel size 5.5 µm, 1280 × 1024 pixels
- Neutral density filters: OD 3.0 to prevent CCD saturation

### 6.2 Expected Focused Waist

From Eq. 16 for M^2 = 1:

    w0 = lambda * f / (pi * W_in)
       = 632.8e-9 * 100e-3 / (pi * 4.3e-3)
       = 4.69 µm

Rayleigh range of focused spot:

    z_R = pi * w0^2 / lambda
        = pi * (4.69e-6)^2 / 632.8e-9
        = 109 µm

### 6.3 Experimental Results

From pinhole scan at z = 31.7 cm from the focused waist, measured spot size w = 4.7 cm.
Applying Eq. 13 (far-field branch, z >> z_R):

    w0 = (lambda * z) / (pi * w(z))
       = (632.8e-9 * 0.317) / (pi * 0.047)
       = 1.36e-2 mm = 13.6 µm

This agrees with the independently measured spot size at the lens position of 4.3 mm,
confirming internal consistency of the method.

---

## 7. Key Equations Summary

| Quantity | Equation | Notes |
|---|---|---|
| Gaussian propagation | w(z)^2 = w0^2 * [1 + (z/z_R)^2] | Eq. 1, fundamental |
| Rayleigh range | z_R = pi * w0^2 / lambda | Eq. 2 |
| Focused spot (collimated) | w0' = lambda * f / (pi * W_in) | Eq. 7, M^2=1 |
| Focused spot (real beam) | w0' = M^2 * lambda * f / (pi * W_in) | Eq. 5 |
| CCD spot vs lens position | w_CCD^2 = w0'^2 * [1 + ((d - z0)/z_R')^2] | Eq. 10, fit this |
| Inverse (near-field branch) | w0 = sqrt(w^2/2 * (1 + sqrt(1 - (2lz/pw^2)^2))) | Eq. 12 |
| Inverse (far-field branch) | w0 = sqrt(w^2/2 * (1 - sqrt(1 - (2lz/pw^2)^2))) | Eq. 13 |
| ISO 11146 fit model | w(z)^2 = w0^2 * [1 + (M^2*(z-z0)/z_R)^2] | Eq. 17, hyperbolic |
| 2D Gaussian fit (CCD) | I(x,y) = A*exp(-2((x-x0)^2/wx^2 + (y-y0)^2/wy^2)) + B | Eq. 18 |
| D4sigma width | d = 4*sqrt(sum(I*(x-xbar)^2)/sum(I)) | Eq. 19, ISO standard |
