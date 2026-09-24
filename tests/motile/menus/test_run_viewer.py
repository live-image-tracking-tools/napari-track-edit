from unittest.mock import patch

import pytest
from funtracks.utils.tracksdata_utils import create_empty_graph
from qtpy.QtWidgets import QPushButton

from motile_tracker.motile.backend import MotileRun, SolverParams
from motile_tracker.motile.menus.run_viewer import RunViewer


@pytest.fixture
def run_viewer(qtbot):
    """Fixture for creating a RunViewer widget."""
    widget = RunViewer()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def sample_run(segmentation_2d):
    """Fixture for creating a sample MotileRun."""

    return MotileRun(
        graph=create_empty_graph(),
        input_segmentation=segmentation_2d,
        run_name="test_run",
        solver_params=SolverParams(),
    )


def test_run_viewer_initialization(run_viewer):
    """Test RunViewer initialization."""
    # Test 1: RunViewer creates all components
    assert run_viewer.run is None
    assert run_viewer.params_widget is not None
    assert run_viewer.solver_label is not None
    assert run_viewer.gap_plot is not None

    # Test 2: RunViewer has correct initial title
    assert run_viewer.title() == "Run Viewer"

    # Test 3: RunViewer has edit_run signal
    assert hasattr(run_viewer, "edit_run")


def test_update_run(run_viewer, sample_run, qtbot):
    """Test update_run method."""
    # Test 1: update_run stores the run
    run_viewer.update_run(sample_run)
    assert run_viewer.run is sample_run

    # Test 2: update_run updates the title with run name and time
    title = run_viewer.title()
    assert "Run Viewer: test_run" in title
    assert "(" in title and ")" in title

    # Test 3: update_run emits params_widget.new_params signal
    sample_run2 = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=sample_run.input_segmentation,
        run_name="test_run2",
        solver_params=SolverParams(),
    )
    with qtbot.waitSignal(run_viewer.params_widget.new_params, timeout=1000):
        run_viewer.update_run(sample_run2)

    # Test 4: update_run calls solver_event_update
    sample_run3 = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=sample_run.input_segmentation,
        run_name="test_run3",
        solver_params=SolverParams(),
    )
    with patch.object(run_viewer, "solver_event_update") as mock_update:
        run_viewer.update_run(sample_run3)
        mock_update.assert_called_once()


def test_back_to_edit_widget(run_viewer, qtbot, sample_run):
    """Test _back_to_edit_widget and related methods."""
    # Test 1: back to editing button is created
    buttons = run_viewer.findChildren(QPushButton)
    back_buttons = [b for b in buttons if "Back to editing" in b.text()]
    assert len(back_buttons) == 1

    # Test 2: back to editing button emits None
    run_viewer.run = sample_run
    back_button = back_buttons[0]
    with qtbot.waitSignal(run_viewer.edit_run) as blocker:
        back_button.click()
    assert blocker.args[0] is None

    # Test 3: edit this run button is created
    edit_buttons = [b for b in buttons if "Edit this run" in b.text()]
    assert len(edit_buttons) == 1

    # Test 4: edit this run button emits current run
    edit_button = edit_buttons[0]
    with qtbot.waitSignal(run_viewer.edit_run) as blocker:
        edit_button.click()
    assert blocker.args[0] is sample_run


def test_emit_run(run_viewer, qtbot, sample_run):
    """Test _emit_run method."""
    run_viewer.run = sample_run

    # Test: _emit_run emits edit_run signal with current run
    with qtbot.waitSignal(run_viewer.edit_run) as blocker:
        run_viewer._emit_run()
    assert blocker.args[0] is sample_run


def test_progress_widget(run_viewer):
    """Test _progress_widget and components."""
    # Test 1: progress widget contains solver label
    assert run_viewer.solver_label is not None
    assert run_viewer.solver_label.text() == ""

    # Test 2: progress widget contains gap plot
    assert run_viewer.gap_plot is not None


def test_plot_widget(run_viewer):
    """Test _plot_widget method."""
    # Test 1: plot widget is created with correct settings
    gap_plot = run_viewer.gap_plot
    assert gap_plot is not None

    # Test 2: plot widget has logarithmic y-axis
    plot_item = gap_plot.plotItem
    assert plot_item.ctrl.logYCheck.isChecked()

    # Test 3: plot widget has correct axis labels
    left_label = plot_item.getAxis("left").labelText
    bottom_label = plot_item.getAxis("bottom").labelText
    assert "Gap" in left_label
    assert "Solver round" in bottom_label


def test_set_solver_label(run_viewer):
    """Test _set_solver_label method."""
    # Test: _set_solver_label updates label text
    run_viewer._set_solver_label("initializing")
    assert run_viewer.solver_label.text() == "Solver status: initializing"

    run_viewer._set_solver_label("solving")
    assert run_viewer.solver_label.text() == "Solver status: solving"

    run_viewer._set_solver_label("done")
    assert run_viewer.solver_label.text() == "Solver status: done"


def test_solver_event_update(run_viewer, sample_run):
    """Test solver_event_update method."""
    # Test 1: solver_event_update with initializing status
    sample_run.status = "initializing"
    sample_run.gaps = None
    run_viewer.run = sample_run
    run_viewer.solver_event_update()
    assert "initializing" in run_viewer.solver_label.text()

    # Test 2: solver_event_update with presolving status
    sample_run.status = "presolving"
    sample_run.gaps = []
    run_viewer.solver_event_update()
    assert "presolving" in run_viewer.solver_label.text()

    # Test 3: solver_event_update with solving status
    sample_run.status = "solving"
    sample_run.gaps = [0.5, 0.3, 0.1]
    run_viewer.solver_event_update()
    assert "solving" in run_viewer.solver_label.text()

    # Test 4: solver_event_update with done status
    sample_run.status = "done"
    sample_run.gaps = [0.5, 0.3, 0.1, 0.05]
    run_viewer.solver_event_update()
    assert "done" in run_viewer.solver_label.text()

    # Test 5: solver_event_update plots gap data
    sample_run.status = "solving"
    sample_run.gaps = [0.5, 0.3, 0.1]
    run_viewer.solver_event_update()
    plot_item = run_viewer.gap_plot.getPlotItem()
    data_items = plot_item.listDataItems()
    assert len(data_items) > 0

    # Test 6: solver_event_update clears plot before updating
    sample_run.gaps = [0.8, 0.6, 0.4, 0.2]
    run_viewer.solver_event_update()
    data_items = plot_item.listDataItems()
    assert len(data_items) == 1

    # Test 7: solver_event_update handles None gaps
    sample_run.status = "initializing"
    sample_run.gaps = None
    run_viewer.solver_event_update()
    data_items = plot_item.listDataItems()
    assert len(data_items) == 0

    # Test 8: solver_event_update handles empty gaps list
    sample_run.status = "presolving"
    sample_run.gaps = []
    run_viewer.solver_event_update()
    data_items = plot_item.listDataItems()
    assert len(data_items) == 0

    # Test 9: solver_event_update handles pyqtgraph exceptions
    sample_run.status = "solving"
    sample_run.gaps = [0.5, 0.3, 0.1]
    with patch.object(
        run_viewer.gap_plot.getPlotItem(),
        "plot",
        side_effect=Exception("X and Y arrays must be the same length"),
    ):
        run_viewer.solver_event_update()


def test_reset_progress(run_viewer, sample_run):
    """Test reset_progress method."""
    # Test 1: reset_progress sets label to 'not running'
    run_viewer._set_solver_label("solving")
    run_viewer.reset_progress()
    assert "not running" in run_viewer.solver_label.text()

    # Test 2: reset_progress clears the gap plot
    sample_run.status = "solving"
    sample_run.gaps = [0.5, 0.3, 0.1]
    run_viewer.run = sample_run
    run_viewer.solver_event_update()
    run_viewer.reset_progress()
    plot_item = run_viewer.gap_plot.getPlotItem()
    data_items = plot_item.listDataItems()
    assert len(data_items) == 0
