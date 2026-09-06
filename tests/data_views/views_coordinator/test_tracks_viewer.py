"""Tests for TracksViewer - the central coordinator for track visualization.

Tests cover node operations, edge operations, display modes, and selection management.
"""

from unittest.mock import MagicMock, patch

import napari
import pytest
from funtracks.data_model import SolutionTracks

from motile_tracker.data_views.views.layers.track_graph import TrackGraph
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views.layers.track_points import TrackPoints
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.motile.backend.motile_run import MotileRun


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.fixture
def tracks_viewer_setup(viewer, graph_2d):
    """Fixture that creates a tracks_viewer with tracks loaded.

    Returns tuple of (viewer, tracks_viewer, tracks) for reuse across tests.
    """
    tracks = MotileRun(graph=graph_2d, run_name="test", ndim=3, time_attr="t")
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")
    return viewer, tracks_viewer, tracks


class TestNodeOperations:
    """Tests for node manipulation operations."""

    def test_delete_single_node(self, tracks_viewer_setup, click_node):
        """Test deleting a single node actually removes it from the graph."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        node_to_delete = 6  # unconnected node in graph_2d
        click_node(tracks_viewer, node_to_delete)

        tracks_viewer.delete_node()

        assert not tracks.graph.has_node(node_to_delete)

    def test_delete_multiple_nodes(self, tracks_viewer_setup, click_node):
        """Test deleting multiple selected nodes removes all of them."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # nodes 5 (terminal) and 6 (unconnected) are safe to delete independently
        nodes_to_delete = [5, 6]
        click_node(tracks_viewer, nodes_to_delete[0])
        for node in nodes_to_delete[1:]:
            click_node(tracks_viewer, node, append=True)

        tracks_viewer.delete_node()

        for node in nodes_to_delete:
            assert not tracks.graph.has_node(node)

    def test_delete_node_with_no_tracks(self, viewer):
        """Test delete_node does nothing when no tracks are loaded."""
        tracks_viewer = TracksViewer.get_instance(viewer)

        # Should not raise an error
        tracks_viewer.delete_node()


class TestEdgeOperations:
    """Tests for edge manipulation operations."""

    def test_disconnect_nodes(self, tracks_viewer_setup, click_node):
        """Test that connect_nodes breaks the edge between two connected nodes."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Test 1: Break the edge between two connected nodes
        edges = tracks.graph.edge_list()
        if not edges:
            pytest.skip("No edges in test graph")

        source, target = edges[0]
        click_node(tracks_viewer, source)
        click_node(tracks_viewer, target, append=True)

        tracks_viewer.connect_nodes()

        # Verify the edge was actually deleted from the graph
        assert not tracks.graph.has_edge(source, target)

        # Test 2: A single selected node is a no-op
        single_node = list(tracks.graph.node_ids())[0]
        click_node(tracks_viewer, single_node)

        edge_count_before = tracks.graph.num_edges()
        tracks_viewer.connect_nodes()

        # Should not have deleted anything
        assert tracks.graph.num_edges() == edge_count_before

    def test_swap_nodes(self, viewer, graph_2d_without_segmentation, click_node):
        """Test swapping predecessors of two nodes updates the graph correctly.

        Extends graph_2d by adding node 7 (t=3) as a predecessor for node 6 (t=4).
        Nodes 5 and 6 are then at the same timepoint with different predecessors
        (4 and 7 respectively), creating a valid swap scenario.
        """
        graph_2d_without_segmentation.bulk_add_nodes(
            nodes=[
                {
                    "t": 3,
                    "pos": [95.0, 95.0],
                    "area": 100.0,
                    "track_id": 5,
                    "lineage_id": 2,
                    "solution": True,
                }
            ],
            indices=[7],
        )
        graph_2d_without_segmentation.bulk_add_edges(
            [{"source_id": 7, "target_id": 6, "solution": True}]
        )

        tracks = SolutionTracks(
            graph=graph_2d_without_segmentation, ndim=3, time_attr="t"
        )
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Select nodes 5 and 6 (both t=4, predecessors 4 and 7 respectively)
        click_node(tracks_viewer, 5)
        click_node(tracks_viewer, 6, append=True)

        tracks_viewer.swap_nodes()

        # After swap: predecessors are exchanged (4->6, 7->5)
        assert tracks.graph.has_edge(4, 6)
        assert tracks.graph.has_edge(7, 5)
        assert not tracks.graph.has_edge(4, 5)
        assert not tracks.graph.has_edge(7, 6)

    def test_connect_nodes_sorts_by_time(self, viewer, graph_2d, click_node):
        """Test connect_nodes orders nodes by time (earlier -> later).

        Uses graph_2d (with segmentation) so click_node goes through TrackLabels,
        which returns np.int64 node IDs — matching the real UI path.
        Uses MotileRun so edge attributes like 'iou' are registered in features.
        """
        tracks = MotileRun(graph=graph_2d, run_name="test", ndim=3, time_attr="t")
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Node 2 (t1, no successors) and node 6 (t4, no predecessors): valid free edge
        # Select in reverse time order to verify sorting
        click_node(tracks_viewer, 6)  # t4, clicked first
        click_node(tracks_viewer, 2, append=True)  # t1, shift-clicked second

        tracks_viewer.connect_nodes()

        # Edge must go from earlier (2) to later (6), regardless of selection order
        assert tracks.graph.has_edge(2, 6)

    def test_connect_nodes_with_force(self, viewer, graph_2d, monkeypatch, click_node):
        """Test connect_nodes handles forceable errors by retrying with force=True.

        Uses graph_2d (with segmentation) so click_node goes through TrackLabels,
        which returns np.int64 node IDs — matching the real UI path.
        Uses MotileRun so edge attributes like 'iou' are registered in features.
        """
        tracks = MotileRun(graph=graph_2d, run_name="test", ndim=3, time_attr="t")
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Node 4 (t2) already has incoming edge from node 3.
        # Adding edge 2(t1)->4 raises InvalidActionError(forceable=True).
        click_node(tracks_viewer, 2)
        click_node(tracks_viewer, 4, append=True)

        # Approve the force dialog automatically
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer.confirm_force_operation",
            lambda message: (True, False),
        )

        tracks_viewer.connect_nodes()

        # New edge should be in the graph
        assert tracks.graph.has_edge(2, 4)
        # Conflicting edge should have been removed by force
        assert not tracks.graph.has_edge(3, 4)

    def test_connect_mode_dialog_divisions(
        self, tracks_viewer_setup, monkeypatch, click_node
    ):
        """Node 4 already has child 5, so the user is asked which mode they want.

        Choosing 'with divisions' keeps the existing child edge.
        """
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        click_node(tracks_viewer, 4)  # t2, has child 5
        click_node(tracks_viewer, 6, append=True)  # t4, unconnected

        ask_mock = MagicMock(return_value=False)  # False == with divisions
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "ask_connect_mode",
            ask_mock,
        )

        tracks_viewer.connect_nodes()

        ask_mock.assert_called_once()
        assert tracks.graph.has_edge(4, 6)
        assert tracks.graph.has_edge(4, 5)  # kept as a division

    def test_connect_mode_dialog_linear(
        self, tracks_viewer_setup, monkeypatch, click_node
    ):
        """Choosing 'linear' turns the existing child edge into a conflict."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        click_node(tracks_viewer, 4)
        click_node(tracks_viewer, 6, append=True)
        tracks_viewer.force = False

        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "ask_connect_mode",
            MagicMock(return_value=True),  # True == linear
        )
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "confirm_force_operation",
            lambda message: (True, False),
        )

        tracks_viewer.connect_nodes()

        assert tracks.graph.has_edge(4, 6)
        assert not tracks.graph.has_edge(4, 5)  # broken to keep the track linear

    def test_connect_mode_dialog_cancelled(
        self, tracks_viewer_setup, monkeypatch, click_node
    ):
        """Cancelling the mode dialog leaves the graph untouched."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        click_node(tracks_viewer, 4)
        click_node(tracks_viewer, 6, append=True)

        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "ask_connect_mode",
            MagicMock(return_value=None),
        )

        num_edges_before = tracks.graph.num_edges()
        tracks_viewer.connect_nodes()

        assert tracks.graph.num_edges() == num_edges_before
        assert not tracks.graph.has_edge(4, 6)

    def test_connect_mode_dialog_skipped_without_a_choice(
        self, tracks_viewer_setup, monkeypatch, click_node
    ):
        """Node 2 has no children, so both modes are the same and nothing is asked."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        click_node(tracks_viewer, 2)  # t1, no children
        click_node(tracks_viewer, 6, append=True)

        ask_mock = MagicMock()
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "ask_connect_mode",
            ask_mock,
        )

        tracks_viewer.connect_nodes()

        ask_mock.assert_not_called()
        assert tracks.graph.has_edge(2, 6)

    def test_keyboard_shortcuts_bypass_the_dialog(
        self, tracks_viewer_setup, monkeypatch, click_node
    ):
        """C and Shift+C pick a mode directly, without asking."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        ask_mock = MagicMock()
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "ask_connect_mode",
            ask_mock,
        )

        # C: connect with divisions
        click_node(tracks_viewer, 4)
        click_node(tracks_viewer, 6, append=True)
        tracks_viewer.connect_nodes_with_divisions()

        ask_mock.assert_not_called()
        assert tracks.graph.has_edge(4, 6)
        assert tracks.graph.has_edge(4, 5)

        # Shift+C: connect linearly, forcing away the conflicting child edge
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_viewer."
            "confirm_force_operation",
            lambda message: (True, False),
        )
        tracks_viewer.selected_nodes.reset()
        click_node(tracks_viewer, 4)
        click_node(tracks_viewer, 5, append=True)
        tracks_viewer.connect_nodes_linearly()  # 4 -> 5 exists: disconnects instead

        ask_mock.assert_not_called()
        assert not tracks.graph.has_edge(4, 5)


class TestDisplayModes:
    """Tests for display mode switching and filtering."""

    def test_toggle_display_mode_skips_group_when_empty(self, tracks_viewer_setup):
        """Test toggle_display_mode alternates between 'all' and 'lineage' when no
        groups exist, skipping 'group' mode."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # No groups exist
        assert tracks_viewer.get_collection_widget().collection_list.count() == 0

        # Start in "all" mode
        tracks_viewer.set_display_mode("all")
        assert tracks_viewer.mode == "all"

        # Toggle to lineage
        tracks_viewer.toggle_display_mode()
        assert tracks_viewer.mode == "lineage"

        # Without groups, lineage goes straight back to all (skipping group)
        tracks_viewer.toggle_display_mode()
        assert tracks_viewer.mode == "all"

    def test_toggle_display_mode_cycles_with_groups(self, tracks_viewer_setup):
        """Test toggle_display_mode cycles through all three modes when groups exist."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Create a group so the 'group' mode is available
        tracks_viewer.get_collection_widget()._add_group(name="test_group", select=True)
        assert tracks_viewer.get_collection_widget().collection_list.count() == 1

        # Start in "all" mode
        tracks_viewer.set_display_mode("all")
        assert tracks_viewer.mode == "all"

        # Toggle to lineage
        tracks_viewer.toggle_display_mode()
        assert tracks_viewer.mode == "lineage"

        # Toggle to group
        tracks_viewer.toggle_display_mode()
        assert tracks_viewer.mode == "group"

        # Toggle back to all
        tracks_viewer.toggle_display_mode()
        assert tracks_viewer.mode == "all"

    def test_removing_last_group_in_group_mode_falls_back_to_all(
        self, tracks_viewer_setup
    ):
        """Removing the last group while in 'group' mode should auto-switch to 'all'."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup
        collection_widget = tracks_viewer.get_collection_widget()

        collection_widget._add_group(name="test_group", select=True)
        tracks_viewer.set_display_mode("group")
        assert tracks_viewer.mode == "group"

        # Remove the only group
        item = collection_widget.collection_list.item(0)
        collection_widget._remove_group(item)

        assert collection_widget.collection_list.count() == 0
        assert tracks_viewer.mode == "all"

    def test_removing_group_in_other_mode_does_not_change_mode(
        self, tracks_viewer_setup
    ):
        """Removing a group while not in 'group' mode should leave the mode untouched."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup
        collection_widget = tracks_viewer.get_collection_widget()

        collection_widget._add_group(name="test_group", select=True)
        tracks_viewer.set_display_mode("lineage")

        item = collection_widget.collection_list.item(0)
        collection_widget._remove_group(item)

        assert tracks_viewer.mode == "lineage"

    def test_display_modes(self, tracks_viewer_setup, click_node):
        """Test all display modes and filtering behavior."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Test 1: Set display mode to 'all'
        tracks_viewer.set_display_mode("all")
        assert tracks_viewer.mode == "all"
        assert tracks_viewer.visible == "all"

        # Test 2: Filter in all mode
        tracks_viewer.filter_visible_nodes()
        assert tracks_viewer.visible == "all"

        # Test 3: Lineage mode with selection
        node = list(tracks.graph.node_ids())[0]
        click_node(tracks_viewer, node)
        tracks_viewer.set_display_mode("lineage")
        assert tracks_viewer.mode == "lineage"
        assert isinstance(tracks_viewer.visible, list)
        assert node in tracks_viewer.visible

        # Test 4: Group mode (no group selected)
        tracks_viewer.set_display_mode("group")
        assert tracks_viewer.mode == "group"
        assert tracks_viewer.visible == []

    def test_filter_visible_nodes_preserves_previous_lineage(
        self, tracks_viewer_setup, click_node
    ):
        """Test lineage mode preserves previous visible nodes when selection cleared."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Select a node and switch to lineage mode
        node = list(tracks.graph.node_ids())[0]
        click_node(tracks_viewer, node)
        tracks_viewer.set_display_mode("lineage")

        # Clear selection
        tracks_viewer.selected_nodes.reset()
        tracks_viewer.filter_visible_nodes()

        # Should keep showing the previous lineage
        assert len(tracks_viewer.visible) > 0


class TestSelectionManagement:
    """Tests for selection tracking and updates."""

    def test_update_selection_centering(self, tracks_viewer_setup, click_node):
        """Test update_selection centering behavior with different selections."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Test 1: Center on single node
        node = list(tracks.graph.node_ids())[0]
        click_node(tracks_viewer, node)

        with patch.object(tracks_viewer, "center_on_node") as center_mock:
            tracks_viewer.update_selection(set_view=True)
            # Should center on the selected node
            center_mock.assert_called_once_with(node)

        # Test 2: No centering with multiple nodes
        tracks_viewer.selected_nodes.reset()
        nodes = list(tracks.graph.node_ids())[:2]
        for i, node in enumerate(nodes):
            click_node(tracks_viewer, node, append=(i > 0))

        with patch.object(tracks_viewer, "center_on_node") as center_mock:
            tracks_viewer.update_selection(set_view=True)
            # Should NOT center
            center_mock.assert_not_called()

    def test_selected_track_management(self, tracks_viewer_setup, click_node):
        """Test selected_track updates and clearing."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Test 1: Update selected_track from selection
        node = list(tracks.graph.node_ids())[0]
        click_node(tracks_viewer, node)
        tracks_viewer.update_selection()

        # selected_track should be set to the track ID of the selected node
        expected_track_id = tracks.get_track_id(node)
        assert tracks_viewer.selected_track == expected_track_id

        # Test 2: Clear selected_track when selection cleared
        tracks_viewer.selected_nodes.reset()
        tracks_viewer.update_selection()

        # selected_track should be None
        assert tracks_viewer.selected_track is None


class TestSingletonLifecycle:
    """Tests for TracksViewer singleton creation, reuse, and cleanup."""

    def test_instance_cleared_after_viewer_close(self, qapp):
        """_instance must be cleared when the viewer's Qt window is destroyed.

        Regression: without the destroyed-signal connection, _instance survives
        viewer.close() and the next get_instance() call returns a stale wrapper,
        crashing with RuntimeError (wrapped C++ object deleted).
        """
        v = napari.Viewer(show=False)
        TracksViewer.get_instance(v)
        assert hasattr(TracksViewer, "_instance")

        v.close()
        qapp.processEvents()

        assert not hasattr(TracksViewer, "_instance"), (
            "TracksViewer._instance was not cleared after viewer.close(). "
            "A subsequent get_instance() call would return a stale, crashed wrapper."
        )

    def test_get_instance_returns_new_instance_for_different_viewer(self, viewer, qapp):
        """get_instance(v2) must return a fresh instance bound to v2.

        Regression: without the viewer-identity check, the existing _instance is
        silently returned regardless of which viewer is passed, wiring all widgets
        to the wrong canvas.
        """
        tv1 = TracksViewer.get_instance(viewer)
        assert tv1.viewer is viewer

        v2 = napari.Viewer(show=False)
        try:
            tv2 = TracksViewer.get_instance(v2)
            assert tv2 is not tv1, (
                "get_instance(v2) returned the existing instance bound to a different viewer"
            )
            assert tv2.viewer is v2
        finally:
            v2.close()
            qapp.processEvents()
            # _clear_instance was called by the destroyed signal, so _instance is
            # gone. Restore tv1 so the autouse reset_tracks_viewer fixture can
            # clear the module viewer's keybindings on teardown.
            TracksViewer._instance = tv1


class TestTracksSignalCleanup:
    """Tests that a superseded TracksViewer unsubscribes from its tracks object."""

    def test_superseded_instance_disconnects_from_tracks(
        self, viewer, solution_tracks_2d, qapp
    ):
        """Showing one tracks object in successive viewers must not stack up
        listeners on that object's refresh signal.

        Regression: get_instance() replaced _instance without telling the outgoing
        TracksViewer to disconnect, and update_tracks only ever disconnects the
        instance's *own* previous tracks (None for a fresh instance). So every new
        viewer added another _refresh listener to the same Tracks object, and each
        subsequent edit refreshed every viewer ever built - editing cost grew
        linearly with the number of viewers (~2x in a 3-round benchmark).
        """
        tv1 = TracksViewer.get_instance(viewer)
        tv1.update_tracks(tracks=solution_tracks_2d, name="test")
        assert len(solution_tracks_2d.refresh) == 1

        v2 = napari.Viewer(show=False)
        try:
            tv2 = TracksViewer.get_instance(v2)
            tv2.update_tracks(tracks=solution_tracks_2d, name="test")

            assert len(solution_tracks_2d.refresh) == 1, (
                "the superseded TracksViewer is still connected to "
                "tracks.refresh; listeners accumulate per viewer"
            )
            assert len(solution_tracks_2d.action_applied) == 1, (
                "the superseded TracksViewer is still connected to "
                "tracks.action_applied"
            )
        finally:
            v2.close()
            qapp.processEvents()
            TracksViewer._instance = tv1

    def test_disconnects_when_viewer_window_destroyed(self, solution_tracks_2d, qapp):
        """Closing a viewer must unsubscribe its TracksViewer from the tracks."""
        v = napari.Viewer(show=False)
        tv = TracksViewer.get_instance(v)
        tv.update_tracks(tracks=solution_tracks_2d, name="test")
        assert len(solution_tracks_2d.refresh) == 1

        v.close()
        qapp.processEvents()

        assert len(solution_tracks_2d.refresh) == 0, (
            "tracks.refresh still holds a listener from the closed viewer"
        )


class TestUndoRedo:
    """Tests for undo/redo functionality."""

    def test_undo_redo_operations(self, tracks_viewer_setup, click_node):
        """Test undo restores deleted node and redo removes it again."""
        viewer, tracks_viewer, tracks = tracks_viewer_setup

        # Do a real action: delete unconnected node 3
        click_node(tracks_viewer, 3)
        tracks_viewer.delete_node()
        assert not tracks.graph.has_node(3)

        # Undo: node 3 should be restored
        tracks_viewer.undo()
        assert tracks.graph.has_node(3)

        # Redo: node 3 should be gone again
        tracks_viewer.redo()
        assert not tracks.graph.has_node(3)

        tracks_viewer.undo()
        assert tracks.graph.has_node(3)

    def test_undo_redo_with_no_tracks(self, viewer):
        """Test undo/redo do nothing when no tracks are loaded."""
        tracks_viewer = TracksViewer.get_instance(viewer)

        # Should not raise errors
        tracks_viewer.undo()
        tracks_viewer.redo()


class TestLayerCreation:
    """Tests that the correct napari layers are created after loading tracks."""

    def test_layers_present_after_update_tracks(self, viewer, solution_tracks_2d):
        """Test that points, tracks graph, and seg layers are added to the viewer
        after calling update_tracks with a SolutionTracks that has segmentation."""
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

        layer_names = [layer.name for layer in viewer.layers]
        assert "test_points" in layer_names
        assert "test_tracks" in layer_names
        assert "test_seg" in layer_names

    def test_layer_types_after_update_tracks(self, viewer, solution_tracks_2d):
        """Test that the created layers have the correct types."""
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

        layers_by_name = {layer.name: layer for layer in viewer.layers}
        assert isinstance(layers_by_name["test_points"], TrackPoints)
        assert isinstance(layers_by_name["test_tracks"], TrackGraph)
        assert isinstance(layers_by_name["test_seg"], TrackLabels)

    def test_layers_present_after_solve(self, viewer, segmentation_2d):
        """End-to-end test: solve on a segmentation, wrap result in MotileRun,
        load into TracksViewer, and verify all three layer types are present."""
        from motile_tracker.motile.backend import MotileRun, SolverParams, solve

        segmentation = segmentation_2d
        params = SolverParams()
        params.appear_cost = None
        solution_graph = solve(params, segmentation)

        run = MotileRun(
            graph=solution_graph,
            run_name="solve_test",
            input_segmentation=segmentation,
            ndim=3,
        )

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=run, name="solve_test")

        layer_names = [layer.name for layer in viewer.layers]
        assert "solve_test_points" in layer_names
        assert "solve_test_tracks" in layer_names
        assert "solve_test_seg" in layer_names
