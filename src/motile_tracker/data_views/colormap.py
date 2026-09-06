from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
from napari.utils import DirectLabelColormap
from napari.utils.colormaps import label_colormap

if TYPE_CHECKING:
    from funtracks.data_model import Tracks


@runtime_checkable
class ColorSource(Protocol):
    """Maps an array of ids/values to an (N, 4) RGBA array.

    Duck-type compatible with `CyclicLabelColormap.map`, so it's a drop-in
    replacement anywhere a napari colormap's `.map()` is used for track-id
    coloring. Swap in a continuous-feature or constant-color source later
    without touching `TrackColormap` or its consumers.
    """

    def map(self, values: np.ndarray) -> np.ndarray: ...


class CategoricalColorSource:
    """Default `ColorSource`: cyclic color per unique id, 0 -> transparent.

    Not track-specific - works for any categorical id (cell type, lineage id).
    """

    def __init__(self, num_colors: int = 49, seed: float = 0.5):
        self._cyclic_colormap = label_colormap(
            num_colors, seed=seed, background_value=0
        )

    def map(self, values: np.ndarray) -> np.ndarray:
        return self._cyclic_colormap.map(values)

    def shuffle(self, num_colors: int, seed: float) -> None:
        """Replace the color cycle (see `TrackLabels.new_colormap`)."""
        self._cyclic_colormap = label_colormap(
            num_colors, seed=seed, background_value=0
        )


class TrackColormap:
    """Node -> display color for a `Tracks` object, with color and alpha as
    independently updatable state (unlike `DirectLabelColormap`, which
    conflates them in one `color_dict`).

    `to_direct_colormap()` builds a fresh napari colormap on every call via
    `DirectLabelColormap.model_construct`, which skips pydantic's per-color
    validation entirely (the expensive part of a normal `DirectLabelColormap(
    ...)` call) - see that method. This replaces three copies of a
    mutate-in-place-then-clear-cache trick that used to live in `TrackLabels`,
    `custom_table_widget`, and `ortho_views.py`, working around that
    validation cost; with it gone, there's nothing left to work around.

    Color is a two-step composition, `node -> feature value -> RGB`:
    `feature_key` names the `Tracks` node attribute to read (default: the
    track id attribute, `tracks.features.tracklet_key`) via
    `tracks.get_nodes_attr`, and `color_source` maps that value to a color.
    Swapping `feature_key` (e.g. to an area/volume attribute) or
    `color_source` (e.g. to a continuous colormap) are independent, composable
    changes - neither needs to know about the other.

    There's no per-node color setter, since a node's color should always be a
    pure function of its feature value: recoloring happens by changing
    `color_source` (e.g. `shuffle`) and calling `set_tracks()` again to
    re-derive colors. `add_node` is the exception, for nodes that need a
    color before `Tracks` knows about them.

    `set_tracks()` does the full O(node count) node/color recompute
    immediately - not lazily. `set_alpha` never triggers it: it only ever
    touches alpha, so the hot path (every selection/hover change) stays cheap.
    """

    def __init__(
        self,
        color_source: ColorSource | None = None,
        feature_key: str | None = None,
        default_alpha: float = 1.0,
    ):
        self._color_source: ColorSource = color_source or CategoricalColorSource()
        self._feature_key = feature_key
        self._default_alpha = default_alpha
        self._tracks: Tracks | None = None
        # Cache of node -> RGB (alpha lives only in self._alpha, so alpha-only
        # updates - set_alpha, the hot path - never touch this), so
        # get_color/get_colors/to_direct_colormap don't re-derive colors
        # (color_source.map, feature lookup) on every call - only
        # set_tracks/add_node touch color_source, everything else just reads this.
        # Keys always match self._alpha's.
        self._node_colors: dict[int, np.ndarray] = {}
        self._alpha: dict[int, float] = {}

    @property
    def color_source(self) -> ColorSource:
        return self._color_source

    @color_source.setter
    def color_source(self, color_source: ColorSource) -> None:
        """Assigning a new `color_source` immediately re-derives node colors
        from it (same cost as `set_tracks` - one vectorized `color_source.map`
        call), so `_node_colors` never goes stale relative to it. Mutating the
        current source in place (e.g. `.shuffle()`) doesn't go through this
        setter - call `set_tracks` again afterward to pick up its new colors,
        same as any other recolor.
        """
        self._color_source = color_source
        self.set_tracks(self._tracks)

    @property
    def feature_key(self) -> str | None:
        return self._feature_key

    @feature_key.setter
    def feature_key(self, feature_key: str | None) -> None:
        """Assigning a new `feature_key` immediately re-derives node colors
        from it (see `color_source` setter)."""
        self._feature_key = feature_key
        self.set_tracks(self._tracks)

    def _feature_values(self, tracks: Tracks, nodes) -> list:
        key = self.feature_key or tracks.features.tracklet_key
        return tracks.get_nodes_attr(nodes, key)

    def map(self, values: np.ndarray) -> np.ndarray:
        """Map feature values to base RGBA (no per-node alpha, no cache lookup).
        Delegates straight to `color_source`, so this is a drop-in replacement
        anywhere a napari colormap's `.map()` is used for track-id coloring.

        Unlike `get_color`/`get_colors`, this never consults `_node_colors` -
        `values` here are feature values (e.g. track ids), not node ids, so
        there's no "unknown node" case to fall back on.
        """
        return self.color_source.map(values)

    def set_tracks(self, tracks: Tracks | None) -> None:
        """Point this colormap at a `Tracks` object and recompute node colors
        from it immediately (O(node count) - color_source.map + one vectorized
        feature lookup). Existing per-node alpha overrides for nodes that are
        still present are preserved; overrides for removed nodes are dropped
        and new nodes default to `default_alpha`.
        """
        self._tracks = tracks
        nodes = tracks.graph.node_ids() if tracks is not None else []
        values = self._feature_values(tracks, nodes) if tracks is not None else []
        if len(values) > 0:
            # One vectorized call - color_source.map has a large fixed
            # per-call overhead, so mapping per-node is much slower.
            mapped = self.color_source.map(np.asarray(values))
            colors = {
                node: rgba[:3].copy() for node, rgba in zip(nodes, mapped, strict=True)
            }
        else:
            colors = {}

        self._alpha = {
            node: self._alpha.get(node, self._default_alpha) for node in nodes
        }
        self._node_colors = colors

    def add_node(self, node: int, feature_value) -> None:
        """Add a node not yet known to `self._tracks`, colored via
        `color_source.map(feature_value)`. Alpha defaults to `default_alpha`.

        `feature_value` must be passed in (rather than looked up via
        `feature_key`, like `set_tracks` does) because callers need this
        before the node exists in the `Tracks` graph - e.g.
        `TrackLabels._new_label`, previewing a color while painting.
        """
        rgba = self.color_source.map(np.asarray([feature_value]))[0]
        self._node_colors[node] = np.asarray(rgba[:3], dtype=float).copy()
        self._alpha[node] = self._default_alpha

    def remove_node(self, node: int) -> None:
        self._node_colors.pop(node, None)
        self._alpha.pop(node, None)

    def set_alpha(self, nodes, value: float) -> None:
        """Set alpha for many nodes at once - the hot path, fired on every
        selection/hover change. Only ever touches alpha, never node colors.
        """
        for node in nodes:
            if node is not None and node in self._alpha:
                self._alpha[node] = value

    def get_alpha(self, node: int, default: float = 0.0) -> float:
        return self._alpha.get(node, default)

    def get_color(self, node: int) -> np.ndarray:
        """RGBA (color + alpha) for a node; transparent black if unknown."""
        if node not in self._node_colors:
            return np.zeros(4)
        return self._colored(node)

    def get_colors(self, nodes: np.ndarray) -> np.ndarray:
        """Vectorized `get_color`: RGBA per node id in `nodes`, in order.
        Unknown nodes get transparent black. For napari-independent
        consumers (e.g. the table widget) that need many colors at once
        without going through `to_direct_colormap()`.
        """
        return np.array([self.get_color(node) for node in nodes])

    @property
    def nodes(self):
        return self._node_colors.keys()

    def to_direct_colormap(self) -> DirectLabelColormap:
        """Build a fresh napari `DirectLabelColormap` for the current
        color/alpha state.

        Uses `model_construct` instead of the normal constructor to skip
        pydantic's per-color validation (`transform_color` on every entry) -
        the ~400x-slower path for large graphs. Safe here because every value
        we hand it is already a properly-shaped (4,) float array; napari's
        validation exists for arbitrary user input (color names, 3-channel
        colors, etc.), not for values built this way.
        """
        return DirectLabelColormap.model_construct(
            color_dict={
                **{node: self._colored(node) for node in self._node_colors},
                None: np.array([0, 0, 0, 0], dtype=float),
            },
            colors=np.zeros(3),
        )

    def _colored(self, node: int) -> np.ndarray:
        """RGB from `_node_colors` plus current alpha, as one RGBA array."""
        return np.append(self._node_colors[node], self._alpha.get(node, self._default_alpha))
