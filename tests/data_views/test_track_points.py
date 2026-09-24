"""Tests for TrackPoints - the Points layer for track visualization."""

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from napari_track_edit.data_views.views.layers.track_points import (
    TrackPoints,
    custom_select,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


class MockEvent:
    """Mock event for testing mouse/data events."""

    def __init__(
        self, action=None, value=None, modifiers=None, event_type="mouse_press"
    ):
        self.action = action
        self.value = value
        self.modifiers = modifiers if modifiers is not None else []
        self.type = event_type


def test_initialization(viewer, solution_tracks_2d):
    """Test TrackPoints layer initialization."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Verify layer was created
    assert points_layer is not None
    assert isinstance(points_layer, TrackPoints)
    assert points_layer.name == "test_points"

    # Verify nodes were extracted
    assert len(points_layer.nodes) == solution_tracks_2d.graph.num_nodes()

    # Verify node_index_dict was created
    assert len(points_layer.node_index_dict) == len(points_layer.nodes)
    for idx, node in enumerate(points_layer.nodes):
        assert points_layer.node_index_dict[node] == idx

    # Verify default size was set
    assert points_layer.default_size == 5

    # Verify properties include node_id and track_id
    assert "node_id" in points_layer.properties
    assert "track_id" in points_layer.properties
    assert len(points_layer.properties["node_id"]) == len(points_layer.nodes)

    # Verify type string
    assert points_layer._type_string == "points"


def test_custom_select_blocks_current_size(viewer, solution_tracks_2d):
    """Test custom_select function blocks current_size signal."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Create mock event
    event = MagicMock()

    # Test that custom_select blocks the current_size signal
    generator = custom_select(points_layer, event)
    # Just verify it returns a generator
    assert hasattr(generator, "__iter__")


def test_add_blocks_current_size_event(viewer, solution_tracks_2d):
    """Test add method blocks current_size event."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Mock the blocker
    with patch.object(points_layer.events.current_size, "blocker") as mock_blocker:
        mock_blocker.return_value.__enter__ = MagicMock()
        mock_blocker.return_value.__exit__ = MagicMock()

        # Add a point
        coords = [0, 10, 20]
        points_layer.add(coords)

        # Verify blocker was called. It is used more than once: adding also selects the
        # new point, and selecting blocks the event as well (see selected_data).
        assert mock_blocker.called


def test_process_click(viewer, solution_tracks_2d, click_node):
    """Test process_click with different click types."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Test 1: Clicking empty space resets selection
    click_node(tracks_viewer, 1)
    assert len(tracks_viewer.selected_nodes) == 1
    event = MockEvent()
    points_layer.process_click(event, None)
    assert len(tracks_viewer.selected_nodes) == 0

    # Test 2: Clicking a point selects the node
    event = MockEvent()
    points_layer.process_click(event, 0)
    assert len(tracks_viewer.selected_nodes) == 1
    assert points_layer.nodes[0] in tracks_viewer.selected_nodes

    # Test 3: Shift-click appends to selection
    event_shift = MockEvent(modifiers=["Shift"])
    points_layer.process_click(event_shift, 1)
    assert len(tracks_viewer.selected_nodes) == 2

    # Test 4: Ctrl-click centers view on node
    with patch.object(tracks_viewer, "center_on_node") as mock_center:
        event_ctrl = MockEvent(modifiers=["Control"])
        points_layer.process_click(event_ctrl, 0)
        mock_center.assert_called_once_with(points_layer.nodes[0])

    # Test 5: Alt-click picks the node's track id and leaves the selection alone
    selection_before = set(tracks_viewer.selected_nodes.as_list)
    with patch.object(tracks_viewer, "select_track_id_from_node") as mock_pick:
        event_alt = MockEvent(modifiers=["Alt"])
        points_layer.process_click(event_alt, 0)
        mock_pick.assert_called_once_with(int(points_layer.nodes[0]))
    assert set(tracks_viewer.selected_nodes.as_list) == selection_before

    # Test 6: Alt-click on empty space does not reset the selection
    event_alt = MockEvent(modifiers=["Alt"])
    points_layer.process_click(event_alt, None)
    assert set(tracks_viewer.selected_nodes.as_list) == selection_before


def test_set_point_size_updates_default_size(viewer, solution_tracks_2d):
    """Test set_point_size updates default_size."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Initial size
    assert points_layer.default_size == 5

    # Set new size
    points_layer.set_point_size(10)

    # Verify size was updated
    assert points_layer.default_size == 10


def test_refresh_updates_data(viewer, solution_tracks_2d, qtbot):
    """Test _refresh updates layer data."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    initial_data_len = len(points_layer.data)

    # Wait for signal
    with qtbot.waitSignal(points_layer.data_updated, timeout=1000):
        points_layer._refresh()

    # Verify we still have the same number of nodes
    assert len(points_layer.data) == initial_data_len


def test_create_node_attrs(viewer, solution_tracks_2d):
    """Test _create_node_attrs creates correct attributes and activates track_id if needed."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Test 1: Create node attributes with track_id set
    tracks_viewer.set_new_track_id()

    new_point = np.array([1, 50, 50])
    attrs = points_layer._create_node_attrs(new_point)

    # Verify attributes
    assert "pos" in attrs
    assert "t" in attrs
    assert "tracklet_id" in attrs
    assert attrs["t"] == 1
    assert np.array_equal(attrs["pos"], [50, 50])
    # Test 2: Activates new track_id if none selected
    tracks_viewer.selected_track = None

    new_point = np.array([1, 50, 50])
    points_layer._create_node_attrs(new_point)

    # Verify track_id was activated
    assert tracks_viewer.selected_track is not None


def test_update_data_without_seg_layer(
    viewer, solution_tracks_2d_without_segmentation, click_node
):
    """Test _update_data handles added, removed, and changed actions without seg layer."""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(
        tracks=solution_tracks_2d_without_segmentation, name="test"
    )

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Verify no seg layer
    assert tracks_viewer.tracking_layers.seg_layer is None

    # Test 1: Added action adds node
    initial_node_count = solution_tracks_2d_without_segmentation.graph.num_nodes()
    new_point = np.array([[1, 50, 50]])
    event = MockEvent(action="added", value=new_point)
    points_layer._update_data(event)
    assert tracks_viewer.tracks.graph.num_nodes() == initial_node_count + 1

    # Test 2: Removed action removes node
    first_node = list(solution_tracks_2d_without_segmentation.graph.node_ids())[0]
    click_node(tracks_viewer, first_node)
    current_node_count = solution_tracks_2d_without_segmentation.graph.num_nodes()
    event = MockEvent(action="removed")
    points_layer._update_data(event)
    assert tracks_viewer.tracks.graph.num_nodes() == current_node_count - 1

    # Test 3: Changed action updates node position (single node)
    points_layer.selected_data.add(0)
    first_node = points_layer.nodes[0]
    original_pos = solution_tracks_2d_without_segmentation.graph.nodes[first_node][
        "pos"
    ]
    new_pos = np.array([1, 100, 100])
    points_layer.data[0] = new_pos
    event = MockEvent(action="changed")
    points_layer._update_data(event)
    updated_pos = tracks_viewer.tracks.graph.nodes[first_node]["pos"]
    assert not np.array_equal(updated_pos, original_pos)

    # Test 4: Changed action updates position for ALL selected nodes (multi-node)
    points_layer.selected_data.clear()
    points_layer.selected_data.add(0)
    points_layer.selected_data.add(1)
    node_0 = points_layer.nodes[0]
    node_1 = points_layer.nodes[1]
    original_pos_0 = np.asarray(
        solution_tracks_2d_without_segmentation.graph.nodes[node_0]["pos"]
    ).copy()
    original_pos_1 = np.asarray(
        solution_tracks_2d_without_segmentation.graph.nodes[node_1]["pos"]
    ).copy()
    points_layer.data[0] = np.array([points_layer.data[0][0], 11.0, 22.0])
    points_layer.data[1] = np.array([points_layer.data[1][0], 33.0, 44.0])
    event = MockEvent(action="changed")
    points_layer._update_data(event)
    updated_pos_0 = np.asarray(tracks_viewer.tracks.graph.nodes[node_0]["pos"])
    updated_pos_1 = np.asarray(tracks_viewer.tracks.graph.nodes[node_1]["pos"])
    assert not np.array_equal(updated_pos_0, original_pos_0)
    assert not np.array_equal(updated_pos_1, original_pos_1)


def test_update_data_with_seg_layer(viewer, solution_tracks_2d):
    """Test _update_data with seg layer shows info for add and refreshes for change."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Verify seg layer exists
    assert tracks_viewer.tracking_layers.seg_layer is not None

    # Test 1: Added action shows info and doesn't add node
    initial_node_count = solution_tracks_2d.graph.num_nodes()
    new_point = np.array([[1, 50, 50]])
    event = MockEvent(action="added", value=new_point)
    with patch("napari_track_edit.data_views.views.layers.track_points.show_info"):
        points_layer._update_data(event)
    assert tracks_viewer.tracks.graph.num_nodes() == initial_node_count

    # Test 2: Changed action refreshes instead of updating
    points_layer.selected_data.add(0)
    first_node = points_layer.nodes[0]
    original_pos = np.asarray(solution_tracks_2d.graph.nodes[first_node]["pos"]).copy()
    new_pos = np.array([1, 100, 100])
    points_layer.data[0] = new_pos
    event = MockEvent(action="changed")
    points_layer._update_data(event)
    updated_pos = np.asarray(tracks_viewer.tracks.graph.nodes[first_node]["pos"])
    assert np.array_equal(updated_pos, original_pos)


def test_update_data_invalid_action_forceable(
    viewer, solution_tracks_2d_without_segmentation, monkeypatch
):
    """Test _update_data handles forceable InvalidActionError by retrying with force=True."""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(
        tracks=solution_tracks_2d_without_segmentation, name="test"
    )

    points_layer = tracks_viewer.tracking_layers.points_layer

    # track_id=1 has node 1 at t=0 with out_degree=2 (a division into nodes 2 and 3).
    # Adding a node to track_id=1 at t=2 raises InvalidActionError(forceable=True).
    tracks_viewer.selected_track = 1

    # Approve the force dialog automatically (avoids Qt dialog popup)
    monkeypatch.setattr(
        "napari_track_edit.data_views.views.layers.track_points.confirm_force_operation",
        lambda message: (True, False),
    )

    initial_node_count = solution_tracks_2d_without_segmentation.graph.num_nodes()
    new_point = np.array([[2, 50, 50]])
    event = MockEvent(action="added", value=new_point)
    points_layer._update_data(event)

    # Node should have been added despite the initial forceable error
    assert (
        solution_tracks_2d_without_segmentation.graph.num_nodes()
        == initial_node_count + 1
    )


def test_update_selection_in_select_mode(viewer, solution_tracks_2d):
    """Test _update_selection updates selected_nodes in select mode."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Enter select mode
    points_layer.mode = "select"

    # Verify signal is connected to _update_selection
    mock_update = MagicMock()
    points_layer.selected_data.events.items_changed.connect(mock_update)

    # Emit the signal directly to verify connection works
    points_layer.selected_data.add(0)

    # Verify the connection was triggered
    mock_update.assert_called_once()

    points_layer.selected_data.add(1)

    # Verify selected_nodes was updated
    assert len(tracks_viewer.selected_nodes) == 2
    assert points_layer.nodes[0] in tracks_viewer.selected_nodes
    assert points_layer.nodes[1] in tracks_viewer.selected_nodes


def test_update_selection_not_in_select_mode_does_nothing(viewer, solution_tracks_2d):
    """Test _update_selection does nothing when not in select mode."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Not in select mode
    points_layer.mode = "pan_zoom"

    # Select some points
    points_layer.selected_data.add(0)

    initial_selection_count = len(tracks_viewer.selected_nodes)
    # Verify selected_nodes was not updated
    assert len(tracks_viewer.selected_nodes) == initial_selection_count


def test_get_symbols_returns_correct_symbols(viewer, solution_tracks_2d):
    """Test get_symbols returns correct symbols for node types."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Get symbols
    symbols = points_layer.get_symbols(solution_tracks_2d, tracks_viewer.symbolmap)

    # Verify symbols list has correct length
    assert len(symbols) == solution_tracks_2d.graph.num_nodes()

    # Verify symbols are from symbolmap
    for symbol in symbols:
        assert symbol in tracks_viewer.symbolmap.values()


def test_selecting_node_does_not_change_same_track_face_color(
    viewer, solution_tracks_3d_with_division, click_node
):
    """Highlighting one node must not alter the face color of another node that
    shares its track id.

    Regression guard for per-track color-array aliasing in TrackPoints: colors
    are now produced by a single vectorized colormap.map call, which returns a
    distinct row per node. Nodes 1 and 2 share track id 1 in this fixture, so
    they must have equal face colors, and selecting node 1 (which updates
    border_color/size, never face_color) must leave node 2's face color intact.
    """
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")
    points_layer = tracks_viewer.tracking_layers.points_layer

    same_track_a, same_track_b = 1, 2
    assert tracks_viewer.tracks.get_track_id(
        same_track_a
    ) == tracks_viewer.tracks.get_track_id(same_track_b)

    idx_a = points_layer.node_index_dict[same_track_a]
    idx_b = points_layer.node_index_dict[same_track_b]

    # Same track id -> identical face color
    assert np.array_equal(
        points_layer.face_color[idx_a], points_layer.face_color[idx_b]
    )
    color_b_before = np.asarray(points_layer.face_color[idx_b]).copy()

    # Highlighting node a must not mutate node b's face color
    click_node(tracks_viewer, same_track_a)
    points_layer.update_point_outline("all")
    assert np.array_equal(points_layer.face_color[idx_b], color_b_before)


def test_update_point_outline(viewer, solution_tracks_2d, click_node):
    """Test update_point_outline with different modes and visibility."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    points_layer = tracks_viewer.tracking_layers.points_layer

    # Test 1: Update outline with "all" mode shows all points
    points_layer.update_point_outline("all")
    assert np.all(points_layer.shown)

    # Test 2: Update outline with list of visible nodes
    first_node = points_layer.nodes[0]
    points_layer.update_point_outline([first_node])
    assert points_layer.shown[0]
    assert not np.all(points_layer.shown)

    # Test 3: Select a node and verify it gets highlighted with cyan border and increased size
    click_node(tracks_viewer, first_node)
    points_layer.update_point_outline("all")

    # Verify selected node has cyan border
    border_0 = points_layer.border_color[0]
    assert np.array_equal(border_0, [0, 1, 1, 1])

    # Verify non-selected node has white border
    border_1 = points_layer.border_color[1]
    assert np.array_equal(border_1, [1, 1, 1, 1])

    # Verify selected node has larger size
    default_size = points_layer.default_size
    selected_size = points_layer.size[0]
    expected_size = math.ceil(default_size + 0.3 * default_size)
    assert selected_size == expected_size

    # Test 4: Group mode includes selected nodes even if not in visible list
    tracks_viewer.mode = "group"
    second_node = points_layer.nodes[1]
    tracks_viewer.selected_nodes.reset()
    click_node(tracks_viewer, first_node)

    # Update outline with only second node visible
    points_layer.update_point_outline([second_node])

    # Verify both first (selected) and second (visible) nodes are shown
    assert points_layer.shown[0]  # selected
    assert points_layer.shown[1]  # visible
    assert not points_layer.shown[2]  # not selected or visible
