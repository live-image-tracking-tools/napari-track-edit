import pandas as pd
import pytest
from qtpy.QtWidgets import QApplication

from motile_tracker.data_views.views.table.custom_table_widget import (
    ColoredTableWidget,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.fixture
def setup_tracks_viewer(viewer, solution_tracks_2d):
    """Create a TracksViewer with tracks loaded."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    return viewer, tracks_viewer


@pytest.fixture
def colored_table_widget(qtbot, setup_tracks_viewer):
    viewer, tracks_viewer = setup_tracks_viewer

    # Build dataframe from tracks
    nodes = tracks_viewer.tracks.graph.node_ids()

    df = pd.DataFrame(
        {
            "ID": nodes,
            "value": list(range(len(nodes))),
        }
    )

    tracks_viewer.track_df = df

    widget = ColoredTableWidget(viewer)
    qtbot.addWidget(widget)

    return widget, tracks_viewer


def test_table_population(colored_table_widget):
    widget, _ = colored_table_widget

    table = widget._table_widget

    assert table.model().rowCount() > 0
    assert table.model().columnCount() >= 1


def test_table_selection_updates_tracksviewer(colored_table_widget, qtbot):
    widget, tracks_viewer = colored_table_widget
    table = widget._table_widget

    first_row_node = widget._table["ID"][0]

    with qtbot.waitSignal(tracks_viewer.selected_nodes.selection_updated, timeout=1000):
        table.selectRow(0)

    assert first_row_node in tracks_viewer.selected_nodes.as_list


def test_tracksviewer_selection_updates_table(colored_table_widget, qtbot):
    widget, tracks_viewer = colored_table_widget
    table = widget._table_widget

    # Select first two nodes in viewer
    nodes = widget._table["ID"][:2].tolist()
    tracks_viewer.selected_nodes.add_list(nodes, append=False)

    qtbot.wait(50)

    selected_rows = sorted({index.row() for index in table.selectedIndexes()})

    assert selected_rows == [0, 1]


def test_no_infinite_selection_loop(colored_table_widget, qtbot):
    widget, tracks_viewer = colored_table_widget
    table = widget._table_widget

    spy_count = {"calls": 0}

    def spy():
        spy_count["calls"] += 1

    tracks_viewer.selected_nodes.selection_updated.connect(spy)

    table.selectRow(0)
    qtbot.wait(50)

    assert spy_count["calls"] == 1


def test_center_from_table_triggers_viewer(colored_table_widget, qtbot):
    widget, tracks_viewer = colored_table_widget
    table = widget._table_widget

    index = table.model().index(0, 0)

    with qtbot.waitSignal(tracks_viewer.center_node, timeout=1000):
        widget.center_node(index)


def test_center_from_tracksviewer_scrolls_table(colored_table_widget, qtbot):
    widget, _ = colored_table_widget
    table = widget._table_widget

    # Force small viewport so only 2 rows fit
    row_height = 30
    table.setFixedHeight(row_height * 2)
    for i in range(table.model().rowCount()):
        table.setRowHeight(i, row_height)

    widget.show()
    qtbot.wait(50)
    qtbot.waitExposed(widget)  # Ensure widget is rendered
    qtbot.wait(50)

    table.verticalScrollBar().setValue(0)
    qtbot.wait(50)

    node = widget._table["ID"][5]
    target_row_index = widget._find_row(ID=node)

    # Scroll to node and check that it is visible
    widget.scroll_to_node(node)
    qtbot.wait(50)

    QApplication.processEvents()
    row_rect = table.visualRect(table.model().index(target_row_index, 0))
    viewport_rect = table.viewport().rect()

    assert row_rect.intersects(viewport_rect), (
        "The target row should be visible after scroll"
    )

    assert widget._syncing is False


def test_sort_preserves_functionality(colored_table_widget, qtbot):
    widget, tracks_viewer = colored_table_widget

    widget._sort_table(0)
    qtbot.wait(50)

    # Try selecting again after sort
    widget._table_widget.selectRow(0)
    qtbot.wait(50)

    assert len(tracks_viewer.selected_nodes.as_list) >= 1


def test_table_widget_keybinds(colored_table_widget, qtbot):
    """Test all keyboard shortcuts in the table widget.

    The table widget supports keybinds that are delegated to tracks_viewer:
    - D / Delete: delete_node
    - Shift+A: create_edge
    - B: delete_edge
    - S: swap_nodes
    - Z: undo
    - R / Ctrl+Shift+Z: redo
    - Escape: deselect
    - E: restore_selection
    """
    from unittest.mock import MagicMock

    from qtpy.QtCore import Qt

    widget, tracks_viewer = colored_table_widget
    table_widget = widget._table_widget

    # Set focus to the table widget so it receives key events
    table_widget.setFocus()

    # Mock all tracks_viewer methods to verify they're called
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

    deselect_mock = MagicMock()
    tracks_viewer.deselect = deselect_mock

    restore_mock = MagicMock()
    tracks_viewer.restore_selection = restore_mock

    # Test D key calls delete_node
    qtbot.keyPress(table_widget, Qt.Key_D)
    delete_mock.assert_called_once()

    # Test Delete key also calls delete_node
    delete_mock.reset_mock()
    qtbot.keyPress(table_widget, Qt.Key_Delete)
    delete_mock.assert_called_once()

    # Test Shift+A key calls create_edge
    qtbot.keyPress(table_widget, Qt.Key_A, Qt.KeyboardModifier.ShiftModifier)
    create_edge_mock.assert_called_once()

    # Test B key calls delete_edge
    qtbot.keyPress(table_widget, Qt.Key_B)
    delete_edge_mock.assert_called_once()

    # Test S key calls swap_nodes
    qtbot.keyPress(table_widget, Qt.Key_S)
    swap_mock.assert_called_once()

    # Test Z key calls undo
    qtbot.keyPress(table_widget, Qt.Key_Z)
    undo_mock.assert_called_once()

    # Test R key calls redo
    qtbot.keyPress(table_widget, Qt.Key_R)
    redo_mock.assert_called_once()

    # Test Ctrl+Shift+Z also calls redo
    redo_mock.reset_mock()
    qtbot.keyPress(
        table_widget,
        Qt.Key_Z,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    redo_mock.assert_called_once()

    # Test Escape key calls deselect
    qtbot.keyPress(table_widget, Qt.Key_Escape)
    deselect_mock.assert_called_once()

    # Test E key calls restore_selection
    qtbot.keyPress(table_widget, Qt.Key_E)
    restore_mock.assert_called_once()
