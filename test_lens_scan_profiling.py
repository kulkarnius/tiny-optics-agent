"""
TEST CASE: Gaussian Beam Profiling via Moving Lens + Fixed CCD Camera
=====================================================================
Science Assistant End-to-End Validation

Physical Setup
--------------
A collimated laser beam passes through a converging lens mounted on a translation
stage. A CCD camera sits at a fixed position downstream. As the lens moves along
the rail, the focused spot sweeps back and forth relative to the camera — the camera
records a different spot size at each lens position. Fitting the resulting caustic
recovers w0, z0, and M².

                  [Laser] --> [moving lens on rail] --> [fixed CCD]
                              <--- scan d_lens --->       (fixed)

This is the standard ISO 11146 lens-scan M² measurement. Reference paper:
Rao & Sharan (2018), arXiv:1807.10739, plus Self (1983) Appl. Opt. 22(5).
RAG document: gaussian_beam_lens_scan.md

How to Run
----------
See the walkthrough at the bottom of this file (Section: HOW TO USE THIS SCRIPT).

Five run_code blocks are defined below. Each is a self-contained chunk to paste
into the Claude conversation as a separate run_code() call.

System Prompt
-------------
You are a laser optics research assistant. Before performing any calculation, you
MUST call search_documents to retrieve relevant equations and parameters from the
paper index. Ground all equations in the retrieved paper chunks.When citing results, 
include the source_file, section_hierarchy, and relevance_score from the search_documents output. 
Before writing any code, output a numbered plan covering: 
(1) the analytical pre-checks you'll perform, 
(2) what each scratchpad call will do, 
(3) anticipated failure modes and how you'll handle them. Only then proceed.

User Queries (send these to Claude in order)
--------------------------------------------
Q1: "Using the Gaussian beam propagation equations from Rao 2018, simulate the
    spot size w_CCD recorded by a fixed camera as we translate a 100 mm focal
    length lens along a 300 mm rail. Use lambda = 632.8 nm, input beam radius
    W_in = 4.3 mm, M^2 = 1.0. Plot the caustic."

Q2: "Now simulate the same lens scan for M^2 = 1.0, 1.3, and 1.8. For each,
    add realistic camera noise (5 µm rms) and run the ISO 11146 hyperbolic fit
    to recover w0 and M^2. Compare recovered vs. true values."

Q3: "Generate synthetic CCD images of the beam at three lens positions: well
    before focus, at focus, and well past focus. Fit a 2D Gaussian to each image
    using Eq. 18 from the paper to extract the spot size."

Q4: "Using Equations 12 and 13 from Rao 2018, demonstrate the two-branch
    inversion: given a single measured spot size w(z) at a known distance z from
    the waist, recover w0. Show which branch applies on each side of the Rayleigh
    range."

Q5: "Plot the minimum number of lens positions required to satisfy the ISO 11146
    sampling rule (5 near-field + 5 far-field) for our setup, and show the
    sensitivity of the M^2 fit to the number of measurement points."
"""

# =============================================================================
# BLOCK 1 — Caustic curve: spot size vs. lens position
# =============================================================================
# Run this first. It establishes the core geometry and produces the main
# diagnostic plot the rest of the test builds on.

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# ── Experimental parameters (Rao & Sharan 2018, Section 6.1) ──────────────────
lambda_m   = 632.8e-9   # wavelength [m], He-Ne laser (paper Section 6.1)
W_in       = 4.3e-3     # input collimated beam radius at lens [m] (paper Sec 6.1)
f_lens     = 100e-3     # lens focal length [m]
L_rail     = 0.30       # total rail length [m]
M2         = 1.0        # beam quality factor (ideal Gaussian for first run)

# ── Derived quantities ─────────────────────────────────────────────────────────
# Focused waist radius (Eq. 7, Rao 2018, collimated input)
w0_focus = (lambda_m * f_lens) / (np.pi * W_in)
# Rayleigh range of focused spot (Eq. 2)
zR_focus = np.pi * w0_focus**2 / lambda_m

print(f"Focused waist radius  w0' = {w0_focus*1e6:.2f} µm")
print(f"Rayleigh range       z_R' = {zR_focus*1e6:.1f} µm  ({zR_focus*1e3:.3f} mm)")
print(f"Depth of focus (2*zR)     = {2*zR_focus*1e3:.3f} mm")

# ── Spot size seen by fixed CCD as lens translates ────────────────────────────
# When lens is at distance d from the camera (d = L_rail - d_from_source):
#   - For a collimated input, the lens forms a waist at its back focal plane,
#     i.e. at distance f behind the lens = distance (d - f) from the camera.
#   - The CCD is at d_cam = 0 (fixed), lens is at position d_lens from camera.
#   - Distance from focused waist to CCD = d_lens - f  (positive if CCD is past focus)
#
# This follows from Eq. 10 (paper): w_CCD^2 = w0'^2 * [1 + ((d_cam - s')/z_R')^2]
# where s' = d_lens - f (image distance from camera reference)

def spot_on_ccd(d_lens, f, w0, zR, M2=1.0):
    """
    Spot size seen by fixed CCD at position 0 when lens is at d_lens.
    Focused waist is at d_lens - f from the camera (Eq. 10, Rao 2018).
    """
    z_from_waist = d_lens - f          # signed distance: CCD to focused waist
    return w0 * np.sqrt(1 + (M2 * z_from_waist / zR)**2)

# Scan lens from 20 mm to 280 mm from the camera
d_lens_range = np.linspace(0.02, 0.28, 500)
w_ccd = spot_on_ccd(d_lens_range, f_lens, w0_focus, zR_focus, M2)

# Focus position: where CCD is at the waist (d_lens = f, so z_from_waist = 0)
d_focus = f_lens
w_min   = w0_focus

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    "Lens-Scan Beam Caustic — Fixed CCD, Moving Lens\n"
    f"λ = {lambda_m*1e9:.1f} nm,  f = {f_lens*1e3:.0f} mm,  W_in = {W_in*1e3:.1f} mm  "
    f"(Rao & Sharan 2018, arXiv:1807.10739)",
    fontsize=12, fontweight='bold'
)

ax = axes[0]
ax.plot(d_lens_range * 1e3, w_ccd * 1e6, color='steelblue', lw=2.5, label='w_CCD(d_lens)')
ax.axvline(d_focus * 1e3, color='tomato', ls='--', lw=1.5, label=f'Focus at d = {d_focus*1e3:.0f} mm')
ax.axhline(w_min * 1e6, color='tomato', ls=':', lw=1.5, alpha=0.7,
           label=f"w0' = {w_min*1e6:.1f} µm")
ax.axvspan((d_focus - zR_focus)*1e3, (d_focus + zR_focus)*1e3,
           alpha=0.12, color='green', label=f'Rayleigh zone ±z_R = ±{zR_focus*1e3:.2f} mm')
ax.set_xlabel('Lens position from CCD  d_lens [mm]', fontsize=11)
ax.set_ylabel('Spot radius on CCD  w_CCD [µm]', fontsize=11)
ax.set_title('Caustic: CCD Spot Size vs. Lens Position', fontsize=11)
ax.legend(fontsize=9)
ax.grid(alpha=0.3)

# ── ISO 11146 sample positions ────────────────────────────────────────────────
d_near = np.linspace(d_focus - 0.9*zR_focus, d_focus + 0.9*zR_focus, 5)
d_far  = np.concatenate([
    np.linspace(d_focus - 4*zR_focus, d_focus - 2.1*zR_focus, 3),
    np.linspace(d_focus + 2.1*zR_focus, d_focus + 4*zR_focus, 2)
])
d_samples = np.sort(np.concatenate([d_near, d_far]))
w_samples = spot_on_ccd(d_samples, f_lens, w0_focus, zR_focus, M2)

ax2 = axes[1]
ax2.plot(d_lens_range * 1e3, w_ccd * 1e6, color='steelblue', lw=2, alpha=0.5, label='True caustic')
ax2.scatter(d_samples * 1e3, w_samples * 1e6, color='tomato', zorder=5, s=80,
            label='ISO 11146 sample points (N=10)')
ax2.scatter(d_near * 1e3, spot_on_ccd(d_near, f_lens, w0_focus, zR_focus, M2) * 1e6,
            color='darkorange', zorder=6, s=80, marker='D', label='Near-field (5 pts)')
ax2.scatter(d_far * 1e3, spot_on_ccd(d_far, f_lens, w0_focus, zR_focus, M2) * 1e6,
            color='purple', zorder=6, s=80, marker='s', label='Far-field (5 pts)')
ax2.set_xlabel('Lens position from CCD  d_lens [mm]', fontsize=11)
ax2.set_ylabel('Spot radius on CCD  w_CCD [µm]', fontsize=11)
ax2.set_title('ISO 11146 Sampling Strategy\n(5 near-field + 5 far-field points)', fontsize=11)
ax2.legend(fontsize=9)
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('shared/caustic_lens_scan.png', dpi=150, bbox_inches='tight')
plt.show()
print(f"\nFigure saved: caustic_lens_scan.png")
print(f"Focus at lens position d = {d_focus*1e3:.1f} mm from camera")
print(f"Minimum spot on CCD: w0' = {w0_focus*1e6:.2f} µm")


# =============================================================================
# BLOCK 2 — M² recovery: noisy scan + hyperbolic fit
# =============================================================================
# Simulates the actual measurement process with noise and fits the ISO 11146
# hyperbolic model to recover w0 and M².

def hyperbolic_model(d, w0, z0, M2_fit):
    """
    ISO 11146 fit model (Eq. 17, Rao 2018):
    w(d)^2 = w0^2 * [1 + (M2 * (d - z0) / z_R)^2]
    where z_R = pi * w0^2 / lambda (Rayleigh range of embedded Gaussian)
    """
    zR = np.pi * w0**2 / lambda_m
    return w0**2 * (1 + (M2_fit * (d - z0) / zR)**2)

M2_true_vals = [1.0, 1.3, 1.8]
colors       = ['steelblue', 'darkorange', 'tomato']
noise_rms    = 5e-6      # 5 µm rms noise on spot size measurement

# Denser sampling for a realistic scan
d_scan = np.linspace(0.02, 0.28, 25)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    "M² Recovery via Hyperbolic Fit to Noisy Lens Scan\n"
    "(ISO 11146 method — Eq. 17, Rao & Sharan 2018)",
    fontsize=12, fontweight='bold'
)

results = []
for M2_true, col in zip(M2_true_vals, colors):
    # Simulate measurement
    w_true  = spot_on_ccd(d_scan, f_lens, w0_focus, zR_focus, M2_true)
    w_noisy = np.abs(w_true + np.random.normal(0, noise_rms, len(d_scan)))

    # Fit w^2 vs d (linear in parameters, more stable)
    try:
        popt, pcov = curve_fit(
            hyperbolic_model, d_scan, w_noisy**2,
            p0=[w0_focus, d_focus, M2_true],
            bounds=([1e-7, 0.0, 0.8], [1e-3, 0.5, 5.0]),
            maxfev=10000
        )
        w0_fit, z0_fit, M2_fit = popt
        perr = np.sqrt(np.diag(pcov))
        results.append((M2_true, M2_fit, w0_fit, z0_fit))
        label = f'M²_true={M2_true} → fit: M²={M2_fit:.2f}±{perr[2]:.2f}, w0={w0_fit*1e6:.1f}µm'
    except RuntimeError:
        label = f'M²_true={M2_true} (fit failed)'
        popt  = [w0_focus, d_focus, M2_true]

    axes[0].scatter(d_scan * 1e3, w_noisy * 1e6, color=col, s=25, alpha=0.7)
    d_fine = np.linspace(0.02, 0.28, 300)
    w_fit_curve = np.sqrt(hyperbolic_model(d_fine, *popt))
    axes[0].plot(d_fine * 1e3, w_fit_curve * 1e6, color=col, lw=2, label=label)

axes[0].set_xlabel('Lens position d_lens [mm]', fontsize=11)
axes[0].set_ylabel('Spot radius w_CCD [µm]', fontsize=11)
axes[0].set_title(f'Noisy Scan (σ_noise = {noise_rms*1e6:.0f} µm) + Hyperbolic Fit', fontsize=10)
axes[0].legend(fontsize=8)
axes[0].grid(alpha=0.3)

# ── Error summary bar chart ───────────────────────────────────────────────────
# results tuple layout: (M2_true, M2_fit, w0_fit, z0_fit)
#   index 0 = M2_true
#   index 1 = M2_fit   (recovered beam quality factor)
#   index 2 = w0_fit   (recovered waist in metres)
#   index 3 = z0_fit   (recovered waist position in metres)
if results:
    ax2 = axes[1]
    m2_true = [r[0] for r in results]
    m2_rec  = [r[1] for r in results]   # index 1 = M2_fit
    errs    = [abs(rec - tr) / tr * 100 for rec, tr in zip(m2_rec, m2_true)]
    bars = ax2.bar([str(t) for t in m2_true], errs, color=colors[:len(results)],
                   width=0.5, zorder=3)
    ax2.axhline(3, color='gray', ls='--', lw=1.5, label='3% target accuracy')
    ax2.set_xlabel('True M²', fontsize=11)
    ax2.set_ylabel('Relative error in M² [%]', fontsize=11)
    ax2.set_title('Fit Accuracy by M² Value', fontsize=11)
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.3, axis='y', zorder=0)
    # Always show at least 0–5% on y-axis so bars are visible even when error < 0.1%
    max_err = max(errs) if errs else 1.0
    ax2.set_ylim(0, max(max_err * 1.4, 5.0))
    for i, (tr, rec, err) in enumerate(zip(m2_true, m2_rec, errs)):
        ax2.text(i, err + max(max_err * 0.04, 0.1),
                 f'recovered:\n{rec:.3f}', ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('shared/M2_hyperbolic_fit.png', dpi=150, bbox_inches='tight')
plt.show()
print("Figure saved: M2_hyperbolic_fit.png")
for r in results:
    print(f"  M²_true={r[0]:.1f}  →  M²_fit={r[1]:.4f},  w0={r[2]*1e6:.2f}µm,  z0={r[3]*1e3:.2f}mm")


# =============================================================================
# BLOCK 3 — Synthetic CCD images at three lens positions
# =============================================================================
# Simulates what the camera actually sees at three lens positions:
# before focus, at focus, and after focus. Fits 2D Gaussian to extract spot size.

from scipy.optimize import curve_fit as cf2d

def gaussian_2d(xy, A, x0, y0, wx, wy, B):
    """
    2D Gaussian intensity model (Eq. 18, Rao & Sharan 2018):
    I(x,y) = A * exp(-2*((x-x0)^2/wx^2 + (y-y0)^2/wy^2)) + B
    """
    x, y = xy
    return (A * np.exp(-2 * ((x - x0)**2 / wx**2 + (y - y0)**2 / wy**2)) + B).ravel()

# ── Three lens positions to image ─────────────────────────────────────────────
# Positions: 2*z_R before focus, at focus, 2*z_R after focus
d_before = d_focus - 2 * zR_focus
d_at     = d_focus
d_after  = d_focus + 2 * zR_focus

positions  = [d_before, d_at, d_after]
pos_labels = [
    f'Before focus\n(d = {d_before*1e3:.2f} mm)',
    f'At focus\n(d = {d_at*1e3:.2f} mm)',
    f'After focus\n(d = {d_after*1e3:.2f} mm)'
]
colors_pos = ['steelblue', 'tomato', 'darkorange']

# CCD pixel grid: 256×256 pixels, 5.5 µm pitch, centred on beam
Npix      = 256
pix_size  = 5.5e-6   # m
x_pix     = (np.arange(Npix) - Npix//2) * pix_size
X_pix, Y_pix = np.meshgrid(x_pix, x_pix)

fig, axes = plt.subplots(2, 3, figsize=(14, 9))
fig.suptitle(
    "Synthetic CCD Images at Three Lens Positions\n"
    "2D Gaussian Fit (Eq. 18) extracts spot size  |  λ = 632.8 nm",
    fontsize=12, fontweight='bold'
)

for col, (d_pos, label) in enumerate(zip(positions, pos_labels)):
    w_true = spot_on_ccd(d_pos, f_lens, w0_focus, zR_focus, M2=1.0)

    # Simulate CCD image with shot noise
    signal  = np.exp(-2 * (X_pix**2 + Y_pix**2) / w_true**2)
    noise   = np.random.normal(0, 0.02, signal.shape)   # 2% rms noise
    image   = np.clip(signal + noise, 0, None)

    # ── Display image ──────────────────────────────────────────────────────────
    ax_img = axes[0, col]
    ext    = [-Npix//2 * pix_size * 1e6, Npix//2 * pix_size * 1e6] * 2
    im = ax_img.imshow(image, extent=ext, origin='lower', cmap='inferno', vmin=0, vmax=1)
    ax_img.set_title(label, fontsize=10)
    ax_img.set_xlabel('x [µm]')
    ax_img.set_ylabel('y [µm]')
    plt.colorbar(im, ax=ax_img, label='Norm. Intensity', fraction=0.046, pad=0.04)

    # Mark true 1/e² radius circle
    theta_c  = np.linspace(0, 2*np.pi, 200)
    ax_img.plot(w_true*1e6*np.cos(theta_c), w_true*1e6*np.sin(theta_c),
                'w--', lw=1.5, label=f'True 1/e² = {w_true*1e6:.0f}µm')
    ax_img.legend(fontsize=8, loc='upper right')

    # ── 2D Gaussian fit ────────────────────────────────────────────────────────
    try:
        xy_flat = (X_pix.ravel(), Y_pix.ravel())
        p0 = [1.0, 0.0, 0.0, w_true, w_true, 0.0]
        popt2d, _ = cf2d(gaussian_2d, xy_flat, image.ravel(), p0=p0, maxfev=5000)
        A_fit, x0_fit, y0_fit, wx_fit, wy_fit, B_fit = popt2d
        w_fit_mean = np.sqrt(abs(wx_fit) * abs(wy_fit))
        err_pct = abs(w_fit_mean - w_true) / w_true * 100
        fit_label = f'Fit: wx={abs(wx_fit)*1e6:.1f}µm, wy={abs(wy_fit)*1e6:.1f}µm\nError: {err_pct:.1f}%'
    except RuntimeError:
        wx_fit, wy_fit, w_fit_mean = w_true, w_true, w_true
        fit_label = 'Fit failed'

    # ── Profile + fit ──────────────────────────────────────────────────────────
    ax_prof = axes[1, col]
    mid      = Npix // 2
    profile  = image[mid, :]
    ax_prof.plot(x_pix * 1e6, profile, color='steelblue', lw=1.5, label='CCD row profile')
    x_fit_fine = np.linspace(x_pix[0], x_pix[-1], 500)
    gauss_fit  = popt2d[0] * np.exp(-2 * (x_fit_fine - popt2d[1])**2 / popt2d[3]**2) + popt2d[5]
    ax_prof.plot(x_fit_fine * 1e6, gauss_fit, color='tomato', lw=2, label=fit_label)
    ax_prof.axvline(wx_fit * 1e6, color='gray', ls=':', lw=1)
    ax_prof.axvline(-wx_fit * 1e6, color='gray', ls=':', lw=1)
    ax_prof.axhline(np.exp(-2), color='gray', ls='--', lw=1, alpha=0.7, label='1/e² level')
    ax_prof.set_xlabel('x position [µm]', fontsize=10)
    ax_prof.set_ylabel('Intensity [a.u.]', fontsize=10)
    ax_prof.set_title(f'Row Profile + 2D Gaussian Fit\n(true w = {w_true*1e6:.1f} µm)', fontsize=10)
    ax_prof.legend(fontsize=8)
    ax_prof.grid(alpha=0.3)
    ax_prof.set_ylim(-0.1, 1.2)

plt.tight_layout()
plt.savefig('shared/ccd_images_three_positions.png', dpi=150, bbox_inches='tight')
plt.show()
print("Figure saved: ccd_images_three_positions.png")


# =============================================================================
# BLOCK 4 — Two-branch inversion (Eqs. 12 & 13, Rao 2018)
# =============================================================================
# Given a single (z, w(z)) measurement, recover w0 using the two closed-form
# branches. Shows which branch is valid on each side of the Rayleigh range.

def recover_w0_plus(w_meas, z, lam):
    """
    Near-field branch (Eq. 12, Rao & Sharan 2018): valid for z <= z_R.
    w0 = sqrt( w^2/2 * (1 + sqrt(1 - (2*lambda*z/(pi*w^2))^2)) )
    """
    disc = 1 - (2 * lam * z / (np.pi * w_meas**2))**2
    disc = np.where(disc >= 0, disc, np.nan)
    return np.sqrt(w_meas**2 / 2 * (1 + np.sqrt(disc)))

def recover_w0_minus(w_meas, z, lam):
    """
    Far-field branch (Eq. 13, Rao & Sharan 2018): valid for z >= z_R.
    w0 = sqrt( w^2/2 * (1 - sqrt(1 - (2*lambda*z/(pi*w^2))^2)) )
    """
    disc = 1 - (2 * lam * z / (np.pi * w_meas**2))**2
    disc = np.where(disc >= 0, disc, np.nan)
    return np.sqrt(w_meas**2 / 2 * (1 - np.sqrt(disc)))

# Ground truth: focused beam with known w0
w0_true = w0_focus
zR_true = zR_focus

z_range  = np.linspace(-4 * zR_true, 4 * zR_true, 500)
w_range  = w0_true * np.sqrt(1 + (z_range / zR_true)**2)

# Recover w0 from each (z, w) pair using both branches
w0_plus  = recover_w0_plus(w_range, np.abs(z_range), lambda_m)
w0_minus = recover_w0_minus(w_range, np.abs(z_range), lambda_m)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    "Two-Branch Inversion: Recovering w0 from Single (z, w) Measurement\n"
    "Equations 12 & 13 — Rao & Sharan (2018) arXiv:1807.10739",
    fontsize=12, fontweight='bold'
)

ax = axes[0]
ax.plot(z_range / zR_true, w_range * 1e6, 'k-', lw=2, label='True w(z)')
ax.axvline(-1, color='gray', ls=':', lw=1, alpha=0.7)
ax.axvline(+1, color='gray', ls=':', lw=1, alpha=0.7, label='±z_R boundary')
ax.axvline(0,  color='gray', ls='--', lw=1, alpha=0.5)
ax.axhline(w0_true * 1e6, color='tomato', ls='--', lw=1.5, label=f'w0 = {w0_true*1e6:.1f} µm')
ax.set_xlabel('z / z_R', fontsize=11)
ax.set_ylabel('Beam radius [µm]', fontsize=11)
ax.set_title('Gaussian Caustic (true beam)', fontsize=11)
ax.legend(fontsize=10)
ax.grid(alpha=0.3)

ax2 = axes[1]
ax2.plot(z_range / zR_true, w0_plus * 1e6, color='steelblue', lw=2.5,
         label='Eq. 12 (w0_+): valid near z ≤ z_R')
ax2.plot(z_range / zR_true, w0_minus * 1e6, color='darkorange', lw=2.5, ls='--',
         label='Eq. 13 (w0_−): valid near z ≥ z_R')
ax2.axhline(w0_true * 1e6, color='tomato', ls=':', lw=2,
            label=f'True w0 = {w0_true*1e6:.1f} µm')
ax2.axvspan(-1, 1, alpha=0.08, color='green', label='Near-field region |z| < z_R')
ax2.axvline(-1, color='gray', ls=':', lw=1)
ax2.axvline(+1, color='gray', ls=':', lw=1, label='±z_R boundary')
ax2.set_xlabel('z / z_R', fontsize=11)
ax2.set_ylabel('Recovered w0 [µm]', fontsize=11)
ax2.set_title('Recovered w0 from Both Inversion Branches', fontsize=11)
ax2.set_ylim(0, w0_true * 1e6 * 3)
ax2.legend(fontsize=9)
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('shared/two_branch_inversion.png', dpi=150, bbox_inches='tight')
plt.show()

# ── Numerical check at specific positions ─────────────────────────────────────
for z_frac, name in [(-0.5, 'z = -0.5 z_R'), (0.5, 'z = 0.5 z_R'),
                     (1.0, 'z = z_R'), (2.5, 'z = 2.5 z_R')]:
    z_abs = abs(z_frac) * zR_true
    w_meas_val = w0_true * np.sqrt(1 + z_frac**2)
    r_plus  = recover_w0_plus(w_meas_val, z_abs, lambda_m)
    r_minus = recover_w0_minus(w_meas_val, z_abs, lambda_m)
    print(f"{name:15s}: w0_+ = {r_plus*1e6:.2f} µm  |  w0_− = {r_minus*1e6:.2f} µm  "
          f"  (true = {w0_true*1e6:.2f} µm)")


# =============================================================================
# BLOCK 5 — ISO 11146 sampling sensitivity: N measurement points vs. M² error
# =============================================================================
# Shows how fit accuracy degrades as you use fewer lens positions, motivating
# the ISO 11146 minimum of 10 points.

N_points_range = [4, 6, 8, 10, 15, 20, 30]
M2_target      = 1.3
n_trials        = 80    # Monte Carlo trials per N

mean_errors = []
std_errors  = []

for N_pts in N_points_range:
    errs = []
    # Spread N_pts across the scan range (not ISO-compliant for small N)
    d_scan_N = np.linspace(d_focus - 4*zR_focus, d_focus + 4*zR_focus, N_pts)
    w_true_N = spot_on_ccd(d_scan_N, f_lens, w0_focus, zR_focus, M2_target)

    for _ in range(n_trials):
        w_noisy = np.abs(w_true_N + np.random.normal(0, noise_rms, N_pts))
        try:
            popt, _ = curve_fit(
                hyperbolic_model, d_scan_N, w_noisy**2,
                p0=[w0_focus, d_focus, M2_target],
                bounds=([1e-7, 0.0, 0.8], [1e-3, 0.5, 5.0]),
                maxfev=5000
            )
            errs.append(abs(popt[2] - M2_target) / M2_target * 100)
        except RuntimeError:
            errs.append(np.nan)

    errs = [e for e in errs if not np.isnan(e)]
    mean_errors.append(np.mean(errs) if errs else np.nan)
    std_errors.append(np.std(errs) if errs else np.nan)

fig, ax = plt.subplots(figsize=(9, 5))
ax.errorbar(N_points_range, mean_errors, yerr=std_errors,
            color='steelblue', marker='o', ms=8, lw=2, capsize=5, label='Mean M² error ± 1σ')
ax.axvline(10, color='tomato', ls='--', lw=2, label='ISO 11146 minimum (10 pts)')
ax.axhline(3, color='gray', ls=':', lw=1.5, label='3% accuracy target')
ax.fill_between(N_points_range, 0, 3, alpha=0.06, color='green', label='< 3% error zone')
ax.set_xlabel('Number of lens positions N', fontsize=12)
ax.set_ylabel('Relative M² error [%]', fontsize=12)
ax.set_title(
    f'M² Fit Accuracy vs. Number of Scan Points\n'
    f'(M²_true = {M2_target}, σ_noise = {noise_rms*1e6:.0f} µm, {n_trials} trials per N)',
    fontsize=11, fontweight='bold'
)
ax.legend(fontsize=10)
ax.grid(alpha=0.3)
ax.set_xlim(3, 31)
plt.tight_layout()
plt.savefig('shared/iso11146_sampling_sensitivity.png', dpi=150, bbox_inches='tight')
plt.show()
print("Figure saved: iso11146_sampling_sensitivity.png")

print("\n=== All blocks complete. Expected figures in shared/: ===")
for f in ['caustic_lens_scan.png', 'M2_hyperbolic_fit.png',
          'ccd_images_three_positions.png', 'two_branch_inversion.png',
          'iso11146_sampling_sensitivity.png']:
    print(f"  {f}")


# =============================================================================
# HOW TO USE THIS SCRIPT
# =============================================================================
#
# STEP 1 — PREPARE YOUR RAG SERVER
# ---------------------------------
# Copy gaussian_beam_lens_scan.md into your RAG server's documents/ folder.
# Confirm ingestion by calling search_documents("Gaussian beam lens scan spot size")
# and checking that chunks from the paper appear in the results.
#
# STEP 2 — OPEN A CLAUDE CONVERSATION
# -------------------------------------
# Open a new conversation with both MCP servers connected:
#   - RAG server (rag_server.py)
#   - Scratchpad server (scratchpad_server.py)
#
# STEP 3 — SET THE SYSTEM PROMPT
# --------------------------------
# Paste the system prompt from the top of this file (the triple-quoted block
# starting "You are a laser optics research assistant...") into the system
# prompt field of your interface, or prepend it as the first user message.
#
# STEP 4 — SEND QUERY 1
# -----------------------
# Send User Query Q1 verbatim. Watch Claude:
#   a) Call search_documents("Gaussian beam lens scan CCD spot size") — it should
#      return chunks from Section 4 (Moving-Lens Scan) and Section 2 (propagation).
#   b) Call run_code with the code from BLOCK 1.
#
# WHAT TO CHECK after Q1:
#   - The plot shows a hyperbolic caustic with minimum at d = 100 mm from camera.
#   - w0' printed to console matches the analytic value ~4.69 µm (He-Ne at 632 nm,
#     f = 100 mm, W_in = 4.3 mm).
#   - search_documents results reference source_file = "gaussian_beam_lens_scan.md"
#     with section_hierarchy containing "Moving-Lens Scan Methodology".
#
# STEP 5 — SEND QUERY 2
# -----------------------
# Send Q2. Claude should run BLOCK 2 and produce a figure with three caustics
# for M² = 1.0, 1.3, 1.8. Check:
#   - Recovered M² values are within ~5% of true values.
#   - The bar chart shows error <3% for M² = 1.0 and rising for higher M².
#   - search_documents citations include Section 4.2 (Fitting Procedure) and Eq. 17.
#
# STEP 6 — SEND QUERY 3
# -----------------------
# Send Q3. Claude should run BLOCK 3. Check:
#   - Three CCD images are produced (dark wide ring before focus, tight bright
#     spot at focus, spreading ring after focus).
#   - 2D Gaussian fit extracts w_x, w_y within ~2% of the true spot size.
#   - search_documents citations include Section 5 (CCD Camera Spot Size Extraction)
#     and Eq. 18 (2D Gaussian fit model).
#
# STEP 7 — SEND QUERY 4
# -----------------------
# Send Q4. Claude should run BLOCK 4. Check:
#   - w0_+ (Eq. 12) returns the true w0 for z < z_R and diverges for z > z_R.
#   - w0_- (Eq. 13) returns the true w0 for z > z_R and diverges for z < z_R.
#   - The printed table shows correct branch switching at z = z_R.
#   - search_documents citations include Section 3.3 (Choosing the Correct Branch)
#     and Eqs. 12-13.
#
# STEP 8 — SEND QUERY 5
# -----------------------
# Send Q5. Claude should run BLOCK 5. Check:
#   - M² error > 10% for N < 6 measurement points.
#   - M² error drops below 3% at N ≥ 10, consistent with ISO 11146 minimum.
#   - search_documents citations include Section 4.3 (ISO 11146 Sampling Requirements).
#
# STEP 9 — VALIDATE PROVENANCE
# -----------------------------
# After all five queries, inspect the results/ directory. For each run you should
# find a directory results/<run_id>/ containing:
#   - record.json with: schema_version, run_id, session_id, code, stdout, stderr,
#     error, success, timestamp, content_hash, figures (list of {filename, sha256,
#     size_bytes} dicts)
#   - The figure .png files copied from shared/
#
# WHAT VALIDATES THE CHAIN:
#   ✓ results/index.json lists all runs newest-first with run_id, session_id,
#     success, timestamp, and content_hash
#   ✓ All five figures appear in results/<run_id>/ alongside record.json
#   ✓ record.json success == true for all five blocks
#   ✓ record.json stdout contains the expected printed values (e.g. w0' = 4.69 µm)
#
# TROUBLESHOOTING
# ----------------
# Problem: Claude does not call search_documents before run_code.
# Fix:     Re-emphasise the system prompt instruction. Add the sentence
#          "Before writing any code, confirm which paper section you are using
#          and cite it explicitly."
#
# Problem: Claude doesn't cite paper sections in its response.
# Fix:     Ask explicitly: "Please re-read the search_documents result from
#          earlier and quote the section heading and equation numbers you used."
#
# Problem: Figures are not appearing in shared/.
# Fix:     Confirm the scratchpad Docker container has shared/ mounted. Check
#          list_figures() output after Block 1 completes.
#
# Problem: 2D Gaussian fit fails in Block 3 (RuntimeError).
# Fix:     The beam may be too small relative to the pixel grid. Increase Npix
#          or increase pix_size to 10 µm to give more pixels per spot.
#
# Expected console output for Block 1:
#   Focused waist radius  w0' = 4.69 µm
#   Rayleigh range       z_R' = 109.4 µm  (0.109 mm)
#   Depth of focus (2*zR)     = 0.219 mm
#   Figure saved: caustic_lens_scan.png
#   Focus at lens position d = 100.0 mm from camera
#   Minimum spot on CCD: w0' = 4.69 µm
