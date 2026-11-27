import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import weibull_min
from matplotlib.gridspec import GridSpec


if __name__== "__main__":

    # --- Parameters ---
    x = np.linspace(0, 7, 200)        # X axis for Weibull
    lambda_vals = np.linspace(1, 5, 100)  # Lambda varying over "time"
    k = 2  # fixed shape parameter

    # --- Meshgrid ---
    X, LAMBDA = np.meshgrid(x, lambda_vals)

    # --- Weibull PDF with time-varying scale ---
    Y = weibull_min.pdf(X, c=k, scale=LAMBDA)

    # --- Projections ---
    proj_XY = np.trapezoid(Y, lambda_vals, axis=0)   # integrate over lambda
    proj_LAMBDA_Y = np.trapezoid(Y, x, axis=1)      # integrate over x

    # --- Layout ---
    fig = plt.figure(figsize=(10, 8))
    gs = GridSpec(
        2, 2,
        width_ratios=[4, 1.5],
        height_ratios=[4, 1.5],
        wspace=0.15,
        hspace=0.30
    )

    # --- Main 3D plot ---
    ax3d = fig.add_subplot(gs[0, 0], projection="3d")
    mappable = ax3d.plot_surface(LAMBDA, X, Y, cmap="viridis")
    ax3d.set_xlabel("Lambda (scale)", labelpad=10)
    ax3d.set_ylabel("t", labelpad=10)
    ax3d.set_title(r"Time Dependent Weibull with Parameteric $\lambda(t)$ ")
    ax3d.view_init(elev=25, azim=-60)

    # --- Right projection: (X, Y) ---
    ax_right = fig.add_subplot(gs[0, 1])
    ax_right.plot(proj_XY, x)
    ax_right.set_title("Standard Weibull Distribution")

    # --- Bottom projection: (Lambda, Y) ---
    ax_bottom = fig.add_subplot(gs[1, 0])
    # Use peak density for convex behavior
    peak_density = (k / lambda_vals) * ( ( (k-1)/(k) )**(k-1) ) * np.exp(-( (k-1)/k )**k)  # approx peak
    ax_bottom.plot(lambda_vals, peak_density)
    ax_bottom.set_xlabel("Lambda (scale)")
    ax_bottom.set_ylabel("Peak density")
    ax_bottom.set_title(r"Example $\lambda(t)$")

    # --- Bottom-right contour ---
    ax_br = fig.add_subplot(gs[1, 1])
    ax_br.contourf(LAMBDA, X, Y, levels=30, cmap="viridis")
    ax_br.set_xlabel("Lambda")
    ax_br.set_ylabel("t")
    ax_br.set_title("Contour Plot")

    plt.savefig("weibull_time_varying_scale.png", dpi=300)
    plt.show()
