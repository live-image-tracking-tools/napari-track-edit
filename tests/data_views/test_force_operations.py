"""Tests for force operations functionality in user interactions.

This module tests the force option dialog and the force parameter behavior
when performing operations like adding nodes and edges that would normally fail due to
conflicts.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest
from qtpy.QtWidgets import QMessageBox

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.data_views.views_coordinator.user_dialogs import (
    confirm_force_operation,
)


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


class MockEvent:
    def __init__(self, value):
        self.value = value


def create_event_val(
    tp: int, z: tuple[int], y: tuple[int], x: tuple[int], old_val: int, target_val: int
) -> list[
    tuple[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray, int]
]:
    """Create event values to simulate a paint event"""

    # construct coordinate lists
    z = np.arange(z[0], z[1])
    y = np.arange(y[0], y[1])
    x = np.arange(x[0], x[1])

    # Create all combinations of x, y, z indices
    Z, Y, X = np.meshgrid(z, y, x, indexing="ij")

    # Flatten to 1D
    tp_idx = np.full(X.size, tp)
    z_idx = Z.ravel()
    y_idx = Y.ravel()
    x_idx = X.ravel()

    old_vals = np.full_like(tp_idx, old_val, dtype=np.uint16)

    # create the event value
    event_val = [
        (
            (
                tp_idx,
                z_idx,
                y_idx,
                x_idx,
            ),  # flattened coordinate arrays, all same length
            old_vals,  # same length, pretend that it is equal to old_val
            target_val,  # new value, will be overwritten
        )
    ]

    return event_val


@pytest.mark.parametrize(
    "button_index, expected",
    [
        (0, (True, True)),  # Yes, always
        (1, (True, False)),  # Yes
        (2, (False, False)),  # No
    ],
)
def test_confirm_force_operation_all_buttons(
    qtbot, monkeypatch, button_index, expected
):
    """Test confirm_force_operation for each button and print which was clicked."""

    clicked_texts = []  # Store clicked button labels for printing

    def mock_exec(self):
        # Simulate clicking one of the buttons based on param
        self._clicked_button = self.buttons()[button_index]
        clicked_texts.append(self._clicked_button.text())
        return 0

    # Patch QMessageBox behavior
    monkeypatch.setattr(QMessageBox, "exec_", mock_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self._clicked_button)

    # Run the dialog under test
    force, always_force = confirm_force_operation("Test operation conflict")

    # Print results
    print(f"Simulated click on: '{clicked_texts[0]}' → Returned: {force, always_force}")

    # Verify correctness
    assert (force, always_force) == expected


@pytest.mark.parametrize(
    "confirm_response, expect_force_retry",
    [
        ((True, True), True),  # User clicks "Yes, always"
        ((True, False), True),  # User clicks "Yes"
        ((False, False), False),  # User clicks "No"
    ],
)
def test_on_paint_invalid_action_upstream_division1_forceable(
    viewer,
    solution_tracks_3d_with_division,
    monkeypatch,
    confirm_response,
    expect_force_retry,
):
    """Test paint event processing

    1) Paint with a the track_id (3) of node 4, at the time point of node 2. This is
        technically invalid, because node 2 has already divided upstream. Therefore, the
        force dialog should pop up.

    2) (Control) Setting tracks_viewer.selected_track to None should allow painting with
        a new track_id, therefore, no InvalidActionError should be raised, and no dialog
        should be triggered.


    TP
    0      1                   1            Control:        1                1
           |                   |                            |                |
    1      2       -1->        2   5                        2       -2->     2    5
          / \\     (force)    /    |                       / \\             / \
    2    3   4               3     4                      3   4            3   4

    """

    # Create example tracks
    tracks = solution_tracks_3d_with_division
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")

    ### 1) Simulate paint event with new label
    tracks_viewer.tracking_layers.seg_layer.mode = "paint"
    step = list(
        viewer.dims.current_step
    )  # make sure the viewer is at the correct dims step
    step[0] = 1
    viewer.dims.current_step = step
    tracks_viewer.selected_track = 3

    # use random target_value, will be overwritten automatically to ensure valid label
    event_val = create_event_val(
        tp=1, z=(15, 18), y=(45, 48), x=(1, 3), old_val=0, target_val=5
    )
    event = MockEvent(event_val)

    seg_layer = tracks_viewer.tracking_layers.seg_layer
    initial_node_count = tracks.graph.num_nodes()

    # Mock the confirm_force_operation dialog
    monkeypatch.setattr(
        "motile_tracker.data_views.views.layers.track_labels.confirm_force_operation",
        lambda message: confirm_response,
    )

    # Mock undo and refresh (keeping these mocks as they test UI behavior, not UserActions)
    parent_class = seg_layer.__class__.__mro__[1]
    undo_mock = MagicMock(name="undo")
    monkeypatch.setattr(parent_class, "undo", undo_mock)
    seg_layer._refresh = MagicMock()
    seg_layer.tracks_viewer.force = False

    # Set selected_label to a value not in the graph so _ensure_valid_label does not
    # override selected_track (track_id=3 is the track of node 4 at t=2).
    seg_layer.selected_label = max(tracks.graph.node_ids()) + 1  # = 5

    seg_layer._on_paint(event)

    # Verify graph state based on user's choice
    if expect_force_retry:
        # Force retry succeeded: node 5 added
        assert tracks.graph.num_nodes() == initial_node_count + 1
        assert seg_layer.tracks_viewer.force == confirm_response[1]
    else:
        # User declined force: graph unchanged
        assert tracks.graph.num_nodes() == initial_node_count
    # In both error paths: super().undo() is called before force retry or decline;
    # _refresh is called (via tracks.refresh signal after success, or explicitly on decline)
    undo_mock.assert_called_once()
    seg_layer._refresh.assert_called_once()

    ### 2) Control case (no dialog triggered)
    # Reset mocks
    undo_mock.reset_mock()
    seg_layer._refresh.reset_mock()

    # Control condition: no track selected → new track, no division conflict
    tracks_viewer.selected_track = None
    node_count_before_section2 = tracks.graph.num_nodes()
    seg_layer.selected_label = (
        max(tracks.graph.node_ids()) + 1
    )  # fresh label not in graph

    seg_layer._on_paint(event)

    # No error branch triggered: node was added successfully via tracks.refresh signal
    assert tracks.graph.num_nodes() == node_count_before_section2 + 1
    undo_mock.assert_not_called()
    seg_layer._refresh.assert_called_once()


@pytest.mark.parametrize(
    "confirm_response, expect_force_retry",
    [
        ((True, True), True),  # User clicks "Yes, always"
        ((True, False), True),  # User clicks "Yes"
        ((False, False), False),  # User clicks "No"
    ],
)
def test_on_paint_invalid_action_upstream_division2_forceable(
    viewer,
    solution_tracks_3d_with_division,
    monkeypatch,
    confirm_response,
    expect_force_retry,
):
    """Test paint event processing

    1) Paint with the track_id of node 2 at time point 2. This is invalid, because node 2
        has already divided at time point 1.

    2) (Control) Setting tracks_viewer.selected_track to None should allow painting with
        a new track_id.

    0      1                   1            Control:        1                1
           |                   |                            |                |
    1      2       -1->        2                            2       -2->     2
          / \\     (force)      |                           / \\              / \
    2    3   4              3  5  4                       3   4            3   4  5

    """

    # Create example tracks
    tracks = solution_tracks_3d_with_division
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")

    ### 1) Simulate paint event with new label
    tracks_viewer.tracking_layers.seg_layer.mode = "paint"
    step = list(
        viewer.dims.current_step
    )  # make sure the viewer is at the correct dims step
    step[0] = 2
    viewer.dims.current_step = step
    tracks_viewer.selected_track = 1

    # use random target_value, will be overwritten automatically to ensure valid label
    event_val = create_event_val(
        tp=2, z=(15, 18), y=(45, 48), x=(1, 3), old_val=0, target_val=5
    )
    event = MockEvent(event_val)

    seg_layer = tracks_viewer.tracking_layers.seg_layer
    initial_node_count = tracks.graph.num_nodes()

    # Mock the confirm_force_operation dialog
    monkeypatch.setattr(
        "motile_tracker.data_views.views.layers.track_labels.confirm_force_operation",
        lambda message: confirm_response,
    )

    # Mock undo and refresh (keeping these mocks as they test UI behavior, not UserActions)
    parent_class = seg_layer.__class__.__mro__[1]
    undo_mock = MagicMock(name="undo")
    monkeypatch.setattr(parent_class, "undo", undo_mock)
    seg_layer._refresh = MagicMock()
    seg_layer.tracks_viewer.force = False

    # Set selected_label to a value not in the graph so _ensure_valid_label does not
    # override selected_track (track_id=1 is the track of nodes 1 and 2).
    seg_layer.selected_label = max(tracks.graph.node_ids()) + 1  # = 5

    seg_layer._on_paint(event)

    # Verify graph state based on user's choice
    if expect_force_retry:
        # Force retry succeeded: node 5 added
        assert tracks.graph.num_nodes() == initial_node_count + 1
        assert seg_layer.tracks_viewer.force == confirm_response[1]
    else:
        # User declined force: graph unchanged
        assert tracks.graph.num_nodes() == initial_node_count
    # In both error paths: super().undo() is called before force retry or decline;
    # _refresh is called (via tracks.refresh signal after success, or explicitly on decline)
    undo_mock.assert_called_once()
    seg_layer._refresh.assert_called_once()

    ### 2) Control case (no dialog triggered)
    # Reset mocks
    undo_mock.reset_mock()
    seg_layer._refresh.reset_mock()

    # Control condition: no track selected → new track, no division conflict
    tracks_viewer.selected_track = None
    node_count_before_section2 = tracks.graph.num_nodes()
    seg_layer.selected_label = (
        max(tracks.graph.node_ids()) + 1
    )  # fresh label not in graph

    seg_layer._on_paint(event)

    # No error branch triggered: node was added successfully via tracks.refresh signal
    assert tracks.graph.num_nodes() == node_count_before_section2 + 1
    undo_mock.assert_not_called()
    seg_layer._refresh.assert_called_once()


@pytest.mark.parametrize(
    "confirm_response, expect_force_retry",
    [
        ((True, True), True),  # User clicks “Yes, always”
        ((True, False), True),  # User clicks “Yes”
        ((False, False), False),  # User clicks “No”
    ],
)
def test_invalid_edge_force(
    viewer,
    solution_tracks_3d_with_division,
    monkeypatch,
    confirm_response,
    expect_force_retry,
    click_node,
):
    r"""Test paint event processing

    1) Add a new, disconnected node (5)
    2) Create an edge between node 5 and 4. This is invalid, because 4 already has an
        incoming edge. Therefore, the force dialog should be triggered.

    TP
    0      1                   1                   1
           |                   |                   |
    1      2       -1->        2    5   -2->       2   5
          / \                 / \      (force)     |   |
    2    3   4               3   4                 3   4


    """

    # Create example tracks
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    ### 1) Simulate paint event with new label
    tracks_viewer.tracking_layers.seg_layer.mode = "paint"
    step = list(
        viewer.dims.current_step
    )  # make sure the viewer is at the correct dims step
    step[0] = 1
    viewer.dims.current_step = step
    tracks_viewer.selected_track = None  # paint with a new track_id

    # use random target_value, will be overwritten automatically to ensure valid label
    event_val = create_event_val(
        tp=1, z=(15, 17), y=(45, 47), x=(75, 78), old_val=0, target_val=5
    )
    event = MockEvent(event_val)
    assert tracks_viewer.tracks.graph.num_nodes() == 4  # 4 nodes before the paint event
    tracks_viewer.tracking_layers.seg_layer._on_paint(event)
    assert tracks_viewer.tracks.graph.num_nodes() == 5  # 5 nodes after the paint event

    ### 2) Add an invalid edge and verify that the dialog was called
    # Node 4 already has an incoming edge from node 2, so adding 5→4 raises
    # InvalidActionError(forceable=True) without any mocking needed.
    # Reset selection first: the paint auto-selected node 5, so clicking it
    # again would toggle it off via NodeSelectionList's toggle behavior.
    tracks_viewer.selected_nodes.reset()
    click_node(tracks_viewer, 5)
    click_node(tracks_viewer, 4, append=True)
    tracks_viewer.force = False

    monkeypatch.setattr(
        "motile_tracker.data_views.views_coordinator.tracks_viewer.confirm_force_operation",
        lambda message: confirm_response,
    )

    tracks_viewer.connect_nodes()

    if expect_force_retry:
        assert solution_tracks_3d_with_division.graph.has_edge(5, 4)
        assert not solution_tracks_3d_with_division.graph.has_edge(2, 4)
    else:
        assert not solution_tracks_3d_with_division.graph.has_edge(5, 4)
        assert solution_tracks_3d_with_division.graph.has_edge(2, 4)
    assert tracks_viewer.force == confirm_response[1]


def test_connect_third_daughter_is_forceable(
    viewer,
    solution_tracks_3d_with_division,
    monkeypatch,
    click_node,
):
    r"""Connecting a third daughter to a parent that already has 2 children conflicts
    with the existing daughter edges, so the force dialog is shown. Forcing removes
    both existing daughter edges.

    TP
    0      1                       1                     1
           |                       |                     |
    1      2          ->           2          -force->    2   3   4
          / \                     / \                     \
    2    3   4                   3   4    5                 5

    """
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    # Paint a new disconnected node 5 at t=2 (new track_id)
    tracks_viewer.tracking_layers.seg_layer.mode = "paint"
    step = list(viewer.dims.current_step)
    step[0] = 2
    viewer.dims.current_step = step
    tracks_viewer.selected_track = None

    event_val = create_event_val(
        tp=2, z=(15, 17), y=(45, 47), x=(75, 78), old_val=0, target_val=5
    )
    tracks_viewer.tracking_layers.seg_layer._on_paint(MockEvent(event_val))
    assert tracks_viewer.tracks.graph.num_nodes() == 5
    assert tracks_viewer.tracks.graph.out_degree(2) == 2

    # Select parent (2) and would-be third daughter (5)
    tracks_viewer.selected_nodes.reset()
    click_node(tracks_viewer, 2)
    click_node(tracks_viewer, 5, append=True)
    tracks_viewer.force = False

    # 1) Declining the force dialog leaves the graph untouched
    monkeypatch.setattr(
        "motile_tracker.data_views.views_coordinator.tracks_viewer."
        "confirm_force_operation",
        lambda message: (False, False),
    )
    num_edges_before = tracks_viewer.tracks.graph.num_edges()
    tracks_viewer.connect_nodes()

    assert tracks_viewer.tracks.graph.num_edges() == num_edges_before
    assert not tracks_viewer.tracks.graph.has_edge(2, 5)
    assert tracks_viewer.tracks.graph.has_edge(2, 3)
    assert tracks_viewer.tracks.graph.has_edge(2, 4)

    # 2) Accepting it breaks both conflicting daughter edges and adds the new one
    monkeypatch.setattr(
        "motile_tracker.data_views.views_coordinator.tracks_viewer."
        "confirm_force_operation",
        lambda message: (True, False),
    )
    tracks_viewer.connect_nodes()

    assert tracks_viewer.tracks.graph.has_edge(2, 5)
    assert not tracks_viewer.tracks.graph.has_edge(2, 3)
    assert not tracks_viewer.tracks.graph.has_edge(2, 4)


def test_connect_horizontal_nodes_blocked(
    viewer,
    solution_tracks_3d_with_division,
    monkeypatch,
    click_node,
):
    """Connecting two nodes in the same time point can never be forced, so a plain
    warning is shown and the graph is left unchanged."""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    # Nodes 3 and 4 are the two daughters of node 2, both at t=2
    tracks_viewer.selected_nodes.reset()
    click_node(tracks_viewer, 3)
    click_node(tracks_viewer, 4, append=True)

    warning_mock = MagicMock(return_value=QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", warning_mock)
    confirm_mock = MagicMock()
    monkeypatch.setattr(
        "motile_tracker.data_views.views_coordinator.tracks_viewer."
        "confirm_force_operation",
        confirm_mock,
    )

    num_edges_before = tracks_viewer.tracks.graph.num_edges()
    tracks_viewer.connect_nodes()

    warning_mock.assert_called_once()
    assert "Cannot connect nodes" in warning_mock.call_args.args[1]
    confirm_mock.assert_not_called()  # never offered as a forceable action
    assert tracks_viewer.tracks.graph.num_edges() == num_edges_before
