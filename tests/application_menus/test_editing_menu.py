"""Tests for EditingMenu - the track editing UI widget.

Tests cover button states, button interactions, and track ID display.
"""

from unittest.mock import MagicMock

from qtpy.QtCore import Qt

from motile_tracker.application_menus.editing_selection_menu import EditingMenu
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


def test_button_states(make_napari_viewer, solution_tracks_2d, click_node):
    """Test button enable/disable states based on selection."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    editing_menu = EditingMenu(viewer)

    # Test 1: Verify all edit buttons are disabled when no selection
    assert not editing_menu.delete_node_btn.isEnabled()
    assert not editing_menu.swap_nodes_btn.isEnabled()
    assert not editing_menu.delete_edge_btn.isEnabled()
    assert not editing_menu.create_edge_btn.isEnabled()
    assert not editing_menu.set_division_btn.isEnabled()

    # Test 2: Verify update_buttons() disables all buttons when selection is cleared
    # First select nodes to enable buttons
    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    editing_menu.update_buttons()
    assert editing_menu.delete_node_btn.isEnabled()

    # Now clear selection and call update_buttons
    tracks_viewer.selected_nodes.reset()
    editing_menu.update_buttons()

    # Verify all edit buttons are disabled
    assert not editing_menu.delete_node_btn.isEnabled()
    assert not editing_menu.swap_nodes_btn.isEnabled()
    assert not editing_menu.delete_edge_btn.isEnabled()
    assert not editing_menu.create_edge_btn.isEnabled()
    assert not editing_menu.set_division_btn.isEnabled()

    # Test 3: Verify only delete button enabled with single node selection
    click_node(tracks_viewer, 1)
    editing_menu.update_buttons()

    # Verify only delete is enabled, others disabled
    assert editing_menu.delete_node_btn.isEnabled()
    assert not editing_menu.delete_edge_btn.isEnabled()
    assert not editing_menu.create_edge_btn.isEnabled()
    assert not editing_menu.set_division_btn.isEnabled()

    # Test 4: Verify all buttons enabled when two nodes selected
    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    editing_menu.update_buttons()

    # Verify all edit buttons are enabled
    assert editing_menu.delete_node_btn.isEnabled()
    assert editing_menu.swap_nodes_btn.isEnabled()
    assert editing_menu.delete_edge_btn.isEnabled()
    assert editing_menu.create_edge_btn.isEnabled()
    assert not editing_menu.set_division_btn.isEnabled()

    # Test 5: Verify delete and division buttons enabled with 3 nodes selected
    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    click_node(tracks_viewer, 3, append=True)
    editing_menu.update_buttons()

    # Verify only delete and division are enabled, others disabled
    assert editing_menu.delete_node_btn.isEnabled()
    assert editing_menu.set_division_btn.isEnabled()
    assert not editing_menu.delete_edge_btn.isEnabled()
    assert not editing_menu.create_edge_btn.isEnabled()

    # Test 6: Verify division button is disabled again with 4 nodes selected
    click_node(tracks_viewer, 4, append=True)
    editing_menu.update_buttons()
    assert not editing_menu.set_division_btn.isEnabled()


def test_button_interactions(make_napari_viewer, solution_tracks_2d, qtbot, click_node):
    """Test button click handlers."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    # Mock all methods before creating EditingMenu
    delete_mock = MagicMock()
    tracks_viewer.delete_node = delete_mock
    create_edge_mock = MagicMock()
    tracks_viewer.create_edge = create_edge_mock
    swap_mock = MagicMock()
    tracks_viewer.swap_nodes = swap_mock
    delete_edge_mock = MagicMock()
    tracks_viewer.delete_edge = delete_edge_mock
    set_division_mock = MagicMock()
    tracks_viewer.set_division = set_division_mock
    new_track_mock = MagicMock()
    tracks_viewer.request_new_track = new_track_mock
    undo_mock = MagicMock()
    tracks_viewer.undo = undo_mock
    redo_mock = MagicMock()
    tracks_viewer.redo = redo_mock

    editing_menu = EditingMenu(viewer)

    # Test 1: Delete Node button calls tracks_viewer.delete_node()
    click_node(tracks_viewer, 1)
    editing_menu.update_buttons()
    qtbot.mouseClick(editing_menu.delete_node_btn, Qt.MouseButton.LeftButton)
    delete_mock.assert_called_once()

    # Test 2: Add Edge button calls tracks_viewer.create_edge()
    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    editing_menu.update_buttons()
    qtbot.mouseClick(editing_menu.create_edge_btn, Qt.MouseButton.LeftButton)
    create_edge_mock.assert_called_once()

    # Test 3: Swap Nodes button calls tracks_viewer.swap_nodes()
    qtbot.mouseClick(editing_menu.swap_nodes_btn, Qt.MouseButton.LeftButton)
    swap_mock.assert_called_once()

    # Test 4: Break Edge button calls tracks_viewer.delete_edge()
    qtbot.mouseClick(editing_menu.delete_edge_btn, Qt.MouseButton.LeftButton)
    delete_edge_mock.assert_called_once()

    # Test 5: Make/break division button calls tracks_viewer.set_division()
    click_node(tracks_viewer, 3, append=True)
    editing_menu.update_buttons()
    qtbot.mouseClick(editing_menu.set_division_btn, Qt.MouseButton.LeftButton)
    set_division_mock.assert_called_once()

    # Test 6: Start New Track button calls tracks_viewer.request_new_track()
    qtbot.mouseClick(editing_menu.new_track_btn, Qt.MouseButton.LeftButton)
    new_track_mock.assert_called_once()

    # Test 7: Undo button calls tracks_viewer.undo()
    qtbot.mouseClick(editing_menu.undo_btn, Qt.MouseButton.LeftButton)
    undo_mock.assert_called_once()

    # Test 8: Redo button calls tracks_viewer.redo()
    qtbot.mouseClick(editing_menu.redo_btn, Qt.MouseButton.LeftButton)
    redo_mock.assert_called_once()


def test_track_id_display(make_napari_viewer, solution_tracks_2d, click_node):
    """Test track ID label updates."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    editing_menu = EditingMenu(viewer)

    # Test 1: Verify label contains the track ID text on creation
    assert "Current Track ID:" in editing_menu.label.text()

    # Test 2: Verify label updates when update_track_id signal is emitted
    click_node(tracks_viewer, 2)
    assert "Current Track ID: 2" in editing_menu.label.text()

    # Test 3: Verify label gets border styling when signal emitted
    tracks_viewer.update_track_id.emit()
    style = editing_menu.label.styleSheet()
    assert "border:" in style
    assert "color:" in style
    assert "rgba(" in style

    # Check that the color of the current track ID matches with the style
    color = tracks_viewer.colormap.map(tracks_viewer.selected_track)
    assert (
        f"rgba({color[0] * 255:.0f}, {color[1] * 255:.0f}, {color[2] * 255:.0f}"
        in style
    )
