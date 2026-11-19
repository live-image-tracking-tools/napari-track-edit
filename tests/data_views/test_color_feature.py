"""Changing the feature the colormap colors by, and keeping every view in sync.

The colormap object is shared by all the views, but each of them caches colors
of its own, so these tests mostly check that a feature change actually reaches
the labels, points, tracks, tree and table - not just the colormap.
"""

import numpy as np
import pytest
from funtracks.user_actions import UserUpdateSegmentation

from napari_track_edit.data_views.colormap import (
    GREY,
    PINK,
    SAME_AS_NODES,
    BinaryColorSource,
    CategoricalColorSource,
    GradientColorSource,
    node_categorical_feature_keys,
)
from napari_track_edit.data_views.views.table.custom_table_widget import (
    ColoredTableWidget,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer

# the 3D fixture's three nodes: 1 -> {2, 3}, each with a track id of its own but
# all in the one lineage, so coloring by lineage id gives them one shared color
# where coloring by track id gives them three different ones
NODES = (1, 2, 3)


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    yield
    viewer.layers.clear()


@pytest.fixture
def tracks_viewer(viewer, solution_tracks_3d):
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d, name="test")
    tracks_viewer.update_track_df(initialization=True)
    # the tree's dataframe is only kept up to date while a tree or table widget
    # is around to want it (see TracksViewer.update_track_df); set after the
    # initial build, which the same flag would otherwise skip
    tracks_viewer.tree_widget_present = True
    return tracks_viewer


def _view_colors(tracks_viewer):
    """The color every view currently shows for each node, as one dict per view.

    RGB only: alpha is display state (selection/lineage dimming), which is not
    what these tests are about.
    """

    layers = tracks_viewer.tracking_layers
    nodes = list(tracks_viewer.tracks.graph_solution.node_ids())
    seg = layers.seg_layer.colormap.color_dict
    points = layers.points_layer
    tracks_layer = layers.tracks_layer
    df = tracks_viewer.track_df

    return {
        "labels": {node: np.asarray(seg[node])[:3] for node in nodes},
        "points": {
            node: points.face_color[points.node_index_dict[node]][:3] for node in nodes
        },
        # the tracks layer holds one vertex per node, ordered by (track id, time)
        "tracks": {
            int(node_id): tracks_layer.track_colors[row][:3]
            for row, node_id in enumerate(tracks_layer.properties["node_id"])
            if int(node_id) in nodes
        },
        "tree": {
            int(row.node_id): np.asarray(row.color)[:3] / 255 for row in df.itertuples()
        },
        # the tracks layer keeps track ids too, for update_track_visibility
        "track_ids": tracks_layer.properties["track_id"],
    }


VIEWS = ("labels", "points", "tracks", "tree")


def test_every_view_starts_on_track_id_colors(tracks_viewer):
    colors = _view_colors(tracks_viewer)

    for view in VIEWS:
        # three track ids, so three different colors
        assert not np.allclose(colors[view][1], colors[view][2]), view
        assert not np.allclose(colors[view][2], colors[view][3]), view
        # and every view agrees with the labels layer
        for node in NODES:
            assert np.allclose(colors[view][node], colors["labels"][node]), (view, node)


def test_a_new_feature_recolors_every_view(tracks_viewer):
    before = _view_colors(tracks_viewer)

    tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)

    after = _view_colors(tracks_viewer)
    for view in VIEWS:
        # the three nodes share a lineage, so now they share a color...
        assert np.allclose(after[view][1], after[view][2]), view
        assert np.allclose(after[view][2], after[view][3]), view
        # ...and it is not the one they had before
        assert not np.allclose(after[view][2], before[view][2]), view


def test_switching_back_restores_track_id_colors(tracks_viewer):
    before = _view_colors(tracks_viewer)

    tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)
    tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.tracklet_key)

    after = _view_colors(tracks_viewer)
    for view in VIEWS:
        for node in NODES:
            assert np.allclose(after[view][node], before[view][node]), (view, node)


def test_tracks_layer_keeps_its_track_ids(tracks_viewer):
    # coloring the tracks layer per node must not cost it the track_id property
    # that update_track_visibility filters on
    before = _view_colors(tracks_viewer)["track_ids"]

    tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)

    assert np.array_equal(_view_colors(tracks_viewer)["track_ids"], before)


def test_table_follows_the_feature(viewer, tracks_viewer, qtbot):
    table = ColoredTableWidget(viewer)
    qtbot.addWidget(table)
    before = table._model._bg[table._id_to_row[2]].name()

    tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)

    rows = [table._id_to_row[node] for node in NODES]
    colors = [table._model._bg[row].name() for row in rows]
    assert len(set(colors)) == 1  # one lineage, one color
    assert colors[0] != before


def test_new_colormap_recolors_every_view(tracks_viewer):
    # the same sync problem from the other direction: the shuffle happens on the
    # shared color source, and every view has to pick the new colors up
    before = _view_colors(tracks_viewer)

    tracks_viewer.tracking_layers.seg_layer.new_colormap()

    after = _view_colors(tracks_viewer)
    for view in VIEWS:
        for node in NODES:
            assert not np.allclose(after[view][node], before[view][node]), (view, node)


def test_tracks_layer_survives_a_napari_recolor(tracks_viewer):
    """Changing the colormap in the Tracks layer controls makes napari recolor
    the vertices itself. It goes through `colormaps_dict`, so the node colors
    have to come back out of it unchanged rather than as a gradient."""

    before = _view_colors(tracks_viewer)["tracks"]

    tracks_viewer.tracking_layers.tracks_layer.colormap = "viridis"

    after = _view_colors(tracks_viewer)["tracks"]
    for node in NODES:
        assert np.allclose(after[node], before[node]), node


def _paint_new_label(tracks_viewer, new_track=True):
    """Press M and paint with the label it hands out, as TrackLabels does.

    Returns the colors to compare: what the label was painted with, what the
    swatch showed, and what the node ended up with once the edit committed.
    """
    seg = tracks_viewer.tracking_layers.seg_layer
    seg.new_label()
    node = int(seg.selected_label)
    track = tracks_viewer.selected_track
    pending = np.asarray(seg.colormap.color_dict[node])[:3].copy()
    swatch = np.asarray(tracks_viewer.track_id_color).copy()

    # one index array per dimension (t, [z], y, x), away from any existing node
    t = int(tracks_viewer.tracks.get_time(1))
    spatial_ndim = tracks_viewer.tracks.ndim - 1
    px = (np.full(3, t), *(np.array([5, 6, 7]) for _ in range(spatial_ndim)))
    UserUpdateSegmentation(
        tracks=tracks_viewer.tracks,
        new_value=node,
        updated_pixels=[(px, 0)],
        current_track_id=track,
        force=True,
    )
    committed = np.asarray(seg.colormap.color_dict[node])[:3]
    return track, pending, swatch, committed


class TestNewLabelColor:
    def test_track_id_color_is_kept_through_the_paint(self, tracks_viewer):
        # colouring by track id, the new node's colour is known up front, so
        # what you paint with is what you end up with
        track, pending, swatch, committed = _paint_new_label(tracks_viewer)

        expected = tracks_viewer.node_colormap.map(np.asarray([track]))[0][:3]
        assert np.allclose(pending, expected)
        assert np.allclose(swatch[:3], expected)
        assert swatch[3] == 1
        assert np.allclose(committed, expected)

    def test_lineage_color_is_kept_through_the_paint(self, tracks_viewer):
        # a new track's lineage id is worked out the same way UserAddNode will,
        # so the colour painted with is the one the node commits to
        tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)

        _track, pending, swatch, committed = _paint_new_label(tracks_viewer)

        assert not np.allclose(pending, GREY)
        assert np.allclose(pending, committed)
        # the swatch names a track id, which has no colour of its own here
        assert np.array_equal(swatch, [0, 0, 0, 0])

    def test_lineage_color_of_an_existing_track_is_kept_through_the_paint(
        self, tracks_viewer
    ):
        # continuing an existing track: the node inherits that track's lineage,
        # not a fresh one
        tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)
        seg = tracks_viewer.tracking_layers.seg_layer
        tracks_viewer.selected_nodes.add(1)
        seg._ensure_valid_label()

        _track, pending, swatch, committed = _paint_new_label(tracks_viewer)

        assert np.allclose(pending, committed)

    def test_swatch_has_no_color_while_coloring_by_another_feature(self, tracks_viewer):
        tracks_viewer.set_node_color_feature(tracks_viewer.tracks.features.lineage_key)

        tracks_viewer.set_track_id_color(1)

        assert np.array_equal(tracks_viewer.track_id_color, [0, 0, 0, 0])


GROUP = "my_group"
IN_GROUP = (1, 2)
OUT_OF_GROUP = (3,)


@pytest.fixture
def grouped(tracks_viewer):
    """The same tracks with a group feature on them, nodes 1 and 2 in it."""
    tracks = tracks_viewer.tracks
    tracks.add_feature(
        GROUP,
        {
            "feature_type": "node",
            "value_type": "bool",
            "num_values": 1,
            "display_name": GROUP,
            "default_value": False,
        },
    )
    for node in tracks.graph_solution.node_ids():
        tracks.graph_solution.nodes[node][GROUP] = node in IN_GROUP
    return tracks_viewer


class TestGroupColoring:
    def test_does_not_crash(self, grouped):
        # napari's cyclic colormap rejects a bool dtype outright, so this used
        # to raise ValueError("Invalid integer data type 'b'")
        grouped.set_node_color_feature(GROUP)

        assert isinstance(grouped.node_colormap.color_source, BinaryColorSource)

    def test_recolors_every_view(self, grouped):
        before = _view_colors(grouped)

        grouped.set_node_color_feature(GROUP)

        after = _view_colors(grouped)
        for view in VIEWS:
            for node in IN_GROUP:
                assert np.allclose(after[view][node], PINK), (view, node)
            for node in OUT_OF_GROUP:
                assert np.allclose(after[view][node], GREY), (view, node)
                assert not np.allclose(after[view][node], before[view][node]), (
                    view,
                    node,
                )

    def test_new_colormap_picks_two_new_colors(self, grouped):
        grouped.set_node_color_feature(GROUP)
        before = _view_colors(grouped)

        grouped.tracking_layers.seg_layer.new_colormap()

        after = _view_colors(grouped)
        for view in VIEWS:
            # still two colors, but two different ones, in every view
            assert np.allclose(after[view][1], after[view][2]), view
            assert not np.allclose(after[view][1], after[view][3]), view
            assert not np.allclose(after[view][1], before[view][1]), view

    def test_a_new_label_is_painted_as_not_in_the_group(self, grouped):
        grouped.set_node_color_feature(GROUP)

        _track, pending, swatch, committed = _paint_new_label(grouped)

        assert np.allclose(pending, GREY)
        assert np.allclose(pending, committed)
        assert np.array_equal(swatch, [0, 0, 0, 0])

    def test_deleting_the_feature_falls_back_to_track_ids(self, grouped):
        grouped.set_node_color_feature(GROUP)

        del grouped.tracks.features[GROUP]
        grouped._refresh()  # must not raise

        assert grouped.node_color_feature_key == grouped.tracks.features.tracklet_key
        assert isinstance(grouped.node_colormap.color_source, CategoricalColorSource)

    def test_new_tracks_reset_to_track_ids(self, grouped, solution_tracks_2d):
        grouped.set_node_color_feature(GROUP)

        # these tracks have no such group; colouring by it would raise on them
        grouped.update_tracks(tracks=solution_tracks_2d, name="other")

        assert (
            grouped.node_color_feature_key == solution_tracks_2d.features.tracklet_key
        )
        assert isinstance(grouped.node_colormap.color_source, CategoricalColorSource)


def test_switching_to_tracks_that_name_their_track_id_differently(tracks_viewer):
    """`update_tracks` forgets the outgoing tracks before re-deriving colors
    for the incoming ones. Without that, setting the incoming track-id feature
    reads it off the outgoing tracks, which do not have it."""

    from funtracks.data_model import SolutionTracks
    from funtracks.utils.tracksdata_utils import create_empty_graphview_graph

    graph = create_empty_graphview_graph(node_attributes=["pos", "track_id"], ndim=3)
    graph.bulk_add_nodes(
        nodes=[
            {"t": 0, "pos": [5.0, 5.0], "track_id": 1, "solution": True},
            {"t": 1, "pos": [6.0, 6.0], "track_id": 1, "solution": True},
        ],
        indices=[1, 2],
    )
    graph.bulk_add_edges([{"source_id": 1, "target_id": 2, "solution": True}])
    graph._update_metadata(shape=(3, 10, 10))
    incoming = SolutionTracks(
        graph=graph, ndim=3, time_attr="t", tracklet_attr="track_id"
    )
    assert incoming.features.tracklet_key != tracks_viewer.tracks.features.tracklet_key

    tracks_viewer.update_tracks(tracks=incoming, name="other")  # must not raise

    assert tracks_viewer.node_color_feature_key == "track_id"


GHOST = "ghost_group"


@pytest.fixture
def with_ghost_feature(tracks_viewer):
    """Tracks whose feature dict describes a feature the graph has no column for.

    `FeatureDict` is a plain dict that nothing keeps in sync with the graph -
    `from_json` rebuilds it from saved metadata - so loaded tracks can end up
    like this. `add_feature` (what the groups widget uses) would add the
    column, which is why this writes the dict directly.
    """
    tracks_viewer.tracks.features[GHOST] = {
        "feature_type": "node",
        "value_type": "bool",
        "num_values": 1,
        "display_name": GHOST,
        "default_value": False,
    }
    return tracks_viewer


class TestFeatureWithoutAGraphColumn:
    def test_is_not_offered(self, with_ghost_feature):
        assert GHOST not in node_categorical_feature_keys(with_ghost_feature.tracks)

    def test_selecting_it_anyway_falls_back_to_track_ids(self, with_ghost_feature):
        # nothing in the UI can reach this now, but the fallback is what keeps
        # a bad key from being committed by any other caller
        with_ghost_feature.set_node_color_feature(GHOST)

        tracklet_key = with_ghost_feature.tracks.features.tracklet_key
        assert with_ghost_feature.node_color_feature_key == tracklet_key
        assert isinstance(
            with_ghost_feature.node_colormap.color_source, CategoricalColorSource
        )

    def test_does_not_wedge_every_later_refresh(self, with_ghost_feature):
        with_ghost_feature.set_node_color_feature(GHOST)

        with_ghost_feature._refresh()  # must not raise


class TestClearTracks:
    """clear_tracks is the mirror of update_tracks, colormap included."""

    def test_forgets_the_colors_of_the_tracks_that_went_away(self, grouped):
        grouped.set_node_color_feature(GROUP)
        assert len(grouped.node_colormap.nodes) > 0

        grouped.clear_tracks()

        assert len(grouped.node_colormap.nodes) == 0

    def test_resets_the_feature_being_colored_by(self, grouped):
        grouped.set_node_color_feature(GROUP)

        grouped.clear_tracks()

        assert grouped.node_color_feature_key is None

    def test_loading_tracks_again_colors_them(self, grouped, solution_tracks_3d):
        grouped.set_node_color_feature(GROUP)
        grouped.clear_tracks()

        grouped.update_tracks(tracks=solution_tracks_3d, name="test")

        assert (
            grouped.node_color_feature_key == solution_tracks_3d.features.tracklet_key
        )
        nodes = solution_tracks_3d.graph_solution.node_ids()
        # every node has a color again (the colormap also holds the label the
        # labels layer has minted to paint with, so this is a subset check)
        assert set(nodes) <= set(grouped.node_colormap.nodes)
        assert (grouped.node_colormap.get_colors(nodes)[:, 3] == 1.0).all()


class TestContinuousColoring:
    """Coloring by a numeric feature: time, in the 3D fixture node 1 at t=0
    and nodes 2 and 3 at t=1, so the two ends of the gradient."""

    def test_recolors_every_view(self, tracks_viewer):
        tracks_viewer.set_node_color_feature("t")

        assert isinstance(tracks_viewer.node_colormap.color_source, GradientColorSource)
        ends = tracks_viewer.node_colormap.color_source.colormap.map(
            np.asarray([0.0, 1.0])
        )
        colors = _view_colors(tracks_viewer)
        for view in VIEWS:
            assert np.allclose(colors[view][1], ends[0][:3]), view
            assert np.allclose(colors[view][2], ends[1][:3]), view
            assert np.allclose(colors[view][3], ends[1][:3]), view

    def test_a_new_label_is_painted_grey(self, tracks_viewer):
        # its value is not known until the node exists
        tracks_viewer.set_node_color_feature("t")

        _track, pending, swatch, _committed = _paint_new_label(tracks_viewer)

        assert np.allclose(pending, GREY)
        assert np.array_equal(swatch, [0, 0, 0, 0])


EDGE_FEATURE = "iou"
# the 3D fixture's two edges, 1 -> 2 and 1 -> 3, as (target node, value)
EDGE_VALUES = {2: 0.2, 3: 0.9}


@pytest.fixture
def with_edge_feature(tracks_viewer):
    """The same tracks with a numeric edge feature on both edges."""
    tracks = tracks_viewer.tracks
    tracks.add_feature(
        EDGE_FEATURE,
        {
            "feature_type": "edge",
            "value_type": "float",
            "num_values": 1,
            "display_name": "IoU",
            "default_value": None,
        },
    )
    graph = tracks.graph_solution
    df = graph.edge_attrs(attr_keys=["edge_id", "target_id"])
    graph.update_edge_attrs(
        edge_ids=df["edge_id"].to_list(),
        attrs={EDGE_FEATURE: [EDGE_VALUES[t] for t in df["target_id"].to_list()]},
    )
    return tracks_viewer


def _tree_edge_colors(tracks_viewer):
    """The tree's edge color per target node, as `_build_edges` would draw it."""
    from napari_track_edit.data_views.views.tree_view.tree_plot_fpl import (
        TreePlot,
    )

    df = tracks_viewer.track_df
    plot = TreePlot.__new__(TreePlot)  # only _build_edges' inputs are needed
    plot._node_ids = df["node_id"].to_numpy()
    plot._positions = np.zeros((len(df), 3), dtype=np.float32)
    colors = np.stack(df["color"].to_numpy()).astype(np.float32) / 255.0
    _pos, edge_cols = plot._build_edges(df, colors)
    children = df["node_id"].to_numpy()[df["parent_id"].to_numpy() != 0]
    return {int(c): edge_cols[3 * i][:3] for i, c in enumerate(children)}


class TestEdgeColoring:
    def test_edges_follow_their_nodes_by_default(self, with_edge_feature):
        colors = _view_colors(with_edge_feature)["tree"]

        edges = _tree_edge_colors(with_edge_feature)

        assert "edge_color" not in with_edge_feature.track_df.columns
        for target, rgb in edges.items():
            assert np.allclose(rgb, colors[target], atol=1 / 255), target

    def test_edge_feature_colors_tree_edges_as_a_gradient(self, with_edge_feature):
        with_edge_feature.set_edge_color_feature(EDGE_FEATURE)

        source = with_edge_feature.edge_colormap.color_source
        assert isinstance(source, GradientColorSource)
        assert source.limits == (0.2, 0.9)
        ends = source.colormap.map(np.asarray([0.0, 1.0]))[:, :3]
        edges = _tree_edge_colors(with_edge_feature)
        assert np.allclose(edges[2], ends[0], atol=1 / 255)
        assert np.allclose(edges[3], ends[1], atol=1 / 255)

    def test_node_colors_are_left_alone(self, with_edge_feature):
        before = _view_colors(with_edge_feature)

        with_edge_feature.set_edge_color_feature(EDGE_FEATURE)

        after = _view_colors(with_edge_feature)
        for view in VIEWS:
            for node in NODES:
                assert np.allclose(after[view][node], before[view][node]), (
                    view,
                    node,
                )

    def test_none_draws_every_edge_grey(self, with_edge_feature):
        with_edge_feature.set_edge_color_feature(None)

        edges = _tree_edge_colors(with_edge_feature)
        for target, rgb in edges.items():
            assert np.allclose(rgb, GREY, atol=1 / 255), target

    def test_back_to_same_as_nodes(self, with_edge_feature):
        with_edge_feature.set_edge_color_feature(EDGE_FEATURE)

        with_edge_feature.set_edge_color_feature(SAME_AS_NODES)

        assert "edge_color" not in with_edge_feature.track_df.columns

    def test_deleting_the_feature_falls_back_to_node_colors(self, with_edge_feature):
        with_edge_feature.set_edge_color_feature(EDGE_FEATURE)

        del with_edge_feature.tracks.features[EDGE_FEATURE]
        with_edge_feature._refresh()  # must not raise

        assert with_edge_feature.edge_color_feature_key == SAME_AS_NODES
        assert "edge_color" not in with_edge_feature.track_df.columns

    def test_new_tracks_reset_edge_coloring(
        self, with_edge_feature, solution_tracks_2d
    ):
        with_edge_feature.set_edge_color_feature(EDGE_FEATURE)

        with_edge_feature.update_tracks(tracks=solution_tracks_2d, name="other")

        assert with_edge_feature.edge_color_feature_key == SAME_AS_NODES
