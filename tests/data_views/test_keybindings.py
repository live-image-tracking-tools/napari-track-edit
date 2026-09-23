"""Tests for the shared napari key bindings defined in keybindings_config."""

import pytest
from napari.utils.action_manager import action_manager
from napari.utils.key_bindings import KeymapHandler, coerce_keybinding

from motile_tracker.data_views.keybindings_config import (
    blocked_napari_binding,
    set_shortcut,
)
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

    assert M not in TrackLabels.class_keymap

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    # blocks napari's Labels binding, for a ContourLabels with no tracks on it
    assert ContourLabels.class_keymap[M] is blocked_napari_binding
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


def test_blocking_napari_does_not_break_key_presses(
    viewer, solution_tracks_3d_with_division
):
    """The block must not put an `Ellipsis` in the keymap chain.

    Regression test: `Ellipsis` is napari's documented way to block a key, but
    napari 0.6's `on_key_press` passes the raw chain to
    `action_manager._get_repeatable_shortcuts`, which reads `__name__` off every
    value - so every canvas key press raised AttributeError. It only surfaced
    once the user rebound [M], because until then our own instance binding for
    [M] shadowed the blocked entry in the ChainMap.
    """

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    handler = KeymapHandler()
    handler.keymap_providers = [tracks_viewer.tracking_layers.seg_layer, viewer]

    set_shortcut("request_new_track", "j")

    assert Ellipsis not in handler.keymap_chain.values()
    # what napari does on every key press in the canvas
    action_manager._get_repeatable_shortcuts(handler.keymap_chain)


def test_block_follows_the_rebound_key(viewer, solution_tracks_3d_with_division):
    """After a rebind, napari's new_label must be blocked on the new key and
    reachable again on the old one - otherwise [M] silently hands out a label
    with no track id behind it."""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    assert ContourLabels.class_keymap[M] is blocked_napari_binding

    set_shortcut("request_new_track", "j")

    assert ContourLabels.class_keymap[coerce_keybinding("j")] is blocked_napari_binding
    assert ContourLabels.class_keymap.get(M) is not blocked_napari_binding
