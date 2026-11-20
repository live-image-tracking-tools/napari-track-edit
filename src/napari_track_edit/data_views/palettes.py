"""The colormaps offered for coloring by a feature.

Append a name to a list to offer it; colors come from the packages, not from
this file.

- `GRADIENTS`: continuous colormaps for numeric features, looked up with
  napari's `ensure_colormap`.
- `CATEGORICAL_PALETTES`: qualitative palettes for features with few categories,
  looked up in the `cmap` catalog (https://cmap-docs.readthedocs.io/). Order
  them by size: the first palette with a color for every category is used.
"""

from __future__ import annotations

from functools import cache

import numpy as np
from cmap import Colormap

GRADIENTS: tuple[str, ...] = (
    "viridis",
    "plasma",
    "magma",
    "inferno",
    "turbo",
    "twilight",
)

CATEGORICAL_PALETTES: tuple[str, ...] = (
    "tab10",
    "tab20",
)


@cache
def palette_colors(name: str) -> np.ndarray:
    """The (N, 3) RGB colors of a categorical palette from the `cmap` catalog."""
    return np.asarray(Colormap(name).color_stops.color_array[:, :3], dtype=float)


def palette_for(n_categories: int) -> str:
    """The smallest palette in CATEGORICAL_PALETTES with a color for every one
    of `n_categories` categories, or the largest if none has enough."""
    for name in CATEGORICAL_PALETTES:
        if len(palette_colors(name)) >= n_categories:
            return name
    return max(CATEGORICAL_PALETTES, key=lambda name: len(palette_colors(name)))
