"""Tests for the shared napari key bindings defined in keybindings_config."""

import pytest
from napari.utils.key_bindings import coerce_keybinding

from motile_tracker.data_views.views.layers.contour_labels import ContourLabels
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

M = coerce_keybinding("m")


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


def _binds_new_track(keymap_provider, tracks_viewer) -> bool:
    """Whether [M] on this viewer or layer starts a new track."""

    return keymap_provider.keymap.get(M) == tracks_viewer.request_new_track


def test_m_starts_a_new_track_from_every_layer(
    viewer, solution_tracks_3d_with_division
):
    """[M] is the 'start a new track' action, so it must reach the TracksViewer from
    the viewer itself and from every tracking layer, not just the labels layer."""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    assert _binds_new_track(viewer, tracks_viewer)
    assert _binds_new_track(tracks_viewer.tracking_layers.seg_layer, tracks_viewer)
    assert _binds_new_track(tracks_viewer.tracking_layers.points_layer, tracks_viewer)


def test_m_is_not_naparis_new_label(viewer, solution_tracks_3d_with_division):
    """napari's own [M] hands out a label without a track id to go with it. It must
    not be reachable on the labels layers, neither from the class keymaps nor from
    the instance keymap of a layer that is showing tracks."""

    assert ContourLabels.class_keymap[M] is Ellipsis  # blocks napari's Labels binding
    assert M not in TrackLabels.class_keymap

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")
    seg_layer = tracks_viewer.tracking_layers.seg_layer

    seg_layer.selected_label = 2  # an existing label, so track 1 is the current track
    assert tracks_viewer.selected_track == 1

    seg_layer.keymap[M](seg_layer)

    # a new label to paint with, and a track id to go with it
    assert seg_layer.selected_label == 5  # next available label
    assert tracks_viewer.selected_track == 4  # next available track id


def test_m_without_segmentation_only_starts_a_new_track_id(
    viewer, solution_tracks_3d_without_segmentation, click_node
):
    """Without a labels layer there is no label to hand out, but [M] should still be
    bound on the points layer and give a fresh track id to place points in."""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(
        tracks=solution_tracks_3d_without_segmentation, name="test"
    )
    points_layer = tracks_viewer.tracking_layers.points_layer

    assert tracks_viewer.tracking_layers.seg_layer is None
    assert _binds_new_track(points_layer, tracks_viewer)

    click_node(tracks_viewer, 1)  # selects the track this node belongs to
    assert tracks_viewer.selected_track in tracks_viewer.tracks.track_id_to_node

    points_layer.keymap[M](points_layer)

    assert tracks_viewer.selected_track not in tracks_viewer.tracks.track_id_to_node
