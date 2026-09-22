"""Changing the feature the colormap colors by, and keeping every view in sync.

The colormap object is shared by all the views, but each of them caches colors
of its own, so these tests mostly check that a feature change actually reaches
the labels, points, tracks, tree and table - not just the colormap.
"""

import numpy as np
import pytest
from funtracks.user_actions import UserUpdateSegmentation

from motile_tracker.data_views.colormap import PENDING_GREY
from motile_tracker.data_views.views.table.custom_table_widget import (
    ColoredTableWidget,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

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
    nodes = list(tracks_viewer.tracks.graph.node_ids())
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

    tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)

    after = _view_colors(tracks_viewer)
    for view in VIEWS:
        # the three nodes share a lineage, so now they share a color...
        assert np.allclose(after[view][1], after[view][2]), view
        assert np.allclose(after[view][2], after[view][3]), view
        # ...and it is not the one they had before
        assert not np.allclose(after[view][2], before[view][2]), view


def test_switching_back_restores_track_id_colors(tracks_viewer):
    before = _view_colors(tracks_viewer)

    tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)
    tracks_viewer.set_color_feature(tracks_viewer.tracks.features.tracklet_key)

    after = _view_colors(tracks_viewer)
    for view in VIEWS:
        for node in NODES:
            assert np.allclose(after[view][node], before[view][node]), (view, node)


def test_tracks_layer_keeps_its_track_ids(tracks_viewer):
    # coloring the tracks layer per node must not cost it the track_id property
    # that update_track_visibility filters on
    before = _view_colors(tracks_viewer)["track_ids"]

    tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)

    assert np.array_equal(_view_colors(tracks_viewer)["track_ids"], before)


def test_table_follows_the_feature(viewer, tracks_viewer, qtbot):
    table = ColoredTableWidget(viewer)
    qtbot.addWidget(table)
    before = table._model._bg[table._id_to_row[2]].name()

    tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)

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

        expected = tracks_viewer.colormap.map(np.asarray([track]))[0][:3]
        assert np.allclose(pending, expected)
        assert np.allclose(swatch[:3], expected)
        assert swatch[3] == 1
        assert np.allclose(committed, expected)

    def test_lineage_color_is_kept_through_the_paint(self, tracks_viewer):
        # a new track's lineage id is worked out the same way UserAddNode will,
        # so the colour painted with is the one the node commits to
        tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)

        _track, pending, swatch, committed = _paint_new_label(tracks_viewer)

        assert not np.allclose(pending, PENDING_GREY)
        assert np.allclose(pending, committed)
        # the swatch names a track id, which has no colour of its own here
        assert np.array_equal(swatch, [0, 0, 0, 0])

    def test_lineage_color_of_an_existing_track_is_kept_through_the_paint(
        self, tracks_viewer
    ):
        # continuing an existing track: the node inherits that track's lineage,
        # not a fresh one
        tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)
        seg = tracks_viewer.tracking_layers.seg_layer
        tracks_viewer.selected_nodes.add(1)
        seg._ensure_valid_label()

        _track, pending, swatch, committed = _paint_new_label(tracks_viewer)

        assert np.allclose(pending, committed)

    def test_swatch_has_no_color_while_coloring_by_another_feature(self, tracks_viewer):
        tracks_viewer.set_color_feature(tracks_viewer.tracks.features.lineage_key)

        tracks_viewer.set_track_id_color(1)

        assert np.array_equal(tracks_viewer.track_id_color, [0, 0, 0, 0])
