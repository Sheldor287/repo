import matplotlib.patches as patches
from matplotlib.path import Path
import numpy as np

def draw_database(ax, x, y, width, height, rx=None, ry=None, **kwargs):

    # Dimensions
    rx = width / 2 if rx is None else rx
    ry = height * 0.15 if ry is None else ry

    KAPPA = 0.56

    # Convert center coordinate into bottom/top
    y_bottom = y - height / 1.9
    y_top = y + height / 2

    verts = [
        # left side
        (x - rx, y_bottom),
        (x - rx, y_top),

        # top ellipse (back half)
        (x - rx, y_top + KAPPA*ry),
        (x - KAPPA*rx, y_top + ry),
        (x, y_top + ry),
        (x + KAPPA*rx, y_top + ry),
        (x + rx, y_top + KAPPA*ry),
        (x + rx, y_top),

        # right side
        (x + rx, y_bottom),

        # bottom ellipse
        (x + rx, y_bottom - KAPPA*ry),
        (x + KAPPA*rx, y_bottom - ry),
        (x, y_bottom - ry),
        (x - KAPPA*rx, y_bottom - ry),
        (x - rx, y_bottom - KAPPA*ry),
        (x - rx, y_bottom),

        # close
        (x - rx, y_bottom),
    ]

    codes = [
        Path.MOVETO,
        Path.LINETO,

        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,

        Path.LINETO,

        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,

        Path.CLOSEPOLY,
    ]

    body = patches.PathPatch(
        Path(verts, codes),
        **kwargs
    )

    ax.add_patch(body)


    # Top ellipse front edge
    top_front = [
        (x + rx, y_top),
        (x + rx, y_top - KAPPA*ry),
        (x + KAPPA*rx, y_top - ry),
        (x, y_top - ry),
        (x - KAPPA*rx, y_top - ry),
        (x - rx, y_top - KAPPA*ry),
        (x - rx, y_top),
    ]

    top_codes = [
        Path.MOVETO,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
    ]

    line_kwargs = kwargs.copy()
    line_kwargs["facecolor"] = "none"
    ax.add_patch(
        patches.PathPatch(
            Path(top_front, top_codes),
            **line_kwargs
        )
    )