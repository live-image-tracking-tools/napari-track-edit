from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
from napari.utils import DirectLabelColormap
from napari.utils.colormaps import label_colormap

if TYPE_CHECKING:
    from funtracks.data_model import Tracks

# What a node is painted with while its own color is not known yet - see add_node.
PINK = (0.75, 0.08, 0.4)
GREY = (0.7, 0.7, 0.7)  # What every node is colored when no feature is selected at all.


def construct_direct_colormap(color_dict: dict) -> DirectLabelColormap:
    """A `DirectLabelColormap` built without pydantic's per-color validation.

    `transform_color` on every entry is the ~400x-slower path on large graphs,
    and every color handed over here is already a properly-shaped (4,) float
    array - napari's validation is there for arbitrary user input (color
    names, 3-channel colors), not for values built this way.

    napari's models are native pydantic v2 from 0.7 on, where that constructor
    is `model_construct`. Before that they are built on `pydantic.v1`, which
    calls it `construct`.
    """
    construct = getattr(DirectLabelColormap, "model_construct", None)
    if construct is None:
        construct = DirectLabelColormap.construct
    return construct(color_dict=color_dict, colors=np.zeros(3))


@runtime_checkable
class ColorSource(Protocol):
    """Maps an array of ids/values to an (N, 4) RGBA array.

    Duck-type compatible with `CyclicLabelColormap.map`, so it's a drop-in
    replacement anywhere a napari colormap's `.map()` is used for track-id
    coloring. Swap in a continuous-feature or constant-color source later
    without touching `TrackColormap` or its consumers.

    `shuffle()` re-draws whatever colors the source uses, so the "new colormap"
    button does the right thing whichever source is installed.
    """

    def map(self, values: np.ndarray) -> np.ndarray: ...

    def shuffle(self) -> None: ...


class CategoricalColorSource:
    """Default `ColorSource`: cyclic color per unique id, 0 -> transparent.

    Not track-specific - works for any categorical id (cell type, lineage id).
    """

    def __init__(self, num_colors: int = 49, seed: float = 0.5):
        self._cyclic_colormap = label_colormap(
            num_colors, seed=seed, background_value=0
        )

    def map(self, values: np.ndarray) -> np.ndarray:
        # napari's cyclic colormap only accepts integer dtypes: a bool (group)
        # feature raises "Invalid integer data type", and a feature whose
        # default is None (lineage id) arrives as an object array. None becomes
        # 0, the colormap's transparent background entry.
        arr = np.asarray(values)
        if arr.dtype.kind in "OUS":
            flat = np.array(
                [0 if v is None else int(v) for v in np.atleast_1d(arr)],
                dtype=np.int64,
            )
            arr = flat if arr.ndim else flat[0]
        elif arr.dtype.kind in "bf":
            arr = arr.astype(np.int64)
        return self._cyclic_colormap.map(arr)

    def shuffle(self, num_colors: int | None = None, seed: float | None = None) -> None:
        """Replace the color cycle (see `TrackLabels.new_colormap`). With no
        arguments a random cycle is drawn, matching the argument-less
        `ColorSource.shuffle` that the "new colormap" button calls."""
        if num_colors is None:
            num_colors = random.randint(49, 69)
        if seed is None:
            seed = random.uniform(0, 1)
        self._cyclic_colormap = label_colormap(
            num_colors, seed=seed, background_value=0
        )


class BinaryColorSource:
    """Two colors for a boolean feature - the shape every group has."""

    def __init__(self, false_color=GREY, true_color=PINK):
        self.false_color = np.append(np.asarray(false_color, dtype=float), 1.0)
        self.true_color = np.append(np.asarray(true_color, dtype=float), 1.0)

    def map(self, values: np.ndarray) -> np.ndarray:
        arr = np.atleast_1d(np.asarray(values))
        # missing values (None) count as "not in the group", as the default does
        flags = (
            np.array([bool(v) for v in arr], dtype=bool)
            if arr.dtype.kind in "OUS"
            else arr.astype(bool)
        )
        colors = np.where(flags[:, np.newaxis], self.true_color, self.false_color)
        return colors[0] if np.asarray(values).ndim == 0 else colors

    def shuffle(self) -> None:
        """Get two fresh colors"""
        self.false_color, self.true_color = CategoricalColorSource(
            seed=random.uniform(0, 1)
        ).map(np.asarray([1, 2]))


class ConstantColorSource:
    """One color for every node"""

    def __init__(self, color=GREY):
        arr = np.asarray(color, dtype=float)
        self.color = arr if arr.shape == (4,) else np.append(arr, 1.0)

    def map(self, values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values)
        if arr.ndim == 0:
            return self.color.copy()
        return np.tile(self.color, (len(arr), 1))

    def shuffle(self) -> None:
        self.color = CategoricalColorSource(seed=random.uniform(0, 1)).map(
            np.asarray([1])
        )[0]


def make_color_source(tracks: Tracks | None, feature_key: str | None) -> ColorSource:
    """The `ColorSource` that can render a feature's values.

    A source and a feature have to match: a group's True/False needs two
    colors, no feature at all means one flat color, categorical features get random
    colors via CategoricalColorSource. TODO: GradientColorSource for continuous features.
    """
    if feature_key is None:
        return ConstantColorSource()
    feature = tracks.features.get(feature_key) if tracks is not None else None
    if feature is not None and feature["value_type"] == "bool":
        return BinaryColorSource()
    return CategoricalColorSource()


def color_feature_available(tracks: Tracks | None, feature_key: str | None) -> bool:
    """Whether `feature_key`'s values can actually be read off `tracks`.

    `tracks.features` only *describes* features; it is a plain dict that
    nothing keeps in sync with the graph (`FeatureDict.from_json` rebuilds it
    from saved metadata without consulting the graph), so a feature can be
    described without having a column to read. Coloring by one of those raises
    KeyError in `get_nodes_attr`, so callers check here first - the tree view
    does the same thing inline (see `extract_sorted_tracks`).

    None (one flat color) reads nothing, so it is always available.
    """
    if feature_key is None:
        return True
    if tracks is None:
        return False
    return (
        feature_key in tracks.features
        and feature_key in tracks.graph_solution.node_attr_keys()
    )


def categorical_feature_keys(tracks: Tracks | None) -> list[str]:
    """The node features that can currently drive coloring: tracklet id, lineage id, and
    every group (solution is excluded for now).

    Features with no column on the graph are left out - see
    `color_feature_available`. The column set is fetched once here rather than
    per key, since reading it can hit the database.
    """
    if tracks is None:
        return []
    features = tracks.features
    attr_keys = set(tracks.graph_solution.node_attr_keys())
    keys: list[str] = [
        key
        for key in (features.tracklet_key, features.lineage_key)
        if key is not None and key in features and key in attr_keys
    ]
    keys += [
        key
        for key, feature in features.node_features.items()
        if feature["value_type"] == "bool"
        and key != "solution"
        and key not in keys
        and key in attr_keys
    ]
    return keys


def feature_display_name(tracks: Tracks | None, feature_key: str | None) -> str:
    """The label to show for a feature in the UI."""
    if feature_key is None:
        return "None"
    feature = tracks.features.get(feature_key) if tracks is not None else None
    return feature_key if feature is None else feature.get("display_name", feature_key)


class TrackColormap:
    """Node -> display color for a `Tracks` object, with color and alpha as
    independently updatable state (unlike `DirectLabelColormap`, which
    conflates them in one `color_dict`).

    `to_direct_colormap()` builds a fresh napari colormap on every call via
    `construct_direct_colormap`, which skips pydantic's per-color
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
        # Nodes colored before `Tracks` knows about them (see add_node), which
        # set_tracks has to leave alone.
        self._pending: set[int] = set()
        # (sorted node ids, matching RGB rows) for vectorized lookup
        self._lookup: tuple[np.ndarray, np.ndarray] | None = None

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

    def set_feature(
        self, feature_key: str | None, color_source: ColorSource | None = None
    ) -> None:
        """Color by `feature_key`, rendered with `color_source`."""
        self._feature_key = feature_key
        self._color_source = color_source or make_color_source(
            self._tracks, feature_key
        )
        self.set_tracks(self._tracks)

    @property
    def colors_by_track_id(self) -> bool:
        """Whether the feature being colored by is the track id."""
        return (
            self._tracks is None
            or self._feature_key is None
            or self._feature_key == self._tracks.features.tracklet_key
        )

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

        Nodes added by `add_node` keep the color it gave them until `Tracks`
        knows about them.
        """
        self._tracks = tracks
        nodes = tracks.graph_solution.node_ids() if tracks is not None else []
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

        if tracks is None:
            self._pending.clear()
        elif self._pending:
            # a pending node stops being pending as soon as it is in the graph,
            # where its own feature value gives it a color
            self._pending -= colors.keys()
            for node in self._pending:
                colors[node] = self._node_colors[node]

        self._alpha = {
            node: self._alpha.get(node, self._default_alpha) for node in colors
        }
        self._node_colors = colors
        self._lookup = None

    def add_node(self, node: int, track_id: int) -> None:
        """Color a node not yet known to `self._tracks`, so that it can be
        painted with (`TrackLabels._new_label`). Alpha defaults to
        `default_alpha`, and `set_tracks` leaves the color alone until the node
        reaches the graph, where its own feature value takes over.

        The node is given the color it will keep wherever the feature's value
        for it can be worked out in advance, so that what you paint with is
        what you end up with. A grey color is used when the color cannot be known in
        advance.
        """
        tracks = self._tracks
        feature = tracks.features.get(self._feature_key) if tracks is not None else None
        if self.colors_by_track_id:
            # the one value a node is given up front (TracksViewer.set_new_track_id)
            value = track_id
        elif tracks is not None and self._feature_key == tracks.features.lineage_key:
            # UserAddNode takes the lineage from another node of the same track
            # and only mints a new one when the track has none yet, so both
            # cases are known before the node exists
            in_track = tracks.track_id_to_node.get(track_id)
            value = (
                tracks.get_lineage_id(next(iter(in_track)))
                if in_track
                else tracks.get_next_lineage_id()
            )
        elif feature is not None and feature["value_type"] == "bool":
            # a node that has just been drawn has not been put in any group
            value = False
        else:
            value = None

        rgba = GREY if value is None else self.color_source.map(value)
        self._node_colors[node] = np.asarray(rgba[:3], dtype=float).copy()
        self._alpha[node] = self._default_alpha
        self._pending.add(node)
        self._lookup = None

    def remove_node(self, node: int) -> None:
        self._node_colors.pop(node, None)
        self._alpha.pop(node, None)
        self._pending.discard(node)
        self._lookup = None

    def set_alpha(self, nodes, value: float) -> None:
        """Set alpha for many nodes at once - the hot path, fired on every
        selection/hover change. Only ever touches alpha, never node colors.
        """
        for node in nodes:
            if node is not None and node in self._alpha:
                self._alpha[node] = value

    def get_alpha(self, node: int, default: float = 0.0) -> float:
        """A node's display alpha, only needed by labels layers and included via
        to_direct_colormap.
        """
        return self._alpha.get(node, default)

    def get_color(self, node: int) -> np.ndarray:
        """A node's own RGBA color, fully opaque; transparent black if this
        colormap doesn't know the node. For its display alpha see `get_alpha`.
        """
        if node not in self._node_colors:
            return np.zeros(4)
        return np.append(self._node_colors[node], 1.0)

    def get_colors(self, nodes: np.ndarray) -> np.ndarray:
        """Vectorized `get_color`: each node's own RGBA color, in order, fully
        opaque; transparent black for nodes this colormap doesn't know. For
        napari-independent consumers (the points and tracks layers, the tree,
        the table, an export) that need many colors at once without going
        through `to_direct_colormap()`.

        Alpha is left out, since only the labels layers need it, and they get it via
        to_direct_colormap.

        Vectorized because the points layer, the tree and the tracks layer
        each ask for every node on every refresh: on a 37k-node graph this is
        ~2ms against ~50ms for a `get_color` call per node, plus ~13ms on the
        first call after the node set changes, which rebuilds `_color_lookup`.
        """
        node_ids, rgb = self._color_lookup()
        nodes = np.asarray(nodes, dtype=np.int64)
        colors = np.zeros((len(nodes), 4))
        if len(node_ids) == 0 or len(nodes) == 0:
            return colors

        # searchsorted + an equality check, rather than a dict lookup per node
        index = np.clip(np.searchsorted(node_ids, nodes), 0, len(node_ids) - 1)
        known = node_ids[index] == nodes
        colors[known, :3] = rgb[index[known]]
        colors[known, 3] = 1.0
        return colors

    def _color_lookup(self) -> tuple[np.ndarray, np.ndarray]:
        """`_node_colors` as (sorted node ids, matching RGB rows), for
        `get_colors`. Built on demand and kept until the node set changes.
        """
        if self._lookup is None:
            node_ids = np.fromiter(
                self._node_colors, dtype=np.int64, count=len(self._node_colors)
            )
            rgb = (
                np.stack(list(self._node_colors.values()))
                if self._node_colors
                else np.zeros((0, 3))
            )
            order = np.argsort(node_ids)
            self._lookup = (node_ids[order], rgb[order])
        return self._lookup

    @property
    def nodes(self):
        return self._node_colors.keys()

    def to_direct_colormap(self) -> DirectLabelColormap:
        """Build a fresh napari `DirectLabelColormap` for the current
        color/alpha state.

        Skips pydantic's per-color validation - see
        `construct_direct_colormap`.
        """
        return construct_direct_colormap(
            {
                **{node: self._colored(node) for node in self._node_colors},
                None: np.array([0, 0, 0, 0], dtype=float),
            }
        )

    def _colored(self, node: int) -> np.ndarray:
        """RGB from `_node_colors` plus current alpha, as one RGBA array."""
        return np.append(
            self._node_colors[node], self._alpha.get(node, self._default_alpha)
        )
