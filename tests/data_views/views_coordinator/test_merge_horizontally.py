"""Tests for the horizontal merge action driven from the TracksViewer.

Covers the dialog flow (one dialog per distinct set of tracklet IDs, cancelling)
and the resulting graph edits.
"""

from unittest.mock import patch

import pytest
from qtpy.QtCore import Qt

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.data_views.views_coordinator.user_dialogs import (
    MergeTrackIDDialog,
)
from motile_tracker.motile.backend.motile_run import MotileRun

DIALOG = (
    "motile_tracker.data_views.views_coordinator.tracks_viewer.select_merge_track_id"
)
WARNING = (
    "motile_tracker.data_views.views_coordinator.tracks_viewer.QMessageBox.warning"
)
OPTIONS = (
    "motile_tracker.data_views.views_coordinator.tracks_viewer.get_track_id_options"
)
MERGE = "motile_tracker.data_views.views_coordinator.tracks_viewer.UserMergeNodes"


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.fixture
def tracks_viewer_setup(viewer, graph_2d):
    """A tracks_viewer with graph_2d loaded.

    graph_2d holds nodes 1 (t=0), 2 and 3 (t=1), 4 (t=2), 5 and 6 (t=4), with
    track ids 1, 2, 3, 3, 3 and 5.
    """
    tracks = MotileRun(graph=graph_2d, run_name="test", ndim=3, time_attr="t")
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")
    return tracks_viewer, tracks


def select_nodes(tracks_viewer, click_node, nodes):
    for i, node in enumerate(nodes):
        click_node(tracks_viewer, node, append=i > 0)


def test_merge_one_set(tracks_viewer_setup, click_node):
    """Nodes 2 and 3 share t=1: one dialog, and the merge is applied."""
    tracks_viewer, tracks = tracks_viewer_setup
    select_nodes(tracks_viewer, click_node, [2, 3])

    with patch(DIALOG, return_value=3) as dialog:
        tracks_viewer.merge_horizontally()

    dialog.assert_called_once_with([2, 3], [1], tracks_viewer.colormap)
    assert not tracks.graph_solution.has_node(2)
    assert tracks.graph_solution.has_node(3)


def test_cancelling_merges_nothing(tracks_viewer_setup, click_node):
    tracks_viewer, tracks = tracks_viewer_setup
    select_nodes(tracks_viewer, click_node, [2, 3])

    with patch(DIALOG, return_value=None):
        tracks_viewer.merge_horizontally()

    assert tracks.graph_solution.has_node(2)
    assert tracks.graph_solution.has_node(3)


def test_two_sets_with_different_track_ids(tracks_viewer_setup, click_node):
    """t=1 offers track ids 2 and 3, t=4 offers 3 and 4, so both are asked."""
    tracks_viewer, tracks = tracks_viewer_setup
    select_nodes(tracks_viewer, click_node, [2, 3, 5, 6])

    with patch(DIALOG, side_effect=[3, 4]) as dialog:
        tracks_viewer.merge_horizontally()

    assert dialog.call_count == 2
    assert dialog.call_args_list[0].args == ([2, 3], [1], tracks_viewer.colormap)
    assert dialog.call_args_list[1].args == ([3, 4], [4], tracks_viewer.colormap)
    assert not tracks.graph_solution.has_node(2)
    assert tracks.graph_solution.has_node(3)
    assert not tracks.graph_solution.has_node(5)
    assert tracks.graph_solution.has_node(6)


def test_two_sets_with_same_track_ids(tracks_viewer_setup, click_node):
    """Both sets offer the same tracklet ids, so a single dialog suffices and the
    answer is applied to both time points."""
    tracks_viewer, tracks = tracks_viewer_setup
    select_nodes(tracks_viewer, click_node, [2, 3, 5, 6])

    with (
        patch(OPTIONS, return_value={1: [2, 3], 4: [2, 3]}),
        patch(DIALOG, return_value=3) as dialog,
        patch(MERGE) as merge,
    ):
        tracks_viewer.merge_horizontally()

    dialog.assert_called_once_with([2, 3], [1, 4], tracks_viewer.colormap)
    assert merge.call_args.kwargs["track_ids"] == {1: 3, 4: 3}


def test_invalid_selection_warns(tracks_viewer_setup, click_node):
    """No two selected nodes share a time point, so nothing is merged."""
    tracks_viewer, tracks = tracks_viewer_setup
    select_nodes(tracks_viewer, click_node, [1, 2, 4])

    with patch(DIALOG) as dialog, patch(WARNING) as warning:
        tracks_viewer.merge_horizontally()

    dialog.assert_not_called()
    warning.assert_called_once()
    assert tracks.graph_solution.has_node(1)
    assert tracks.graph_solution.has_node(2)
    assert tracks.graph_solution.has_node(4)


def test_dialog_buttons_are_colored(tracks_viewer_setup, qtbot):
    """Each tracklet ID gets its own button, bordered in that tracklet's color."""
    tracks_viewer, _ = tracks_viewer_setup

    dialog = MergeTrackIDDialog([2, 3], [1], tracks_viewer.colormap)
    qtbot.addWidget(dialog)

    assert sorted(dialog.track_id_btns) == [2, 3]
    for track_id, button in dialog.track_id_btns.items():
        assert button.text() == str(track_id)
        color = tracks_viewer.colormap.map(track_id)
        rgb = ", ".join(str(int(channel * 255)) for channel in color[:3])
        assert f"border: 3px solid rgb({rgb})" in button.styleSheet()


def test_dialog_returns_clicked_track_id(tracks_viewer_setup, qtbot):
    tracks_viewer, _ = tracks_viewer_setup

    dialog = MergeTrackIDDialog([2, 3], [1], tracks_viewer.colormap)
    qtbot.addWidget(dialog)
    qtbot.mouseClick(dialog.track_id_btns[3], Qt.MouseButton.LeftButton)

    assert dialog.track_id == 3
    assert not dialog.isVisible()


def test_dialog_cancel_returns_none(tracks_viewer_setup, qtbot):
    tracks_viewer, _ = tracks_viewer_setup

    dialog = MergeTrackIDDialog([2, 3], [1], tracks_viewer.colormap)
    qtbot.addWidget(dialog)
    qtbot.mouseClick(dialog.cancel_btn, Qt.MouseButton.LeftButton)

    assert dialog.track_id is None
    assert not dialog.isVisible()
