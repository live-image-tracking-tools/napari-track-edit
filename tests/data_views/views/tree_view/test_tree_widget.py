"""Tests for TreeWidget - the lineage tree visualization widget.

Tests cover TreePlot data display, node selection, keyboard shortcuts,
mode switching, and integration with TracksViewer.
"""

import gc
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from qtpy.QtCore import Qt

from motile_tracker.data_views.views.tree_view.navigation_widget import (
    NavigationWidget,
)
from motile_tracker.data_views.views.tree_view.tree_widget import TreeWidget
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

# TreeWidget builds the fastplotlib/wgpu tree canvas. On headless Linux CI wgpu
# aborts (SIGABRT) constructing the Qt canvas figure, killing the whole pytest
# process. These are covered on macOS (Metal) and Windows (DX12); skip on Linux.
pytestmark = pytest.mark.skipif(
    sys.platform == "linux",
    reason="fastplotlib/wgpu can't build a Qt canvas on headless Linux CI",
)


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


def test_tree_plot_initialization_and_update(viewer, solution_tracks_2d):
    """Test TreePlot initialization, signals, and update method."""
    # Need napari viewer context for Qt initialization
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)
    tree_plot = tree_widget.tree_widget

    # Test 1: Initialization
    assert tree_plot is not None
    # after loading data the scatter + edges exist and positions are populated
    assert tree_plot._scatter is not None
    assert len(tree_plot._positions) > 0
    assert tree_plot._edges is not None  # edges from graph_2d
    assert tree_plot.view_direction == "vertical"

    # Test 2: Signals
    assert hasattr(tree_plot, "node_clicked")
    assert hasattr(tree_plot, "jump_to_node")
    assert hasattr(tree_plot, "nodes_selected")

    # Test 3: Update with all parameters
    track_df = tree_widget.tracks_viewer.track_df
    tree_widget.tree_widget.update(
        track_df=track_df,
        view_direction="horizontal",
        plot_type="tree",
        feature=None,
        selected_nodes=[1, 2],
        reset_view=True,
        allow_flip=False,
    )
    assert tree_widget.tree_widget.view_direction == "horizontal"


def test_tree_plot_data_display(viewer, solution_tracks_2d):
    """Test TreePlot data display with empty data, track data, and view directions."""
    tree_widget = TreeWidget(viewer)
    tree_plot = tree_widget.tree_widget

    # Test 1: Empty DataFrame -> nothing rendered
    empty_df = pd.DataFrame()
    tree_plot.update(empty_df, "vertical", "tree", None, [])
    assert tree_plot._scatter is None
    assert len(tree_plot._node_ids) == 0

    # Test 2: Actual track data
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    # Create new tree_widget after loading data
    tree_widget = TreeWidget(viewer)
    tree_plot = tree_widget.tree_widget

    # Verify data was loaded
    assert len(tree_plot._positions) > 0
    assert len(tree_plot._node_ids) > 0

    # Test 3: Vertical view direction
    tree_plot.set_view("vertical", "tree")
    assert tree_plot.view_direction == "vertical"

    # Test 4: Horizontal view direction
    tree_plot.set_view("horizontal", "tree")
    assert tree_plot.view_direction == "horizontal"


def test_tree_plot_selection(viewer, solution_tracks_2d):
    """Test set_selection with empty list and rectangle (box) selection signal."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)
    tree_plot = tree_widget.tree_widget

    # Test 1: setting selection with an empty list should not raise
    tree_plot.set_selection([], "tree")

    # Test 2: a box-select covering all nodes emits nodes_selected with those ids.
    # (select_points_in_rect takes x0, x1, y0, y1 and only emits when non-empty;
    # it emits synchronously, so a direct connect capture is enough.)
    received = []
    tree_plot.nodes_selected.connect(lambda nodes, append: received.append(nodes))
    xs, ys = tree_plot._positions[:, 0], tree_plot._positions[:, 1]
    tree_plot.select_points_in_rect(
        xs.min() - 1, xs.max() + 1, ys.min() - 1, ys.max() + 1
    )
    assert received, "nodes_selected should have been emitted for a covering box"
    assert len(received[0]) == len(tree_plot._node_ids)


def test_centering(viewer, solution_tracks_2d):
    """Test centering on nodes via the fastplotlib camera."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)
    tree_plot = tree_widget.tree_widget
    cam = tree_plot._subplot.camera

    def node_pos(node_id):
        row = tree_plot._id_to_row[node_id]
        return tree_plot._positions[row, 0], tree_plot._positions[row, 1]

    def in_view(x, y):
        st = cam.get_state()
        cx, cy = st["position"][0], st["position"][1]
        w, h = st["width"], st["height"]
        return (cx - w / 2 <= x <= cx + w / 2) and (cy - h / 2 <= y <= cy + h / 2)

    # Test 1: centering on a node that doesn't exist should not raise
    tree_plot.center_on_node(999)

    # Test 2: move the camera far from a node, then center -> it comes into view
    node_x, node_y = node_pos(1)
    st = dict(cam.get_state())
    st["position"] = (node_x + 1000, node_y + 1000, st["position"][2])
    st["width"], st["height"] = 10, 10
    cam.set_state(st)
    assert not in_view(node_x, node_y), "node should start outside the view"

    tree_plot.center_on_node(1)
    assert in_view(node_x, node_y), "node should be in view after center_on_node"

    # Test 3: centering again is a no-op when the node is already in view
    before = tuple(cam.get_state()["position"])
    tree_plot.center_on_node(1)
    after = tuple(cam.get_state()["position"])
    assert before == after, "camera should not move when node is already visible"

    # Test 4: selecting multiple nodes centers on their range without error
    tree_plot.set_selection([1, 2, 3], "tree")


def test_adding_a_visible_node_to_the_selection_keeps_the_zoom(
    viewer, solution_tracks_2d
):
    """Shift-clicking a node that is already on screen must not reframe the view.

    Picking a run of nodes by hand means adding them one by one while zoomed in; if
    every addition zoomed out far enough to also fit the nodes selected earlier (which
    may have been panned off screen since), the user would have to zoom back in for
    each click. A selection that lands off screen must still be brought into view.
    """
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)
    tree_plot = tree_widget.tree_widget
    cam = tree_plot._subplot.camera

    node_ids = [int(n) for n in tree_plot._node_ids]
    rows = tree_plot._positions

    # zoom in tightly on the first node, with a second node just inside the view
    first, second = node_ids[0], node_ids[1]
    tree_plot.set_selection([first], "tree")
    pts = rows[[tree_plot._id_to_row[first], tree_plot._id_to_row[second]]]
    st = dict(cam.get_state())
    st["position"] = (pts[:, 0].mean(), pts[:, 1].mean(), st["position"][2])
    st["width"] = max(1.0, (np.ptp(pts[:, 0]) + 1) * 1.5)
    st["height"] = max(1.0, (np.ptp(pts[:, 1]) + 1) * 1.5)
    cam.set_state(st)
    before = cam.get_state()

    tree_plot.set_selection([first, second], "tree")
    after = cam.get_state()
    assert tuple(after["position"]) == tuple(before["position"])
    assert (after["width"], after["height"]) == (before["width"], before["height"])

    # ...but a node outside the view (e.g. the far end of a broken edge) still pulls
    # the camera out far enough to show it
    far = max(node_ids, key=lambda n: abs(rows[tree_plot._id_to_row[n], 1]))
    if not tree_plot._rows_fit([tree_plot._id_to_row[far]]):
        tree_plot.set_selection([first, far], "tree")
        assert cam.get_state()["height"] > before["height"]


def test_tree_widget_initialization(viewer, solution_tracks_2d):
    """Test TreeWidget initialization without and with tracks."""

    # Test 1: Basic initialization
    tree_widget = TreeWidget(viewer)

    assert tree_widget is not None
    assert tree_widget.mode == "all"
    assert tree_widget.plot_type == "tree"
    assert tree_widget.view_direction == "vertical"
    assert hasattr(tree_widget, "tree_widget")
    assert hasattr(tree_widget, "mode_widget")
    assert hasattr(tree_widget, "plot_type_widget")
    assert hasattr(tree_widget, "navigation_widget")
    assert hasattr(tree_widget, "flip_widget")

    # Test 2: Initialization with tracks loaded
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget_with_tracks = TreeWidget(viewer)

    assert not tree_widget_with_tracks.tracks_viewer.track_df.empty
    assert tree_widget_with_tracks.graph is not None


@patch.object(NavigationWidget, "move")
def test_keyboard_shortcuts_all(mock_move, viewer, solution_tracks_2d, qtbot):
    """Test all keyboard shortcuts including standard keys, releases, arrows, and toggles."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    # Mock all methods
    delete_mock = MagicMock()
    tracks_viewer.delete_node = delete_mock
    create_edge_mock = MagicMock()
    tracks_viewer.create_edge = create_edge_mock
    delete_edge_mock = MagicMock()
    tracks_viewer.delete_edge = delete_edge_mock
    swap_mock = MagicMock()
    tracks_viewer.swap_nodes = swap_mock
    undo_mock = MagicMock()
    tracks_viewer.undo = undo_mock
    redo_mock = MagicMock()
    tracks_viewer.redo = redo_mock

    tree_widget = TreeWidget(viewer)

    # Test 1: D key calls delete_node
    qtbot.keyPress(tree_widget, Qt.Key_D)
    delete_mock.assert_called_once()

    # Test 2: A key calls create_edge
    qtbot.keyPress(tree_widget, Qt.Key_A)
    create_edge_mock.assert_called_once()

    # Test 3: B key calls delete_edge
    qtbot.keyPress(tree_widget, Qt.Key_B)
    delete_edge_mock.assert_called_once()

    # Test 4: S key calls swap_nodes
    qtbot.keyPress(tree_widget, Qt.Key_S)
    swap_mock.assert_called_once()

    # Test 5: Z key calls undo
    qtbot.keyPress(tree_widget, Qt.Key_Z)
    undo_mock.assert_called_once()

    # Test 6: R key calls redo
    qtbot.keyPress(tree_widget, Qt.Key_R)
    redo_mock.assert_called_once()

    # Test 7: F key flips axes
    initial_direction = tree_widget.view_direction
    qtbot.keyPress(tree_widget, Qt.Key_F)
    assert tree_widget.view_direction != initial_direction

    # Test 8: X key release re-enables mouse in both directions
    qtbot.keyPress(tree_widget, Qt.Key_X)
    qtbot.keyRelease(tree_widget, Qt.Key_X)

    # Test 9: Y key release re-enables mouse in both directions
    qtbot.keyPress(tree_widget, Qt.Key_Y)
    qtbot.keyRelease(tree_widget, Qt.Key_Y)

    # Test 10: All arrow keys call navigation widget move method
    qtbot.keyPress(tree_widget, Qt.Key_Left)
    mock_move.assert_called_with("left")

    qtbot.keyPress(tree_widget, Qt.Key_Right)
    mock_move.assert_called_with("right")

    qtbot.keyPress(tree_widget, Qt.Key_Up)
    mock_move.assert_called_with("up")

    qtbot.keyPress(tree_widget, Qt.Key_Down)
    mock_move.assert_called_with("down")

    # Test 11: Q key toggles display mode
    with patch.object(tree_widget.mode_widget, "_toggle_display_mode") as mock_toggle:
        qtbot.keyPress(tree_widget, Qt.Key_Q)
        mock_toggle.assert_called_once()

    # Test 12: W key toggles feature mode
    with patch.object(tree_widget.plot_type_widget, "_toggle_plot_type") as mock_toggle:
        qtbot.keyPress(tree_widget, Qt.Key_W)
        mock_toggle.assert_called_once()

    # Test 13: Delete key calls delete_node (alternate key for D)
    delete_mock.reset_mock()
    qtbot.keyPress(tree_widget, Qt.Key_Delete)
    delete_mock.assert_called_once()

    # Test 14: Escape key calls deselect
    deselect_mock = MagicMock()
    tracks_viewer.deselect = deselect_mock
    qtbot.keyPress(tree_widget, Qt.Key_Escape)
    deselect_mock.assert_called_once()

    # Test 15: E key calls restore_selection
    restore_mock = MagicMock()
    tracks_viewer.restore_selection = restore_mock
    qtbot.keyPress(tree_widget, Qt.Key_E)
    restore_mock.assert_called_once()


def test_mode_and_plot_type_switching(viewer, solution_tracks_2d, click_node):
    """Test mode switching, plot type switching, and their interaction."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)

    # Test 1: Setting mode to 'all'
    tree_widget._set_mode("all")
    assert tree_widget.mode == "all"

    # Test 2: Setting mode to 'lineage'
    # Select a node first (use click_node so the ID is np.int64, matching the real UI)
    click_node(tracks_viewer, 1)
    tree_widget._set_mode("lineage")
    assert tree_widget.mode == "lineage"
    assert tree_widget.view_direction == "horizontal"

    # Test 3: Invalid mode raises ValueError
    with pytest.raises(ValueError, match="must be 'all' or 'lineage'"):
        tree_widget._set_mode("invalid")

    # Test 4: Setting plot type to 'tree'
    tree_widget._set_mode("all")  # Reset to all mode
    tree_widget._set_plot_type("tree")
    assert tree_widget.plot_type == "tree"

    # Test 5: Setting plot type to 'feature'
    tree_widget._set_plot_type("feature")
    assert tree_widget.plot_type == "feature"
    assert tree_widget.view_direction == "horizontal"

    # Test 6: Invalid plot type raises ValueError
    with pytest.raises(ValueError, match="must be 'tree' or 'feature'"):
        tree_widget._set_plot_type("invalid")

    # Test 7: Setting mode to 'all' with plot_type='tree' sets vertical view
    tree_widget.plot_type = "tree"
    tree_widget._set_mode("all")
    assert tree_widget.view_direction == "vertical"

    # Test 8: Setting mode to 'all' with plot_type='feature' sets horizontal view
    tree_widget.plot_type = "feature"
    tree_widget._set_mode("all")
    assert tree_widget.view_direction == "horizontal"


def test_lineage_mode_edge_cases(viewer, solution_tracks_2d, click_node):
    """Test lineage mode edge cases with selection changes."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)

    # Test 1: _update_selected in lineage mode doesn't crash
    # Switch to lineage mode with a selection (use click_node so the ID is np.int64,
    # matching the real UI path that produces np.int64 from layer.get_value())
    click_node(tracks_viewer, 1)
    tree_widget._set_mode("lineage")

    # Change selection to a node not in current lineage
    click_node(tracks_viewer, 2)

    # _update_selected should handle this without crashing
    tree_widget._update_selected()

    # Test 2: _update_lineage_df doesn't crash with empty selection
    # Select node and switch to lineage mode
    click_node(tracks_viewer, 1)
    tree_widget._set_mode("lineage")

    # Clear selection but lineage_df still has data
    tracks_viewer.selected_nodes.reset()

    # This should not crash
    tree_widget._update_lineage_df()
    # Test passes if we reach here without exception


def test_tree_widget_integration(viewer, solution_tracks_2d):
    """Test TreeWidget signal response, axis flipping, and mouse controls."""
    tracks_viewer = TracksViewer.get_instance(viewer)

    # Test 1: TreeWidget responds to tracks_updated signal
    tree_widget = TreeWidget(viewer)
    assert tree_widget.tracks_viewer.track_df.empty

    # Update tracks
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    # Verify track_df was updated
    assert not tree_widget.tracks_viewer.track_df.empty

    # Test 2: flip_axes toggles between horizontal and vertical
    # Start with vertical
    assert tree_widget.view_direction == "vertical"

    # Flip to horizontal
    tree_widget.flip_axes()
    assert tree_widget.view_direction == "horizontal"

    # Flip back to vertical
    tree_widget.flip_axes()
    assert tree_widget.view_direction == "vertical"

    # Test 3: set_mouse_enabled changes mouse behavior (should not raise error)
    tree_widget.set_mouse_enabled(x=True, y=False)
    tree_widget.set_mouse_enabled(x=False, y=True)
    tree_widget.set_mouse_enabled(x=True, y=True)


def test_update_track_data_without_reset(viewer, solution_tracks_2d):
    """Test _update_track_data preserves axis_order when reset_view=False."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)

    # Update without reset
    tree_widget._update_track_data(reset_view=False)

    # axis_order should have been passed through
    assert hasattr(tree_widget.tracks_viewer, "axis_order")


def test_update_track_data_with_none_tracks(viewer):
    """Test _update_track_data handles None tracks."""
    tree_widget = TreeWidget(viewer)

    # Update with no tracks
    tree_widget._update_track_data(reset_view=True)

    assert tree_widget.tracks_viewer.track_df.empty
    assert tree_widget.graph is None


def _render_canvas_of(tree_widget):
    """The QRenderWidget that rendercanvas registers for this tree view."""
    figure_canvas = tree_widget.tree_widget._figure.canvas
    return getattr(figure_canvas, "_subwidget", figure_canvas)


def test_cleanup_releases_canvas(viewer, solution_tracks_2d):
    """cleanup() closes the wgpu canvas and releases the graphics it was drawing."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    tree_widget = TreeWidget(viewer)
    canvas = _render_canvas_of(tree_widget)
    assert not canvas.get_closed()
    assert tree_widget.tree_widget._scatter is not None

    tree_widget.cleanup()

    assert tree_widget.tree_widget._closed
    assert canvas.get_closed()
    assert tree_widget.tree_widget._scatter is None  # GPU buffers released

    tree_widget.cleanup()  # idempotent
    # a closed tree view ignores further updates instead of touching a dead canvas
    tree_widget.tree_widget.update(
        tracks_viewer.track_df, "vertical", "tree", None, [], reset_view=True
    )
    tree_widget.tree_widget.set_selection([], "tree")
    tree_widget.tree_widget.center_on_node(1)


def test_deleted_tree_widget_leaves_no_dangling_canvas(viewer):
    """A destroyed tree view must not leave a canvas behind in rendercanvas.

    rendercanvas only drops a canvas from its registry when that canvas reports itself
    closed, and the nested QRenderWidget never receives a Qt close event. Its Python
    wrapper then outlives the deleted C++ widget, and rendercanvas' loop trips over it
    at application exit with "wrapped C/C++ object of type QRenderWidget has been
    deleted".
    """
    from rendercanvas.qt import loop

    tree_widget = TreeWidget(viewer)
    canvas = _render_canvas_of(tree_widget)
    assert canvas in canvas._rc_canvas_group._canvases

    del tree_widget
    gc.collect()

    assert canvas.get_closed()
    # this is what the loop does on QApplication.aboutToQuit
    remaining = loop.get_canvases(close_closed=True)
    assert canvas not in remaining
    for remaining_canvas in remaining:
        getattr(remaining_canvas, "_rc_closed_by_loop", False)
