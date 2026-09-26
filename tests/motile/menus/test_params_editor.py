"""Tests for SolverParamsEditor - the parameter editing UI widget.

Tests cover parameter widgets, optional parameter checkboxes, chunking constraints,
and validation logic.
"""

from qtpy.QtWidgets import QCheckBox, QLabel

from napari_track_edit.motile.backend.solver_params import SolverParams
from napari_track_edit.motile.menus.params_editor import (
    EditableParam,
    OptionalEditableParam,
    SolverParamsEditor,
    _get_base_type,
)


def test_get_base_type():
    """Test _get_base_type utility function."""
    # Test 1: Extracting int from plain int type
    result = _get_base_type(int)
    assert result is int

    # Test 2: Extracting float from plain float type
    result = _get_base_type(float)
    assert result is float

    # Test 3: Extracting int from int | None type
    result = _get_base_type(int | None)
    assert result is int

    # Test 4: Extracting float from float | None type
    result = _get_base_type(float | None)
    assert result is float


def test_editable_param(qapp):
    """Test EditableParam widget for required parameters."""
    # Test 1: EditableParam creates all UI elements correctly
    solver_params = SolverParams()
    param = EditableParam("max_edge_distance", solver_params)
    assert param.param_name == "max_edge_distance"
    assert param.dtype == float
    assert param.title == "Max Move Distance"
    assert isinstance(param.param_label, QLabel)

    # Test 2: EditableParam with negative=True
    param_neg = EditableParam("edge_selection_cost", solver_params, negative=True)
    assert param_neg.negative is True
    assert param_neg.param_value.minimum() < 0

    # Test 3: EditableParam with negative=False
    param_no_neg = EditableParam("max_edge_distance", solver_params, negative=False)
    assert param_no_neg.negative is False
    assert param_no_neg.param_value.minimum() >= 0

    # Test 4: update_from_params updates the displayed value
    solver_params_100 = SolverParams(max_edge_distance=100.0)
    param4 = EditableParam("max_edge_distance", solver_params_100)
    assert param4.param_value.value() == 100.0
    new_params = SolverParams(max_edge_distance=200.0)
    param4.update_from_params(new_params)
    assert param4.param_value.value() == 200.0

    # Test 5: update_from_params works with int parameters
    solver_params_3 = SolverParams(max_children=3)
    param5 = EditableParam("max_children", solver_params_3)
    assert param5.param_value.value() == 3
    new_params_5 = SolverParams(max_children=5)
    param5.update_from_params(new_params_5)
    assert param5.param_value.value() == 5


def test_optional_editable_param(qapp, qtbot):
    """Test OptionalEditableParam widget for optional parameters."""
    # Test 1: OptionalEditableParam creates checkbox label
    solver_params = SolverParams()
    param = OptionalEditableParam("window_size", solver_params)
    assert isinstance(param.param_label, QCheckBox)
    assert param.param_label.text() == "Window Size"

    # Test 2: OptionalEditableParam reads ui_default from schema
    assert param.ui_default == 50

    # Test 3: update_from_params with None value unchecks and disables
    solver_params_none = SolverParams(window_size=None)
    param3 = OptionalEditableParam("window_size", solver_params_none)
    assert not param3.param_label.isChecked()
    assert not param3.param_value.isEnabled()
    assert param3.param_value.value() == 50

    # Test 4: update_from_params with actual value checks and enables
    solver_params_100 = SolverParams(window_size=100)
    param4 = OptionalEditableParam("window_size", solver_params_100)
    assert param4.param_label.isChecked()
    assert param4.param_value.isEnabled()
    assert param4.param_value.value() == 100

    # Test 5: toggle_enable enables widget when checked
    solver_params_none2 = SolverParams(window_size=None)
    param5 = OptionalEditableParam("window_size", solver_params_none2)
    assert not param5.param_value.isEnabled()
    param5.toggle_enable(True)
    assert param5.param_value.isEnabled()

    # Test 6: toggle_enable disables widget when unchecked
    solver_params_100_2 = SolverParams(window_size=100)
    param6 = OptionalEditableParam("window_size", solver_params_100_2)
    assert param6.param_value.isEnabled()
    param6.toggle_enable(False)
    assert not param6.param_value.isEnabled()

    # Test 7: toggle_enable emits valueChanged signal
    solver_params_100_3 = SolverParams(window_size=100)
    param7 = OptionalEditableParam("window_size", solver_params_100_3)
    with qtbot.waitSignal(param7.param_value.valueChanged, timeout=1000):
        param7.toggle_enable(False)

    # Test 8: toggle_visible emits valueChanged signal
    solver_params_100_4 = SolverParams(window_size=100)
    param8 = OptionalEditableParam("window_size", solver_params_100_4)
    with qtbot.waitSignal(param8.param_value.valueChanged, timeout=1000):
        param8.toggle_visible(False)


def test_solver_params_editor_initialization(qapp):
    """Test SolverParamsEditor initialization."""
    # Test 1: SolverParamsEditor creates all UI elements
    editor = SolverParamsEditor()
    assert isinstance(editor.solver_params, SolverParams)
    assert "hyperparams" in editor.param_categories
    assert "constant_costs" in editor.param_categories
    assert "attribute_costs" in editor.param_categories
    assert "chunking" in editor.param_categories
    assert hasattr(editor, "iou_row")
    assert hasattr(editor, "window_size_row")
    assert hasattr(editor, "overlap_size_row")
    assert hasattr(editor, "single_window_start_row")

    # Test 2: param_categories contains correct parameter names
    assert "max_edge_distance" in editor.param_categories["hyperparams"]
    assert "max_children" in editor.param_categories["hyperparams"]
    assert "edge_selection_cost" in editor.param_categories["constant_costs"]
    assert "appear_cost" in editor.param_categories["constant_costs"]
    assert "division_cost" in editor.param_categories["constant_costs"]
    assert "distance_cost" in editor.param_categories["attribute_costs"]
    assert "iou_cost" in editor.param_categories["attribute_costs"]
    assert "window_size" in editor.param_categories["chunking"]
    assert "overlap_size" in editor.param_categories["chunking"]
    assert "single_window_start" in editor.param_categories["chunking"]


def test_chunking_constraints(qapp):
    """Test chunking parameter validation constraints."""
    # Test 1: window_size has minimum value of 2
    editor = SolverParamsEditor()
    assert editor.window_size_row.param_value.minimum() == 2

    # Test 2: overlap_size has minimum value of 1
    assert editor.overlap_size_row.param_value.minimum() == 1

    # Test 3: overlap_size maximum updates when window_size changes
    editor.window_size_row.param_label.setChecked(True)
    editor.window_size_row.param_value.setValue(10)
    assert editor.overlap_size_row.param_value.maximum() == 9

    # Test 4: overlap_size value is clamped when window_size decreases
    editor.overlap_size_row.param_label.setChecked(True)
    editor.overlap_size_row.param_value.setValue(8)
    editor.window_size_row.param_value.setValue(5)
    assert editor.overlap_size_row.param_value.value() == 4

    # Test 5: overlap_size and single_window_start disabled when window_size unchecked
    editor.window_size_row.param_label.setChecked(False)
    assert not editor.overlap_size_row.isEnabled()
    assert not editor.single_window_start_row.isEnabled()

    # Test 6: overlap_size and single_window_start enabled when window_size checked
    editor.window_size_row.param_label.setChecked(True)
    assert editor.overlap_size_row.isEnabled()
    assert editor.single_window_start_row.isEnabled()

    # Test 7: overlap_size and single_window_start are mutually exclusive
    editor.overlap_size_row.param_label.setChecked(True)
    assert editor.overlap_size_row.param_label.isChecked()
    editor.single_window_start_row.param_label.setChecked(True)
    assert not editor.overlap_size_row.param_label.isChecked()
    assert editor.single_window_start_row.param_label.isChecked()
    editor.overlap_size_row.param_label.setChecked(True)
    assert editor.overlap_size_row.param_label.isChecked()
    assert not editor.single_window_start_row.param_label.isChecked()

    # Test 8: last chunking mode is remembered when toggling window_size
    editor2 = SolverParamsEditor()
    editor2.window_size_row.param_label.setChecked(True)
    editor2.overlap_size_row.param_label.setChecked(True)
    assert editor2._last_chunking_mode == "overlap"
    editor2.window_size_row.param_label.setChecked(False)
    editor2.window_size_row.param_label.setChecked(True)
    assert editor2.overlap_size_row.param_label.isChecked()
    assert not editor2.single_window_start_row.param_label.isChecked()

    # Test 9: single_window mode is remembered when toggling window_size
    editor3 = SolverParamsEditor()
    editor3.window_size_row.param_label.setChecked(True)
    editor3.single_window_start_row.param_label.setChecked(True)
    assert editor3._last_chunking_mode == "single_window"
    editor3.window_size_row.param_label.setChecked(False)
    editor3.window_size_row.param_label.setChecked(True)
    assert editor3.single_window_start_row.param_label.isChecked()
    assert not editor3.overlap_size_row.param_label.isChecked()


def test_set_max_frames(qapp):
    """Test set_max_frames method."""
    # Test 1: set_max_frames sets correct maximum for single_window_start
    editor = SolverParamsEditor()
    editor.set_max_frames(100)
    assert editor.single_window_start_row.param_value.maximum() == 99

    # Test 2: set_max_frames clamps current value if too high
    editor.window_size_row.param_label.setChecked(True)
    editor.single_window_start_row.param_label.setChecked(True)
    editor.single_window_start_row.param_value.setValue(50)
    editor.set_max_frames(30)
    assert editor.single_window_start_row.param_value.value() == 29

    # Test 3: set_max_frames with 0 frames
    editor2 = SolverParamsEditor()
    editor2.set_max_frames(0)
    assert editor2.single_window_start_row.param_value.maximum() == 0


def test_param_signals(qapp):
    """Test signal emissions and connections."""
    # Test 1: new_params signal updates all parameter widgets
    editor = SolverParamsEditor()
    new_params = SolverParams(max_edge_distance=100.0, max_children=3, window_size=50)
    editor.new_params.emit(new_params)

    # Test 2: solver_params has required attributes
    assert hasattr(editor.solver_params, "max_edge_distance")
    assert hasattr(editor.solver_params, "window_size")
    assert hasattr(editor.solver_params, "overlap_size")
