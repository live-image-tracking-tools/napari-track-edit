"""Tests for RunEditor - the UI for configuring and starting tracking runs."""

import dask.array as da
import numpy as np
import pytest
import tracksdata as td
from funtracks.utils.tracksdata_utils import create_empty_graph

from napari_track_edit.motile.backend import MotileRun, SolverParams
from napari_track_edit.motile.menus.run_editor import RunEditor


def test_run_editor_initialization(make_napari_viewer, segmentation_2d):
    """Test RunEditor widget initialization and layer dropdown population."""
    viewer = make_napari_viewer()

    # RunEditor creates all UI elements correctly
    editor = RunEditor(viewer)
    assert editor.viewer is viewer
    assert editor.solver_params_widget is not None
    assert editor.run_name is not None
    assert editor.layer_selection_box is not None
    assert editor.run_name.text() == "new_run"

    # RunEditor populates layer dropdown when layers exist
    viewer.add_labels(segmentation_2d, name="seg1")
    viewer.add_labels(segmentation_2d, name="seg2")
    editor2 = RunEditor(viewer)
    assert editor2.layer_selection_box.count() == 2
    assert editor2.layer_selection_box.itemText(0) in ["seg1", "seg2"]


def test_layer_management(make_napari_viewer, segmentation_2d, qtbot):
    """Test layer selection and management functionality."""
    viewer = make_napari_viewer()

    # update_labels_layers adds new Labels layers
    editor = RunEditor(viewer)
    assert editor.layer_selection_box.count() == 0
    viewer.add_labels(segmentation_2d, name="seg1")
    assert editor.layer_selection_box.count() == 1
    assert editor.layer_selection_box.itemText(0) == "seg1"

    # update_labels_layers adds Points layers
    points_data = np.array([[0, 10, 20], [1, 30, 40]])
    viewer.add_points(points_data, name="points1")
    assert editor.layer_selection_box.count() == 2
    assert "points1" in [editor.layer_selection_box.itemText(i) for i in range(2)]

    # update_labels_layers ignores Image layers
    viewer.add_image(segmentation_2d.astype(float), name="image1")
    assert editor.layer_selection_box.count() == 2

    # update_labels_layers preserves current selection
    viewer.add_labels(segmentation_2d, name="seg2")
    editor2 = RunEditor(viewer)
    editor2.layer_selection_box.setCurrentText("seg2")
    assert editor2.layer_selection_box.currentText() == "seg2"
    viewer.add_labels(segmentation_2d, name="seg3")
    assert editor2.layer_selection_box.currentText() == "seg2"

    # get_input_layer returns the selected layer
    layer = viewer.add_labels(segmentation_2d, name="seg4")
    editor3 = RunEditor(viewer)
    editor3.layer_selection_box.setCurrentText("seg4")
    result = editor3.get_input_layer()
    assert result is layer

    # get_input_layer returns None when nothing selected
    viewer2 = make_napari_viewer()
    editor4 = RunEditor(viewer2)
    result = editor4.get_input_layer()
    assert result is None

    # update_layer_selection enables IoU cost for Labels layers
    viewer2.add_labels(segmentation_2d, name="seg_iou")
    editor5 = RunEditor(viewer2)
    qtbot.addWidget(editor5)
    editor5.show()
    editor5.layer_selection_box.setCurrentText("seg_iou")
    editor5.update_layer_selection()
    assert editor5.solver_params_widget.iou_row.isVisible()

    # update_layer_selection disables IoU cost for Points layers
    viewer2.add_points(points_data, name="points_iou")
    editor5.layer_selection_box.setCurrentText("points_iou")
    editor5.update_layer_selection()
    assert not editor5.solver_params_widget.iou_row.isVisible()


def test_run_creation(make_napari_viewer, segmentation_2d):
    """Test creating MotileRun objects from editor state."""
    viewer = make_napari_viewer()
    viewer.add_labels(segmentation_2d, name="seg1", scale=(1, 2, 3))
    editor = RunEditor(viewer)
    editor.run_name.setText("test_run")
    editor.layer_selection_box.setCurrentText("seg1")

    # get_run creates run with Labels layer
    run = editor.get_run()
    assert run is not None
    assert run.run_name == "test_run"
    assert run.input_segmentation is not None
    assert np.array_equal(run.input_segmentation, segmentation_2d)
    assert run.input_points is None
    assert tuple(run.scale) == (1, 2, 3)
    assert isinstance(run.graph_solution, td.graph.GraphView)

    # get_run creates run with Points layer
    points_data = np.array([[0, 10, 20], [1, 30, 40]])
    viewer.add_points(points_data, name="points1", scale=(1, 2, 3))
    editor.run_name.setText("points_run")
    editor.layer_selection_box.setCurrentText("points1")
    run2 = editor.get_run()
    assert run2 is not None
    assert run2.run_name == "points_run"
    assert run2.input_segmentation is None
    assert run2.input_points is not None
    assert np.array_equal(run2.input_points, points_data)
    assert tuple(run2.scale) == (1, 2, 3)

    # get_run uses solver params from the editor
    viewer.add_labels(segmentation_2d, name="seg_params")
    editor7 = RunEditor(viewer)
    editor7.layer_selection_box.setCurrentText("seg_params")
    editor7.solver_params_widget.solver_params.max_edge_distance = 123.0
    run8 = editor7.get_run()
    assert run8 is not None
    assert run8.solver_params.max_edge_distance == 123.0


def test_run_creation_edge_cases(make_napari_viewer, segmentation_2d):
    """Test get_run edge cases: no layer, wrong dimensions, dask, multiscale."""
    viewer = make_napari_viewer()

    # get_run returns None when no layer selected
    editor = RunEditor(viewer)
    with pytest.warns(UserWarning, match="No input layer selected"):
        run = editor.get_run()
    assert run is None

    # get_run raises error for 2D segmentation
    seg_2d = np.zeros((100, 100), dtype="int32")
    viewer.add_labels(seg_2d, name="seg_2d")
    editor2 = RunEditor(viewer)
    editor2.layer_selection_box.setCurrentText("seg_2d")
    with pytest.raises(ValueError, match="Expected segmentation to be at least 3D"):
        editor2.get_run()

    # get_run raises error for 5D segmentation
    seg_5d = np.zeros((2, 2, 10, 100, 100), dtype="int32")
    viewer.add_labels(seg_5d, name="seg_5d")
    editor2.layer_selection_box.setCurrentText("seg_5d")
    with pytest.raises(ValueError, match="Expected segmentation to be at most 4D"):
        editor2.get_run()

    # get_run converts dask array to numpy
    dask_seg = da.from_array(segmentation_2d, chunks=(1, 50, 50))
    viewer.add_labels(dask_seg, name="seg_dask")
    editor2.layer_selection_box.setCurrentText("seg_dask")
    run_dask = editor2.get_run()
    assert run_dask is not None
    assert isinstance(run_dask.input_segmentation, np.ndarray)
    assert not isinstance(run_dask.input_segmentation, da.Array)

    # get_run extracts highest resolution from multiscale labels
    level0 = segmentation_2d
    level1 = segmentation_2d[:, ::2, ::2]
    viewer.add_labels([level0, level1], name="multiscale_seg", multiscale=True)
    editor2.layer_selection_box.setCurrentText("multiscale_seg")
    run_ms = editor2.get_run()
    assert run_ms is not None
    assert isinstance(run_ms.input_segmentation, np.ndarray)
    assert run_ms.input_segmentation.shape == level0.shape
    assert np.array_equal(run_ms.input_segmentation, level0)


def test_signal_emission(make_napari_viewer, segmentation_2d, qtbot):
    """Test signal emission when starting runs."""
    viewer = make_napari_viewer()

    # emit_run emits start_run signal when run is valid
    viewer.add_labels(segmentation_2d, name="seg1")
    editor = RunEditor(viewer)
    editor.layer_selection_box.setCurrentText("seg1")
    with qtbot.waitSignal(editor.start_run, timeout=1000) as blocker:
        editor.emit_run()
    run = blocker.args[0]
    assert isinstance(run, MotileRun)

    # emit_run doesn't emit signal when no layer selected
    viewer2 = make_napari_viewer()
    editor2 = RunEditor(viewer2)
    with qtbot.assertNotEmitted(editor2.start_run), pytest.warns(UserWarning):
        editor2.emit_run()


def test_new_run(make_napari_viewer, segmentation_2d, qtbot):
    """Test loading existing runs into editor."""
    viewer = make_napari_viewer()
    editor = RunEditor(viewer)

    custom_params = SolverParams(max_edge_distance=999.0, max_children=5)
    existing_run = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=segmentation_2d,
        run_name="existing_run",
        solver_params=custom_params,
        ndim=3,
    )
    editor.new_run(existing_run)
    assert editor.run_name.text() == "existing_run"
    qtbot.wait(100)
    assert editor.solver_params_widget.solver_params.max_edge_distance == 999.0
    assert editor.solver_params_widget.solver_params.max_children == 5


def test_max_frames_update(make_napari_viewer, segmentation_2d):
    """Test updating max frame constraint from viewer dims."""
    viewer = make_napari_viewer()
    viewer.add_labels(segmentation_2d, name="seg1")

    editor = RunEditor(viewer)
    editor._update_max_frames()
    max_frame = int(viewer.dims.range[0].stop)
    assert (
        editor.solver_params_widget.single_window_start_row.param_value.maximum()
        == max_frame - 1
    )
