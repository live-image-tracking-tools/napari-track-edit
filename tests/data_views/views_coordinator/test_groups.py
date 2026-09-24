"""Tests for CollectionButton and CollectionWidget - group management UI.

Tests cover button states, group creation/deletion, node/track/lineage operations,
selection operations, and export functionality.
"""

from unittest.mock import MagicMock, patch

import pytest
from qtpy.QtCore import Qt

from motile_tracker.application_menus.editing_selection_menu import SelectionWidget
from motile_tracker.data_views.views_coordinator.groups import (
    CollectionButton,
    CollectionWidget,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


def test_collection_button(viewer):
    """Test CollectionButton widget initialization, node count updates, and size."""
    # viewer provides the Qt context
    button = CollectionButton("test_group")

    # Test 1: Verify initialization and UI elements
    assert button.name.text() == "test_group"
    assert button.name.height() == 20

    # Verify collection starts empty
    assert len(button.collection) == 0
    assert isinstance(button.collection, set)

    # Verify node count label
    assert button.node_count.text() == "0 node(s)"

    # Verify buttons exist
    assert button.delete is not None
    assert button.export is not None
    assert button.export.toolTip() == "Export nodes in this group to CSV or geff"

    # Test 2: Update node count with multiple nodes
    button.collection = {1, 2, 3, 4, 5}
    button.update_node_count()
    assert button.node_count.text() == "5 node(s)"

    # Remove some nodes
    button.collection = {1, 2}
    button.update_node_count()
    assert button.node_count.text() == "2 node(s)"

    # Test 3: Size hint returns correct height
    hint = button.sizeHint()
    assert hint.height() == 30


def test_collection_widget_initialization(viewer, solution_tracks_2d):
    """Test CollectionWidget initializes correctly and has correct initial button states."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Test 1: Verify initialization
    assert widget.tracks_viewer == tracks_viewer
    assert widget.collection_list is not None
    assert widget.selected_collection is None

    # Verify buttons exist
    assert widget.add_nodes_btn is not None
    assert widget.remove_node_btn is not None
    assert widget.add_track_btn is not None
    assert widget.remove_track_btn is not None
    assert widget.add_lineage_btn is not None
    assert widget.remove_lineage_btn is not None
    assert widget.new_group_button is not None

    # Test 2: Initial button states when no groups exist
    # Edit buttons should be disabled (no group selected)
    assert not widget.add_nodes_btn.isEnabled()
    assert not widget.remove_node_btn.isEnabled()
    assert not widget.add_track_btn.isEnabled()
    assert not widget.remove_track_btn.isEnabled()
    assert not widget.add_lineage_btn.isEnabled()
    assert not widget.remove_lineage_btn.isEnabled()

    # New group button should be enabled (tracks exist)
    assert widget.new_group_button.isEnabled()


def test_group_creation_and_deletion(viewer, solution_tracks_2d, qtbot):
    """Test creating groups (including duplicates) and deleting groups."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Test 1: Create a new group
    widget.group_name.setText("my_test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    assert widget.collection_list.count() == 1

    # Verify group name
    item = widget.collection_list.item(0)
    button = widget.collection_list.itemWidget(item)
    assert button.name.text() == "my_test_group"

    # Verify feature was added to tracks
    assert "my_test_group" in tracks_viewer.tracks.features
    feature = tracks_viewer.tracks.features["my_test_group"]
    assert feature["value_type"] == "bool"
    assert feature["feature_type"] == "node"

    # Test 2: Create group with duplicate name appends _1
    widget.group_name.setText("duplicate")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    widget.group_name.setText("duplicate")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    # Verify both groups exist with different names
    assert widget.collection_list.count() == 3

    item1 = widget.collection_list.item(1)
    button1 = widget.collection_list.itemWidget(item1)
    assert button1.name.text() == "duplicate"

    item2 = widget.collection_list.item(2)
    button2 = widget.collection_list.itemWidget(item2)
    assert button2.name.text() == "duplicate_1"

    # Test 3: Delete a group
    widget.group_name.setText("to_delete")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    assert widget.collection_list.count() == 4
    assert "to_delete" in tracks_viewer.tracks.features

    # Delete the group
    item = widget.collection_list.item(3)
    button = widget.collection_list.itemWidget(item)
    qtbot.mouseClick(button.delete, Qt.MouseButton.LeftButton)

    # Verify group was removed
    assert widget.collection_list.count() == 3
    assert "to_delete" not in tracks_viewer.tracks.features


def test_button_states(viewer, solution_tracks_2d, qtbot, click_node):
    """Test button enable/disable states based on selection and group state."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Test 1: Edit buttons initially disabled (no group selected)
    assert not widget.add_nodes_btn.isEnabled()
    assert not widget.add_track_btn.isEnabled()
    assert not widget.add_lineage_btn.isEnabled()
    assert not widget.remove_node_btn.isEnabled()
    assert not widget.remove_track_btn.isEnabled()
    assert not widget.remove_lineage_btn.isEnabled()

    # Test 2: Edit buttons enabled when group selected and nodes selected
    # Create a group
    widget.group_name.setText("test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    # Ensure nodes are selected
    tracks_viewer.selected_nodes.add_list([1, 2], append=False)

    # Verify edit buttons are enabled when group selected and nodes selected
    assert widget.add_nodes_btn.isEnabled()
    assert widget.add_track_btn.isEnabled()
    assert widget.add_lineage_btn.isEnabled()
    assert widget.remove_node_btn.isEnabled()
    assert widget.remove_track_btn.isEnabled()
    assert widget.remove_lineage_btn.isEnabled()

    # Test 3: Edit buttons disabled when no nodes selected
    tracks_viewer.selected_nodes.reset()
    assert not widget.add_nodes_btn.isEnabled()
    assert not widget.add_track_btn.isEnabled()
    assert not widget.add_lineage_btn.isEnabled()
    assert not widget.remove_node_btn.isEnabled()
    assert not widget.remove_track_btn.isEnabled()
    assert not widget.remove_lineage_btn.isEnabled()


def test_add_remove_nodes(viewer, solution_tracks_2d, qtbot, click_node):
    """Test adding and removing individual nodes to/from groups."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Create a group
    widget.group_name.setText("test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    # Test 1: Add nodes to group
    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    click_node(tracks_viewer, 3, append=True)
    qtbot.mouseClick(widget.add_nodes_btn, Qt.MouseButton.LeftButton)

    # Verify nodes were added to collection
    assert 1 in widget.selected_collection.collection
    assert 2 in widget.selected_collection.collection
    assert 3 in widget.selected_collection.collection
    assert len(widget.selected_collection.collection) == 3
    assert widget.selected_collection.node_count.text() == "3 node(s)"

    # Test 2: Remove some nodes
    click_node(tracks_viewer, 2)
    qtbot.mouseClick(widget.remove_node_btn, Qt.MouseButton.LeftButton)

    # Verify node was removed
    assert 1 in widget.selected_collection.collection
    assert 2 not in widget.selected_collection.collection
    assert 3 in widget.selected_collection.collection
    assert len(widget.selected_collection.collection) == 2


def test_add_remove_tracks(viewer, solution_tracks_2d, qtbot, click_node):
    """Test adding and removing entire tracks to/from groups."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Create a group
    widget.group_name.setText("test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    # Test 1: Add entire track to group
    click_node(tracks_viewer, 1)
    qtbot.mouseClick(widget.add_track_btn, Qt.MouseButton.LeftButton)

    # Verify all nodes in the track were added
    track_id = tracks_viewer.tracks.get_track_id(1)
    track_nodes = tracks_viewer.tracks.track_annotator.tracklet_id_to_nodes[track_id]

    for node in track_nodes:
        assert node in widget.selected_collection.collection

    initial_count = len(widget.selected_collection.collection)
    assert initial_count > 0

    # Test 2: Remove the entire track
    click_node(tracks_viewer, 1)
    qtbot.mouseClick(widget.remove_track_btn, Qt.MouseButton.LeftButton)

    # Verify track was removed
    for node in track_nodes:
        assert node not in widget.selected_collection.collection


def test_add_remove_lineages(viewer, solution_tracks_2d, qtbot, click_node):
    """Test adding and removing entire lineages to/from groups."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Create a group
    widget.group_name.setText("test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    # Test 1: Add entire lineage to group
    click_node(tracks_viewer, 1)
    qtbot.mouseClick(widget.add_lineage_btn, Qt.MouseButton.LeftButton)

    # Verify lineage nodes were added (at least the selected node)
    assert 1 in widget.selected_collection.collection
    assert len(widget.selected_collection.collection) > 0

    initial_count = len(widget.selected_collection.collection)

    # Test 2: Remove the lineage
    click_node(tracks_viewer, 1)
    qtbot.mouseClick(widget.remove_lineage_btn, Qt.MouseButton.LeftButton)

    # Verify lineage was removed (should be empty or much smaller)
    assert len(widget.selected_collection.collection) < initial_count


def test_selection_operations(viewer, solution_tracks_2d, qtbot, click_node):
    """Test selection operations: select, deselect, invert, restore."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)
    selection_widget = SelectionWidget(tracks_viewer)

    # Create a group and add nodes
    widget.group_name.setText("test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    click_node(tracks_viewer, 3, append=True)
    qtbot.mouseClick(widget.add_nodes_btn, Qt.MouseButton.LeftButton)

    # Test 1: Select all nodes in group via CollectionButton
    tracks_viewer.selected_nodes.reset()
    assert len(tracks_viewer.selected_nodes) == 0

    item = widget.collection_list.item(0)
    collection_btn = widget.collection_list.itemWidget(item)
    qtbot.mouseClick(
        collection_btn.select_nodes_in_group_btn, Qt.MouseButton.LeftButton
    )

    # Verify nodes were selected
    assert 1 in tracks_viewer.selected_nodes
    assert 2 in tracks_viewer.selected_nodes
    assert 3 in tracks_viewer.selected_nodes

    # Test 2: Deselect all nodes
    qtbot.mouseClick(selection_widget.deselect_btn, Qt.MouseButton.LeftButton)
    assert len(tracks_viewer.selected_nodes) == 0

    # Test 3: Restore previous selection
    qtbot.mouseClick(selection_widget.reselect_btn, Qt.MouseButton.LeftButton)
    assert 1 in tracks_viewer.selected_nodes
    assert 2 in tracks_viewer.selected_nodes
    assert 3 in tracks_viewer.selected_nodes

    # Test 4: Invert selection
    all_nodes = set(tracks_viewer.tracks.graph_solution.node_ids())
    selected = [1, 2, 3]

    qtbot.mouseClick(selection_widget.invert_btn, Qt.MouseButton.LeftButton)

    # Verify selection was inverted
    expected = all_nodes - set(selected)
    actual = set(tracks_viewer.selected_nodes.as_list)
    assert actual == expected


def test_node_navigation(viewer, solution_tracks_2d, qtbot, click_node):
    """Test jumping to next/previous selected nodes."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    # Mock center_on_node to verify it's called
    center_mock = MagicMock()
    tracks_viewer.center_on_node = center_mock

    selection_widget = SelectionWidget(tracks_viewer)

    # Select multiple nodes
    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    click_node(tracks_viewer, 3, append=True)
    center_mock.reset_mock()  # reset calls that happened during selection setup

    # Test 1: Jump to next node
    qtbot.mouseClick(selection_widget.jump_to_next_btn, Qt.MouseButton.LeftButton)
    center_mock.assert_called_once()

    # Test 2: Jump to previous node
    center_mock.reset_mock()
    qtbot.mouseClick(selection_widget.jump_to_previous_btn, Qt.MouseButton.LeftButton)
    center_mock.assert_called_once()


class TestRetrieveExistingGroups:
    """Test retrieving groups from track features."""

    def test_retrieve_existing_groups(self, viewer, solution_tracks_2d):
        """Test retrieving groups that exist as features on tracks."""
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

        # Add a boolean feature to tracks (simulates existing group)
        from funtracks.features import Feature

        tracks_viewer.tracks.add_feature(
            "existing_group",
            Feature(
                feature_type="node", value_type="bool", num_values=1, default_value=None
            ),
        )

        # Set some nodes to True for this feature
        tracks_viewer.tracks.graph_solution.nodes[1]["existing_group"] = True
        tracks_viewer.tracks.graph_solution.nodes[2]["existing_group"] = True

        widget = CollectionWidget(tracks_viewer)
        widget.retrieve_existing_groups()

        # Verify group was created in the list
        assert widget.collection_list.count() == 1

        # Verify group has correct nodes
        item = widget.collection_list.item(0)
        button = widget.collection_list.itemWidget(item)
        assert button.name.text() == "existing_group"
        assert 1 in button.collection
        assert 2 in button.collection

    def test_refresh_removes_deleted_nodes(
        self, viewer, solution_tracks_2d, qtbot, click_node
    ):
        """Test refresh removes nodes that no longer exist in graph."""
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

        widget = CollectionWidget(tracks_viewer)

        # Create a group and add nodes
        widget.group_name.setText("test_group")
        qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

        click_node(tracks_viewer, 1)
        click_node(tracks_viewer, 2, append=True)
        qtbot.mouseClick(widget.add_nodes_btn, Qt.MouseButton.LeftButton)

        assert len(widget.selected_collection.collection) == 2

        # Remove a node from the graph
        tracks_viewer.tracks.graph_solution.remove_node(1)

        # Mark the node as deleted in the selection system
        tracks_viewer.selected_nodes.deleted_items.add(1)

        # Refresh
        widget._refresh()

        # Verify that the deleted node is still in the collection, but not in the node count
        assert 1 in widget.selected_collection.collection
        assert 2 in widget.selected_collection.collection
        assert len(widget.selected_collection.collection) == 2
        assert widget.selected_collection.node_count.text() == "1 node(s)"


@patch("motile_tracker.data_views.views_coordinator.groups.ExportDialog")
def test_export_button_shows_dialog(
    mock_export_dialog, viewer, solution_tracks_2d, qtbot, click_node
):
    """Test export button shows export dialog."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Create a group and add nodes
    widget.group_name.setText("export_test")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    qtbot.mouseClick(widget.add_nodes_btn, Qt.MouseButton.LeftButton)

    # Click export button
    item = widget.collection_list.item(0)
    button = widget.collection_list.itemWidget(item)
    qtbot.mouseClick(button.export, Qt.MouseButton.LeftButton)

    # Verify export dialog was called
    mock_export_dialog.show_export_dialog.assert_called_once()

    # Verify correct parameters were passed
    call_args = mock_export_dialog.show_export_dialog.call_args
    assert call_args.kwargs["name"] == "export_test"
    assert call_args.kwargs["tracks"] == solution_tracks_2d
    assert 1 in call_args.kwargs["nodes_to_keep"]
    assert 2 in call_args.kwargs["nodes_to_keep"]


def test_is_deleted_flag_prevents_updates(viewer, solution_tracks_2d):
    """Test that _is_deleted flag prevents further updates when widget is deleted."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Mock selectedItems to raise RuntimeError with "has been deleted" message
    with patch.object(widget.collection_list, "selectedItems") as mock_selected:
        mock_selected.side_effect = RuntimeError(
            "wrapped C/C++ object of type QListWidget has been deleted"
        )

        # Call _update_buttons_and_node_count which should catch this
        widget._update_buttons_and_node_count()

        # Verify _is_deleted flag was set
        assert widget._is_deleted is True

    # Call _update_buttons_and_node_count which should return early
    # when _is_deleted is True. If it raises, the test fails.
    widget._update_buttons_and_node_count()

    # Verify _is_deleted flag is still True
    assert widget._is_deleted is True


def test_node_count_accounting_for_deleted_items(
    viewer, solution_tracks_2d, qtbot, click_node
):
    """Test node count correctly excludes deleted items."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = CollectionWidget(tracks_viewer)

    # Create a group and add nodes
    widget.group_name.setText("test_group")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)

    click_node(tracks_viewer, 1)
    click_node(tracks_viewer, 2, append=True)
    click_node(tracks_viewer, 3, append=True)
    qtbot.mouseClick(widget.add_nodes_btn, Qt.MouseButton.LeftButton)

    # Verify initial count
    assert widget.selected_collection.node_count.text() == "3 node(s)"

    # Mark some nodes as deleted
    tracks_viewer.selected_nodes.deleted_items.add(1)
    tracks_viewer.selected_nodes.deleted_items.add(2)

    # Update counts
    widget._update_buttons_and_node_count(update_counts=True)

    # Verify count is reduced (only node 3 remains)
    assert widget.selected_collection.node_count.text() == "1 node(s)"
