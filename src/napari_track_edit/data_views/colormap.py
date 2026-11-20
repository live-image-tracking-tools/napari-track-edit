from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
from napari.utils import DirectLabelColormap
from napari.utils.colormaps import ensure_colormap, label_colormap
from tracksdata.constants import DEFAULT_ATTR_KEYS

from napari_track_edit.data_views.palettes import (
    CATEGORICAL_PALETTES,
    GRADIENTS,
    ID_PALETTES,
    RANDOM_IDS,
    palette_colors,
    palette_for,
)

if TYPE_CHECKING:
    from funtracks.data_model import Tracks

# What a node is painted with while its own color is not known yet - see add_node.
PINK = (0.75, 0.08, 0.4)
GREY = (0.7, 0.7, 0.7)  # What every node is colored when no feature is selected at all.
# The edge "feature" that draws every edge in its child node's color (see
# EdgeColormap). Not None, which means one flat color, as it does for nodes.
SAME_AS_NODES = "__same_as_nodes__"


@dataclass(frozen=True)
class FeatureComponent:
    """One value of a multi-valued node feature, as a color feature key.

    Used for the axes of a stacked position feature (e.g. `pos` = (z, y, x)),
    so that each axis can be picked to color by on its own. Positions stored
    as one column per axis are plain keys already.

    A frozen dataclass rather than a tuple: Qt hands a Python tuple stored as
    item data back as a list, which no longer compares equal.
    """

    key: str
    index: int


def _base_key(feature_key):
    """The feature a color feature key reads: itself, or a component's feature."""
    return feature_key.key if isinstance(feature_key, FeatureComponent) else feature_key


def node_feature_values(tracks: Tracks, nodes, feature_key) -> list:
    """Every node's value of `feature_key`, a plain key or a `FeatureComponent`."""
    if isinstance(feature_key, FeatureComponent):
        values = tracks.get_nodes_attr(nodes, feature_key.key)
        return [None if v is None else v[feature_key.index] for v in values]
    return tracks.get_nodes_attr(nodes, feature_key)


def colormap_choices(color_source) -> tuple[str, ...]:
    """The named colormaps `color_source` can switch between; empty for sources
    without any (ids, groups, one flat color)."""
    return tuple(getattr(color_source, "choices", ()))


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
    without touching `NodeColormap` or its consumers.

    `shuffle()` re-draws whatever colors the source uses, so napari's "shuffle
    colors" button does the right thing whichever source is installed.

    Sources with named colormaps to choose from (`GradientColorSource`,
    `PaletteColorSource`) also have `choices` and a settable `choice`, which
    the colormap picker next to the "Color ... by" dropdowns shows (drawn with
    their `preview(name)` colors); see `colormap_choices`.
    """

    def map(self, values: np.ndarray) -> np.ndarray: ...

    def shuffle(self) -> None: ...


class CategoricalColorSource:
    """Default `ColorSource`: cyclic color per unique id, 0 -> transparent.

    Not track-specific - works for any categorical id (cell type, lineage id).

    `choice` "random" (the default) is napari's random label colormap; the
    other ID_PALETTES are generated palettes of ID_CYCLE colors that ids
    cycle through.
    """

    choices = ID_PALETTES
    ID_CYCLE = 49  # colors an id palette cycles through

    def __init__(self, num_colors: int = ID_CYCLE, seed: float = 0.5):
        self._cyclic_colormap = label_colormap(
            num_colors, seed=seed, background_value=0
        )
        self._choice = RANDOM_IDS
        self._order = np.arange(self.ID_CYCLE)

    @property
    def choice(self) -> str:
        return self._choice

    @choice.setter
    def choice(self, name: str) -> None:
        self._choice = name
        self._order = np.arange(self.ID_CYCLE)

    def preview(self, name: str) -> np.ndarray:
        """The colors to show for `name` in the colormap picker."""
        if name == RANDOM_IDS:
            return self._cyclic_colormap.map(np.arange(1, 25))[:, :3]
        return palette_colors(name, self.ID_CYCLE)[:24]

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
        if self._choice == RANDOM_IDS:
            return self._cyclic_colormap.map(arr)
        scalar = np.ndim(arr) == 0
        ids = np.atleast_1d(arr).astype(np.int64)
        palette = palette_colors(self._choice, self.ID_CYCLE)[self._order]
        colors = np.ones((len(ids), 4))
        colors[:, :3] = palette[(ids - 1) % self.ID_CYCLE]
        colors[ids == 0] = 0.0  # the background stays transparent
        return colors[0] if scalar else colors

    def shuffle(self, num_colors: int | None = None, seed: float | None = None) -> None:
        """New colors (see `TrackLabels.new_colormap`): a new random cycle for
        "random", the same palette in a new order for the others. With no
        arguments a random cycle is drawn, matching the argument-less
        `ColorSource.shuffle` that the "shuffle colors" button calls."""
        if self._choice != RANDOM_IDS:
            self._order = np.random.permutation(self.ID_CYCLE)
            return
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
        """Nothing to shuffle: "None" means one flat grey, so it stays grey."""


class GradientColorSource:
    """A continuous colormap (viridis by default) for numeric features.

    Values are scaled linearly between `limits` (low, high) and clipped to
    them. Missing values (None, NaN) are painted GREY, so they read as "no
    value" rather than as the low end of the scale.

    With `autoscale` on, `NodeColormap.set_tracks` calls `fit` with every
    node's value each time it recolors, so the limits follow the data through
    edits. Passing `limits` turns autoscale off.
    """

    def __init__(
        self,
        colormap: str = GRADIENTS[0],
        limits: tuple[float, float] | None = None,
    ):
        self.colormap = ensure_colormap(colormap)
        self.autoscale = limits is None
        self.limits: tuple[float, float] = (0.0, 1.0) if limits is None else limits

    def fit(self, values: np.ndarray) -> None:
        """Set `limits` to the range of the finite `values`, if autoscaling."""
        if not self.autoscale:
            return
        arr = _as_float(values)
        finite = arr[np.isfinite(arr)]
        if finite.size > 0:
            self.limits = (float(finite.min()), float(finite.max()))

    def map(self, values: np.ndarray) -> np.ndarray:
        scalar = np.ndim(values) == 0
        arr = np.atleast_1d(_as_float(values))
        low, high = self.limits
        span = high - low
        # a feature with one value everywhere lands in the middle of the scale
        scaled = (arr - low) / span if span > 0 else np.full(arr.shape, 0.5)
        missing = ~np.isfinite(scaled)
        colors = np.empty((len(arr), 4))
        colors[~missing] = self.colormap.map(np.clip(scaled[~missing], 0.0, 1.0))
        colors[missing] = (*GREY, 1.0)
        return colors[0] if scalar else colors

    choices = GRADIENTS

    @property
    def choice(self) -> str:
        return self.colormap.name

    @choice.setter
    def choice(self, name: str) -> None:
        self.colormap = ensure_colormap(name)

    @staticmethod
    def preview(name: str) -> np.ndarray:
        """The (N, 3) colors to show for colormap `name` in the colormap picker."""
        return ensure_colormap(name).map(np.linspace(0.0, 1.0, 64))[:, :3]

    def shuffle(self) -> None:
        """Switch to the next colormap in `GRADIENTS`."""
        names = GRADIENTS
        current = self.colormap.name
        index = names.index(current) + 1 if current in names else 0
        self.colormap = ensure_colormap(names[index % len(names)])


# An int feature with at most this many distinct values is colored as
# categories rather than as a gradient (see make_node_color_source).
MAX_CATEGORIES = 20


class PaletteColorSource:
    """A fixed palette for categorical features with few values (small int
    codes, text), one palette color per distinct value.

    Each value keeps its color: `fit` hands out palette slots to values it has
    not seen before, in sorted order, and never takes one back, so editing the
    data (or a new value appearing) does not recolor the existing categories.
    Values beyond the palette's length reuse its colors from the start.
    Missing values (None) are GREY.

    `shuffle` keeps the palette and deals its colors out to the slots in a new
    random order; picking another palette (`choice`) starts it in order again.
    """

    def __init__(self, palette: str = CATEGORICAL_PALETTES[0], n_colors: int = 20):
        self._slots: dict = {}
        # how many colors a generated palette is made with: the number of
        # categories when the feature was picked. Fixed from then on, so that
        # a new category does not recolor the others; it reuses a color.
        self._n_colors = max(int(n_colors), 1)
        self.choice = palette

    @classmethod
    def for_values(cls, values) -> PaletteColorSource:
        """A source whose palette is big enough for `values`' categories, with
        their slots already handed out."""
        n = len(_categories(values))
        source = cls(palette_for(n), n_colors=n)
        source.fit(values)
        return source

    def fit(self, values) -> None:
        """Give every value not seen before the next free slot."""
        new = [v for v in _categories(values) if v not in self._slots]
        for value in new:
            self._slots[value] = len(self._slots)

    def map(self, values) -> np.ndarray:
        scalar = np.ndim(values) == 0
        arr = np.atleast_1d(np.asarray(values, dtype=object))
        colors = np.empty((len(arr), 4))
        colors[:] = (*GREY, 1.0)
        palette = palette_colors(self.palette, self._n_colors)[self._order]
        # a dict lookup per value rather than np.unique, which sorts and so
        # raises on values that do not compare (text next to a NaN, mixed
        # types). Missing and unseen values get -1 and stay GREY.
        slots = self._slots
        index = np.fromiter(
            (-1 if _is_missing(v) else slots.get(v, -1) for v in arr),
            dtype=np.int64,
            count=len(arr),
        )
        known = index >= 0
        colors[known, :3] = palette[index[known] % len(palette)]
        return colors[0] if scalar else colors

    choices = CATEGORICAL_PALETTES

    @property
    def choice(self) -> str:
        return self.palette

    @choice.setter
    def choice(self, name: str) -> None:
        self.palette = name
        # which palette color each slot gets; in order until shuffled
        self._order = np.arange(len(palette_colors(name, self._n_colors)))

    def preview(self, name: str) -> np.ndarray:
        """The (N, 3) colors to show for palette `name` in the colormap picker."""
        return palette_colors(name, self._n_colors)

    def shuffle(self) -> None:
        """Deal the same palette's colors out to the categories in a new order.
        Every value keeps its slot, so categories still never share a color
        unless there are more of them than the palette has colors."""
        order = self._order
        while len(order) > 1 and np.array_equal(order, self._order):
            order = np.random.permutation(len(self._order))
        self._order = order


def _is_missing(value) -> bool:
    """None, or a float NaN: what an empty cell of an imported text column
    holds."""
    return value is None or (
        isinstance(value, float | np.floating) and bool(np.isnan(value))
    )


def _categories(values) -> list:
    """The distinct non-missing values, sorted (as text if they do not sort)."""
    distinct = {
        v for v in np.asarray(values, dtype=object).ravel() if not _is_missing(v)
    }
    try:
        return sorted(distinct)
    except TypeError:
        return sorted(distinct, key=str)


def _as_float(values) -> np.ndarray:
    """`values` as a float array, with None (a missing value) as NaN."""
    arr = np.asarray(values)
    if arr.dtype.kind == "O":
        arr = np.array([np.nan if v is None else v for v in arr.ravel()]).reshape(
            arr.shape
        )
    return arr.astype(float)


def _is_value_feature(tracks: Tracks, feature_key) -> bool:
    """Whether a node feature holds one number or one piece of text per node,
    colored by its values: as categories or as a gradient (see
    `make_node_color_source`).

    Tracklet and lineage ids are left out: they have colors of their own
    (`CategoricalColorSource`), and so do groups (bool features).
    """
    if isinstance(feature_key, FeatureComponent):
        return True  # only position axes are offered as components
    features = tracks.features
    feature = features.get(feature_key)
    return (
        feature is not None
        and feature["value_type"] in ("float", "int", "str")
        and feature.get("num_values", 1) == 1
        and feature_key not in (features.tracklet_key, features.lineage_key)
    )


def _value_color_source(feature: dict | None, read_values, is_time: bool):
    """Categories or a gradient for a feature colored by its values.

    Text is always categories; floats (and position axes, which have no
    feature dict of their own here) are always a gradient. An int feature is
    categories when it has at most MAX_CATEGORIES distinct values, otherwise a
    gradient, except time, which is a gradient however few time points there
    are. Deciding this reads the values once, here, when the feature is picked:
    the choice does not flip back and forth as edits add or remove values.
    """
    value_type = None if feature is None else feature["value_type"]
    if value_type == "str":
        return PaletteColorSource.for_values(read_values())
    if value_type == "int" and not is_time:
        values = read_values()
        if len(_categories(values)) <= MAX_CATEGORIES:
            return PaletteColorSource.for_values(values)
    return GradientColorSource()


def make_node_color_source(
    tracks: Tracks | None, feature_key: str | None
) -> ColorSource:
    """The `ColorSource` that can render a feature's values.

    A source and a feature have to match: no feature at all means one flat
    color, a group's True/False two colors, tracklet and lineage ids random
    colors via CategoricalColorSource, and every other feature categories or a
    gradient, decided from its values (see `_value_color_source`).
    """
    if feature_key is None:
        return ConstantColorSource()
    feature = tracks.features.get(feature_key) if tracks is not None else None
    if feature is not None and feature["value_type"] == "bool":
        return BinaryColorSource()
    if tracks is not None and _is_value_feature(tracks, feature_key):
        return _value_color_source(
            feature,
            lambda: node_feature_values(
                tracks, tracks.graph_solution.node_ids(), feature_key
            ),
            is_time=feature_key == tracks.features.time_key,
        )
    return CategoricalColorSource()


def node_color_feature_available(
    tracks: Tracks | None, feature_key: str | None
) -> bool:
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
    key = _base_key(feature_key)
    return key in tracks.features and key in tracks.graph_solution.node_attr_keys()


def node_categorical_feature_keys(tracks: Tracks | None) -> list[str]:
    """The node features that can currently drive coloring: tracklet id, lineage id, and
    every group (solution is excluded for now).

    Features with no column on the graph are left out - see
    `node_color_feature_available`. The column set is fetched once here rather than
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


def node_value_feature_keys(tracks: Tracks | None) -> list:
    """The node features colored by their values: numbers, text and position
    axes, as categories or a gradient (see `make_node_color_source`).

    Same rules as `node_categorical_feature_keys` for features without a column.
    """
    if tracks is None:
        return []
    attr_keys = set(tracks.graph_solution.node_attr_keys())
    position_key = tracks.features.position_key
    keys: list = []
    for key, feature in tracks.features.node_features.items():
        if key not in attr_keys:
            continue
        if key == position_key and feature.get("num_values", 1) > 1:
            # a stacked position: one entry per axis. Positions stored as one
            # column per axis are single-valued and picked up below.
            keys += [FeatureComponent(key, i) for i in range(feature["num_values"])]
        elif _is_value_feature(tracks, key):
            keys.append(key)
    return keys


def node_color_feature_keys(tracks: Tracks | None) -> list[str]:
    """Every node feature that can currently drive node coloring: ids and
    groups, then the features colored by their values."""
    return [
        *node_categorical_feature_keys(tracks),
        *node_value_feature_keys(tracks),
    ]


def edge_color_feature_keys(tracks: Tracks | None) -> list[str]:
    """The edge features that can currently drive edge coloring: bool features
    (two colors), and numbers and text (categories or a gradient, as for
    nodes), one value per edge, with a column on the graph. `solution` is left
    out, as for nodes.
    """
    if tracks is None:
        return []
    attr_keys = set(tracks.graph_solution.edge_attr_keys())
    return [
        key
        for key, feature in tracks.features.edge_features.items()
        if feature["value_type"] in ("bool", "float", "int", "str")
        and feature.get("num_values", 1) == 1
        and key != "solution"
        and key in attr_keys
    ]


def edge_color_feature_available(
    tracks: Tracks | None, feature_key: str | None
) -> bool:
    """Whether `feature_key`'s edge values can be read off `tracks`. None (one
    flat color) and SAME_AS_NODES read nothing, so they always can. See
    `node_color_feature_available`."""
    if feature_key is None or feature_key == SAME_AS_NODES:
        return True
    if tracks is None:
        return False
    return (
        feature_key in tracks.features
        and feature_key in tracks.graph_solution.edge_attr_keys()
    )


def make_edge_color_source(
    tracks: Tracks | None, feature_key: str | None
) -> ColorSource:
    """One flat color for None, two colors for a bool edge feature, and
    categories or a gradient for numbers and text, decided from the values as
    for nodes (see `_value_color_source`)."""
    if feature_key is None:
        return ConstantColorSource()
    feature = tracks.features.get(feature_key) if tracks is not None else None
    if feature is not None and feature["value_type"] == "bool":
        return BinaryColorSource()
    return _value_color_source(
        feature,
        lambda: tracks.graph_solution.edge_attrs(attr_keys=[feature_key])[
            feature_key
        ].to_list(),
        is_time=False,
    )


def feature_display_name(tracks: Tracks | None, feature_key: str | None) -> str:
    """The label to show for a feature in the UI."""
    if feature_key is None:
        return "None"
    if isinstance(feature_key, FeatureComponent):
        feature = tracks.features.get(feature_key.key) if tracks is not None else None
        names = (feature or {}).get("value_names")
        if names is not None and feature_key.index < len(names):
            return str(names[feature_key.index])
        return f"{feature_key.key}[{feature_key.index}]"
    feature = tracks.features.get(feature_key) if tracks is not None else None
    return feature_key if feature is None else feature.get("display_name", feature_key)


class NodeColormap:
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
        self._color_source = color_source or make_node_color_source(
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
        return node_feature_values(tracks, nodes, key)

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
        fit = getattr(self.color_source, "fit", None)
        if fit is not None and len(values) > 0:
            fit(values)
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


class EdgeColormap:
    """Edge -> display color, by an edge feature, for the lineage view.

    The tree draws a node's incoming edge under it, and in a lineage every node
    has at most one parent, so colors are looked up by the edge's target node.

    `feature_key` SAME_AS_NODES (the default) means edges are not colored on
    their own at all (`active` is False) and the tree draws them like their
    nodes; None means one flat color, as for nodes. Like `NodeColormap`,
    colors are computed once per `set_tracks` and only read afterwards; the
    gradient limits are refit there too.
    """

    def __init__(self):
        self._feature_key: str | None = SAME_AS_NODES
        self._color_source: ColorSource | None = None
        self._tracks: Tracks | None = None
        # (sorted target node ids, matching RGB rows)
        self._lookup: tuple[np.ndarray, np.ndarray] = (
            np.empty(0, dtype=np.int64),
            np.zeros((0, 3)),
        )

    @property
    def feature_key(self) -> str | None:
        return self._feature_key

    @property
    def color_source(self) -> ColorSource | None:
        return self._color_source

    @property
    def active(self) -> bool:
        return self._feature_key != SAME_AS_NODES

    def set_feature(
        self, feature_key: str | None, color_source: ColorSource | None = None
    ) -> None:
        """Color edges by `feature_key` (see the class docstring for None and
        SAME_AS_NODES)."""
        self._feature_key = feature_key
        self._color_source = (
            None
            if feature_key == SAME_AS_NODES
            else color_source or make_edge_color_source(self._tracks, feature_key)
        )
        self.set_tracks(self._tracks)

    def set_tracks(self, tracks: Tracks | None) -> None:
        """Read every edge's value of the feature and recompute the colors.

        TODO: TracksViewer._refresh calls this on every edit, so while edges
        are colored by a feature every edit re-reads all edges, even with no
        lineage view open to show them. Skip it while no tree widget is
        present (and recompute when one opens) if this shows up on large
        graphs.
        """
        self._tracks = tracks
        targets = np.empty(0, dtype=np.int64)
        rgb = np.zeros((0, 3))
        if tracks is not None and self.active:
            target_key = DEFAULT_ATTR_KEYS.EDGE_TARGET
            key = self._feature_key
            df = tracks.graph_solution.edge_attrs(
                attr_keys=[target_key] if key is None else [target_key, key]
            )
            if len(df) > 0:
                values = (
                    np.zeros(len(df))
                    if key is None
                    else np.asarray(df[key].to_list(), dtype=object)
                )
                fit = getattr(self._color_source, "fit", None)
                if fit is not None:
                    fit(values)
                targets = df[target_key].to_numpy().astype(np.int64)
                rgb = np.asarray(self._color_source.map(values))[:, :3]
                order = np.argsort(targets)
                targets, rgb = targets[order], rgb[order]
        self._lookup = (targets, rgb)

    def get_colors(self, target_nodes) -> np.ndarray:
        """RGBA of the edge into each of `target_nodes`, fully opaque;
        transparent black where there is no such edge."""
        targets, rgb = self._lookup
        nodes = np.asarray(target_nodes, dtype=np.int64)
        colors = np.zeros((len(nodes), 4))
        if len(targets) == 0 or len(nodes) == 0:
            return colors
        index = np.clip(np.searchsorted(targets, nodes), 0, len(targets) - 1)
        known = targets[index] == nodes
        colors[known, :3] = rgb[index[known]]
        colors[known, 3] = 1.0
        return colors
