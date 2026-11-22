from matplotlib import pyplot as plt
from matplotlib import patheffects
import numpy as np


class MainExample1:

    def __init__(
        self,
        spacing=3,
        num_lines=20,
        figsize=(10, 6),
        xlim=(0, 10),
        ylim=(0, 10),
        title=r"Values of $3x_1 + 5x_2$",
    ):
        self.spacing = spacing
        self.num_lines = num_lines
        self.figsize = figsize
        self.xlim = xlim
        self.ylim = ylim
        self.title = title

        self.fig = None
        self.ax = None

    def new_plot(self):
        """Initializes a fresh figure with the objective heatmap and contours."""
        self.fig, self.ax = plt.subplots(figsize=self.figsize)

        x1 = np.linspace(*self.xlim, 400)
        x2 = np.linspace(*self.ylim, 400)
        X1, X2 = np.meshgrid(x1, x2)

        # Objective function values across the grid
        Z = 3 * X1 + 5 * X2

        # Match discrete levels
        levels = [i * self.spacing for i in range(1, self.num_lines + 1)]

        # Filled heatmap-like bands
        cf = self.ax.contourf(
            X1, X2, Z, levels=levels, cmap="viridis", extend="both"
        )

        # Crisp contour lines
        cs = self.ax.contour(
            X1, X2, Z, levels=levels, colors="white", linewidths=0.8, alpha=0.8
        )
        self.ax.clabel(cs, inline=True, fontsize=8, fmt="c=%d")

        self.fig.colorbar(cf, ax=self.ax, label=r"$3x_1 + 5x_2$")
        self.ax.set_title(self.title)
        self.ax.set_xlabel(r"$x_1$")
        self.ax.set_ylabel(r"$x_2$")
        self.ax.set_xlim(*self.xlim)
        self.ax.set_ylim(*self.ylim)
        return self

    def add_constraint(
        self,
        a1,
        a2,
        b,
        label=None,
        color="#FF3B30",
        shade_infeasible=True,
        hatch="///",
    ):
        """Adds a linear constraint a1*x1 + a2*x2 <= b, graying out the infeasible area."""
        if self.ax is None:
            self.new_plot()

        label = label or rf"${a1}x_1 + {a2}x_2 \leq {b}$"
        x1 = np.linspace(*self.xlim, 400)

        # Thin black halo behind the line so any highlight color stays readable
        halo = [
            patheffects.Stroke(linewidth=4, foreground="black", alpha=0.7),
            patheffects.Normal(),
        ]

        if a2 == 0:
            x_bound = b / a1
            self.ax.plot(
                [x_bound, x_bound],
                self.ylim,
                color=color,
                linewidth=2.5,
                path_effects=halo,
                zorder=5,
                label=label,
            )
            if shade_infeasible:
                x_fill = (
                    [x_bound, self.xlim[1]]
                    if a1 > 0
                    else [self.xlim[0], x_bound]
                )
                self.ax.fill_between(
                    x_fill,
                    self.ylim[0],
                    self.ylim[1],
                    facecolor="#1F1F1F",
                    edgecolor="#4A4A4A",
                    hatch=hatch,
                    alpha=0.45,
                    zorder=4,
                )
        else:
            x2 = (b - a1 * x1) / a2
            self.ax.plot(
                x1,
                x2,
                color=color,
                linewidth=2.5,
                path_effects=halo,
                zorder=5,
                label=label,
            )
            if shade_infeasible:
                y_bound = self.ylim[1] if a2 > 0 else self.ylim[0]
                self.ax.fill_between(
                    x1,
                    x2,
                    y_bound,
                    facecolor="#1F1F1F",
                    edgecolor="#4A4A4A",
                    hatch=hatch,
                    alpha=0.45,
                    zorder=4,
                )

        return self

    def show(self):
        """Finalizes layout, renders legend if needed, and displays the plot."""
        if self.ax is None:
            self.new_plot()

        handles, _ = self.ax.get_legend_handles_labels()
        if handles:
            self.ax.legend(loc="upper right", framealpha=0.95)

        self.fig.tight_layout()
        plt.show()


example1 = MainExample1(spacing=4, num_lines=20)