"""Tests for TrackingFromScratch - creating an empty tracking tree.

The 'track from scratch' flow is the only place where a Tracks object is displayed
with *zero* nodes, so it exercises code paths (layer construction, colormaps, tree
view, table) that every other flow only ever sees with data in them. These tests
guard that empty-graph path.
"""

import numpy as np
import pytest

from motile_tracker.application_menus.track_list_widget import TrackListWidget
from motile_tracker.application_menus.tracking_from_scratch_widget import (
    TrackingFromScratch,
)
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views.layers.track_points import TrackPoints
from motile_tracker.data_views.views.table.custom_table_widget import (
    ColoredTableWidget,
)
from motile_tracker.data_views.views.tree_view.tree_widget import TreeWidget


@pytest.fixture
def scratch_app(make_napari_viewer):
    """A viewer with a size layer, the from-scratch widget, and the two data views
    that also have to cope with an empty graph (tree view and table)."""

    viewer = make_napari_viewer()
    viewer.add_image(np.zeros((5, 10, 10), dtype=np.uint16), name="img")
    widget = TrackingFromScratch(viewer)
    table = ColoredTableWidget(viewer)
    tree = TreeWidget(viewer)
    return viewer, widget, table, tree


@pytest.mark.parametrize(
    ("mode", "layer_type"), [("points", TrackPoints), ("labels", TrackLabels)]
)
def test_start_tracking_creates_empty_tracks(scratch_app, mode, layer_type):
    """Creating empty tracks must build the track layers without raising.

    Regression guard: TrackPoints used to hand napari a (0, 4) face-color array for
    an empty graph, which crashes in `transform_color` ('zero-size array to reduction
    operation minimum').
    """

    _viewer, widget, table, _tree = scratch_app
    widget.size_layer_dropdown.setCurrentText("img")
    widget._start_tracking(mode)

    tracks_viewer = widget.tracks_viewer
    assert tracks_viewer.tracks is not None
    assert tracks_viewer.tracks.graph.num_nodes() == 0

    # the track layers exist and are empty
    points_layer = tracks_viewer.tracking_layers.points_layer
    assert isinstance(points_layer, TrackPoints)
    assert len(points_layer.data) == 0
    if mode == "labels":
        assert isinstance(tracks_viewer.tracking_layers.seg_layer, layer_type)
    else:
        assert tracks_viewer.tracking_layers.seg_layer is None

    # the table view survives an empty graph
    assert table._model.rowCount() == 0
    assert table._id_to_row == {}

    # an empty tree still gets a valid (non-zero) tracklet id to annotate with
    assert tracks_viewer.selected_track is not None
    assert tracks_viewer.selected_track != 0


def test_start_buttons_require_a_size_layer(make_napari_viewer):
    """The start buttons are only enabled once an Image/Labels layer is selected."""

    viewer = make_napari_viewer()
    widget = TrackingFromScratch(viewer)
    assert not widget.start_points_btn.isEnabled()
    assert not widget.start_labels_btn.isEnabled()

    viewer.add_image(np.zeros((5, 10, 10), dtype=np.uint16), name="img")
    widget.size_layer_dropdown.setCurrentText("img")
    assert widget.start_points_btn.isEnabled()
    assert widget.start_labels_btn.isEnabled()


def test_creating_a_second_tree_replaces_the_first(scratch_app):
    """Creating another empty tree switches the tracks viewer over to it."""

    _viewer, widget, _table, _tree = scratch_app
    widget.size_layer_dropdown.setCurrentText("img")

    widget._start_tracking("labels")
    first = widget.tracks_viewer.tracks
    assert first.segmentation is not None

    widget._start_tracking("points")
    second = widget.tracks_viewer.tracks
    assert second is not first
    assert second.segmentation is None


def test_track_list_widget_contains_from_scratch_widget(make_napari_viewer):
    """The from-scratch controls live above the tracks list in the Tracks List tab."""

    viewer = make_napari_viewer()
    widget = TrackListWidget(viewer)
    assert isinstance(widget.layout().itemAt(0).widget(), TrackingFromScratch)
