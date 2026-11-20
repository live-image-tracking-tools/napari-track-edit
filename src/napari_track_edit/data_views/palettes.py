"""The colormaps offered for coloring by a feature.

Append a name to a list to offer it.

- `GRADIENTS`: continuous colormaps for numeric features, looked up with
  napari's `ensure_colormap`.
- `CATEGORICAL_PALETTES`: palettes for features with few categories. Either a
  name in the `cmap` catalog (https://cmap-docs.readthedocs.io/), or one of the
  `GENERATED_PALETTES` below. Fixed-size palettes first, by size: the first one
  with a color for every category is the default.
- `ID_PALETTES`: palettes for tracklet and lineage ids. "random" is napari's
  random label colormap; the others are generated palettes.
"""

from __future__ import annotations

import colorsys
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

# Palettes generated for any number of colors: evenly spaced bright hues in a
# fixed random order, so neighbouring categories (or ids) do not get
# neighbouring hues. "purple-orange" keeps to blue-purple and magenta-orange
# hues; "varied" also varies the saturation, for more contrast between
# colors with similar hues. Contributed by Caroline Malin-Mayor.
GENERATED_PALETTES: dict[str, dict] = {
    "hues": {},
    "hues varied": {"vary_saturation": True},
    "purple-orange": {"purple_orange": True},
    "purple-orange varied": {"purple_orange": True, "vary_saturation": True},
}

CATEGORICAL_PALETTES: tuple[str, ...] = (
    "tab10",
    "tab20",
    *GENERATED_PALETTES,
)

RANDOM_IDS = "random"
ID_PALETTES: tuple[str, ...] = (RANDOM_IDS, *GENERATED_PALETTES)

# The palette used for more categories than any fixed-size palette has colors.
_UNBOUNDED_PALETTE = "hues"


def hue_palette(
    n: int,
    purple_orange: bool = False,
    vary_saturation: bool = False,
    seed: int = 0,
) -> np.ndarray:
    """`n` (N, 3) RGB colors with evenly spaced hues, in a fixed random order.

    The seed is fixed so that a palette is the same in every session.
    """
    n = max(int(n), 1)
    rng = np.random.default_rng(seed)
    if purple_orange:
        half = n // 2
        hues = [0.65 + 0.25 * i / n for i in range(half)]
        hues += [(0.90 + 0.25 * i / n) % 1.0 for i in range(half, n)]
    else:
        hues = [i / n for i in range(n)]
    saturations = 0.45 + 0.55 * rng.random(n) if vary_saturation else np.ones(n)
    colors = np.array(
        [colorsys.hsv_to_rgb(h, s, 1.0) for h, s in zip(hues, saturations, strict=True)]
    )
    return colors[rng.permutation(n)]


@cache
def palette_colors(name: str, n: int | None = None) -> np.ndarray:
    """The (N, 3) RGB colors of palette `name`. A generated palette is made
    with `n` colors (20 if not given); a catalog palette has its own size."""
    if name in GENERATED_PALETTES:
        return hue_palette(n or 20, **GENERATED_PALETTES[name])
    return np.asarray(Colormap(name).color_stops.color_array[:, :3], dtype=float)


def palette_for(n_categories: int) -> str:
    """The default palette for `n_categories` categories: the smallest
    fixed-size palette in CATEGORICAL_PALETTES with a color for each, or a
    generated one (which has exactly as many colors as needed)."""
    for name in CATEGORICAL_PALETTES:
        if name not in GENERATED_PALETTES and len(palette_colors(name)) >= n_categories:
            return name
    return _UNBOUNDED_PALETTE
