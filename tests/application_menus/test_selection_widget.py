"""Tests for SelectionWidget - the selection control UI.

Tests cover button states, button interactions, and selection history navigation.
"""

from unittest.mock import MagicMock

from qtpy.QtCore import Qt

from napari_track_edit.application_menus.editing_selection_menu import SelectionWidget
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


def test_selection_widget_initialization(make_napari_viewer, solution_tracks_2d):
    """Test SelectionWidget initializes correctly with correct button states."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = SelectionWidget(tracks_viewer)

    # Test 1: Verify all buttons exist
    assert widget.invert_btn is not None
    assert widget.deselect_btn is not None
    assert widget.reselect_btn is not None
    assert widget.jump_to_next_btn is not None
    assert widget.jump_to_previous_btn is not None
    assert widget.select_next_set_btn is not None
    assert widget.select_previous_set_btn is not None

    # Test 2: Verify initial button states (no selection)
    assert not widget.deselect_btn.isEnabled()
    assert not widget.jump_to_next_btn.isEnabled()
    assert not widget.jump_to_previous_btn.isEnabled()
    assert not widget.reselect_btn.isEnabled()
    assert not widget.select_next_set_btn.isEnabled()
    assert not widget.select_previous_set_btn.isEnabled()

    # Invert button should always be enabled (can invert empty to all)
    assert widget.invert_btn.isEnabled()


def test_button_states_on_selection(make_napari_viewer, solution_tracks_2d):
    """Test button enable/disable states based on selection."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = SelectionWidget(tracks_viewer)

    # Test 1: Deselect, jump buttons enabled when nodes are selected
    tracks_viewer.selected_nodes.add_list([1, 2, 3], append=False)
    assert widget.deselect_btn.isEnabled()
    assert widget.jump_to_next_btn.isEnabled()
    assert widget.jump_to_previous_btn.isEnabled()

    # Test 2: Navigation buttons disabled when selection cleared
    tracks_viewer.selected_nodes.reset()
    assert not widget.deselect_btn.isEnabled()
    assert not widget.jump_to_next_btn.isEnabled()
    assert not widget.jump_to_previous_btn.isEnabled()


def test_button_states_on_history_changes(make_napari_viewer, solution_tracks_2d):
    """Test button states change when navigating selection history."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = SelectionWidget(tracks_viewer)

    # Build some history: add different selections
    tracks_viewer.selected_nodes.add_list([1], append=False)
    tracks_viewer.selected_nodes.add_list([2, 3], append=False)
    tracks_viewer.selected_nodes.add_list([4], append=False)

    # Test 1: Previous selection should be available
    assert widget.select_previous_set_btn.isEnabled()

    # We're at the end, so next should be disabled
    assert not widget.select_next_set_btn.isEnabled()

    # Test 2: Reselect button enabled when prev_set is valid
    assert widget.reselect_btn.isEnabled()


def test_button_interactions(make_napari_viewer, solution_tracks_2d, qtbot):
    """Test button click handlers."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = SelectionWidget(tracks_viewer)

    # Mock the methods
    invert_mock = MagicMock()
    tracks_viewer._invert_selection = invert_mock
    center_mock = MagicMock()
    tracks_viewer.center_on_node = center_mock

    # Test 1: Invert button works
    initial_len = len(tracks_viewer.selected_nodes)
    qtbot.mouseClick(widget.invert_btn, Qt.MouseButton.LeftButton)
    # After invert, selection should be different (all nodes not in current selection)
    assert len(tracks_viewer.selected_nodes) > initial_len

    # Test 2: Deselect button works
    tracks_viewer.selected_nodes.add_list([1, 2], append=False)
    assert len(tracks_viewer.selected_nodes) > 0
    qtbot.mouseClick(widget.deselect_btn, Qt.MouseButton.LeftButton)
    assert len(tracks_viewer.selected_nodes) == 0

    # Test 3: Jump to next node works
    tracks_viewer.selected_nodes.add_list([1, 2, 3], append=False)
    qtbot.mouseClick(widget.jump_to_next_btn, Qt.MouseButton.LeftButton)
    center_mock.assert_called()

    # Test 4: Restore selection works
    first_selection = [1, 2]
    tracks_viewer.selected_nodes.add_list(first_selection, append=False)
    second_selection = [3, 4]
    tracks_viewer.selected_nodes.add_list(second_selection, append=False)

    # Current should be [3, 4]
    assert set(tracks_viewer.selected_nodes) == set(second_selection)

    # Restore should go back to [1, 2]
    qtbot.mouseClick(widget.reselect_btn, Qt.MouseButton.LeftButton)
    assert set(tracks_viewer.selected_nodes) == set(first_selection)


def test_selection_history_navigation(make_napari_viewer, solution_tracks_2d):
    """Test navigating through selection history."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = SelectionWidget(tracks_viewer)

    # Create selection history: [1], [1,2], [3,4,5]
    tracks_viewer.selected_nodes.add_list([1], append=False)
    tracks_viewer.selected_nodes.add_list([1, 2], append=False)
    tracks_viewer.selected_nodes.add_list([3, 4, 5], append=False)

    # Test 1: Can navigate to previous selection
    initial = set(tracks_viewer.selected_nodes)
    assert initial == {3, 4, 5}

    widget.select_previous_set_btn.clicked.emit()
    after_prev = set(tracks_viewer.selected_nodes)
    assert after_prev == {1, 2}

    # Test 2: Can navigate to previous again
    widget.select_previous_set_btn.clicked.emit()
    after_prev2 = set(tracks_viewer.selected_nodes)
    assert after_prev2 == {1}

    # Test 3: Can navigate forward again
    widget.select_next_set_btn.clicked.emit()
    after_next = set(tracks_viewer.selected_nodes)
    assert after_next == {1, 2}
