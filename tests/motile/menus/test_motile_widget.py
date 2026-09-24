"""Tests for MotileWidget - the main tracking control widget."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from funtracks.utils.tracksdata_utils import create_empty_graph

from motile_tracker.motile.backend import MotileRun, SolverParams
from motile_tracker.motile.menus.motile_widget import MotileWidget


def test_initialization_and_title(make_napari_viewer):
    """Test MotileWidget initialization, signals, and title widget."""
    from qtpy.QtWidgets import QLabel

    viewer = make_napari_viewer()
    widget = MotileWidget(viewer)

    # Verify all components created
    assert widget.viewer is viewer
    assert widget.edit_run_widget is not None
    assert widget.view_run_widget is not None
    assert not widget.view_run_widget.isVisible()

    # Verify signal connections exist
    assert hasattr(widget, "solver_update")
    assert hasattr(widget, "new_run")
    assert hasattr(widget.edit_run_widget, "start_run")
    assert hasattr(widget.view_run_widget, "edit_run")

    # Title widget
    title = widget._title_widget()
    assert isinstance(title, QLabel)
    assert len(title.text()) > 0
    assert "motile" in title.text().lower()
    assert title.openExternalLinks()
    assert title.wordWrap()


def test_view_and_edit_run(make_napari_viewer, solution_tracks_2d, qtbot):
    """Test view_run and edit_run widget visibility toggling."""
    viewer = make_napari_viewer()
    widget = MotileWidget(viewer)
    qtbot.addWidget(widget)
    widget.show()

    # view_run with MotileRun shows viewer and hides editor
    run = MotileRun(
        graph=create_empty_graph(),
        run_name="test_run",
        solver_params=SolverParams(),
        ndim=3,
    )
    widget.view_run(run)
    assert widget.view_run_widget.isVisible()
    assert not widget.edit_run_widget.isVisible()

    # view_run with Tracks (non-MotileRun) hides the viewer and falls back
    # to the editor, so the solver settings stay available without a motile run
    widget.view_run(solution_tracks_2d)
    assert not widget.view_run_widget.isVisible()
    assert widget.edit_run_widget.isVisible()

    # edit_run with None shows editor and hides viewer
    widget.view_run_widget.show()
    widget.edit_run(None)
    assert widget.edit_run_widget.isVisible()
    assert not widget.view_run_widget.isVisible()

    # edit_run with run loads parameters into editor
    custom_params = SolverParams(max_edge_distance=999.0)
    run2 = MotileRun(
        graph=create_empty_graph(),
        run_name="test_run",
        solver_params=custom_params,
        ndim=3,
    )
    with patch.object(widget.edit_run_widget, "new_run") as mock_new_run:
        widget.edit_run(run2)
        mock_new_run.assert_called_once_with(run2)
    assert widget.edit_run_widget.isVisible()


def test_generate_tracks(make_napari_viewer):
    """Test _generate_tracks method."""
    viewer = make_napari_viewer()
    widget = MotileWidget(viewer)

    run = MotileRun(
        graph=create_empty_graph(),
        run_name="test_run",
        solver_params=SolverParams(),
        ndim=3,
    )

    with patch.object(widget, "solve_with_motile") as mock_solve:
        mock_worker = MagicMock()
        mock_solve.return_value = mock_worker

        # Sets status to initializing and starts worker
        widget._generate_tracks(run)
        assert run.status == "initializing"
        mock_worker.start.assert_called_once()

    # Calls view_run
    with (
        patch.object(widget, "solve_with_motile") as mock_solve,
        patch.object(widget, "view_run") as mock_view_run,
    ):
        mock_worker = MagicMock()
        mock_solve.return_value = mock_worker
        widget._generate_tracks(run)
        mock_view_run.assert_called_once_with(run)


def test_solve_with_motile(make_napari_viewer, segmentation_2d):
    """Test solve_with_motile method with different input scenarios."""
    viewer = make_napari_viewer()
    widget = MotileWidget(viewer)
    worker_fn = widget.solve_with_motile.__wrapped__

    # Returns a run where all nodes have track_id assigned
    run = MotileRun(
        graph=create_empty_graph(),
        run_name="test_run",
        solver_params=SolverParams(),
        input_segmentation=segmentation_2d,
    )
    widget.view_run_widget.run = run
    result = worker_fn(widget, run)
    assert result.graph_solution.num_nodes() > 0
    for node in result.graph_solution.node_ids():
        assert result.get_track_id(node) is not None

    # Area feature is enabled and computed for all nodes
    assert "area" in result.features
    for node in result.graph_solution.node_ids():
        assert result.graph_solution.nodes[node]["area"] > 0

    # Raises ValueError without input data
    run2 = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=None,
        run_name="test_run",
        solver_params=SolverParams(),
        ndim=3,
    )
    run2.input_points = None
    with pytest.raises(ValueError, match="Must have one of input segmentation"):
        worker_fn(widget, run2)

    # Uses points when provided
    points_data = np.array([[0, 10, 20], [1, 30, 40]])
    run3 = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=None,
        input_points=points_data,
        run_name="test_run",
        solver_params=SolverParams(),
        ndim=3,
    )
    with (
        patch(
            "motile_tracker.motile.menus.motile_widget.build_candidate_graph"
        ) as mock_build,
        patch("motile_tracker.motile.menus.motile_widget.solve") as mock_solve,
    ):
        mock_build.return_value = create_empty_graph()
        mock_solve.return_value = create_empty_graph()
        worker_fn = widget.solve_with_motile.__wrapped__
        worker_fn(widget, run3)
        mock_build.assert_called_once()
        assert np.array_equal(mock_build.call_args[0][0], points_data)
        mock_solve.assert_called_once()

    # Shows warning for empty result
    run4 = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=segmentation_2d,
        run_name="test_run",
        solver_params=SolverParams(),
    )
    with (
        patch(
            "motile_tracker.motile.menus.motile_widget.build_candidate_graph"
        ) as mock_build,
        patch("motile_tracker.motile.menus.motile_widget.solve") as mock_solve,
        patch("motile_tracker.motile.menus.motile_widget.show_warning") as mock_warning,
    ):
        mock_build.return_value = create_empty_graph()
        mock_solve.return_value = create_empty_graph()
        worker_fn = widget.solve_with_motile.__wrapped__
        worker_fn(widget, run4)
        mock_warning.assert_called_once()
        assert "No tracks found" in mock_warning.call_args[0][0]

    # Relabel segmentation when there are duplicate labels
    segmentation_2d[1][10:10, 10:10] = 1  # duplicate value

    run5 = MotileRun(
        graph=create_empty_graph(),
        input_segmentation=segmentation_2d,
        run_name="test_run",
        solver_params=SolverParams(),
    )

    with (
        patch(
            "motile_tracker.motile.menus.motile_widget.build_candidate_graph"
        ) as mock_build,
        patch("motile_tracker.motile.menus.motile_widget.solve") as mock_solve,
        patch(
            "motile_tracker.motile.menus.motile_widget.ensure_unique_labels"
        ) as mock_relabel,
    ):
        mock_build.side_effect = [
            ValueError("Duplicate values found among nodes"),
            create_empty_graph(),
        ]
        mock_solve.return_value = create_empty_graph()

        relabeled = segmentation_2d.copy()
        relabeled[1][10:10, 10:10] = 100
        mock_relabel.return_value = relabeled

        worker_fn = widget.solve_with_motile.__wrapped__
        worker_fn(widget, run5)

        # build_candidate_graph called twice (once failed, once after relabel)
        assert mock_build.call_count == 2

        # relabel called once
        assert mock_relabel.call_count == 1

        # solve called once with the pre-built graph
        assert mock_solve.call_count == 1
        call_kwargs = mock_solve.call_args[1]
        assert call_kwargs["cand_graph"] is not None

        # solve received the relabeled segmentation
        assert mock_solve.call_args[0][1] is relabeled


def test_solver_events_and_completion(make_napari_viewer, qtbot):
    """Test _on_solver_event and _on_solve_complete methods."""
    viewer = make_napari_viewer()
    widget = MotileWidget(viewer)

    run = MotileRun(
        graph=create_empty_graph(),
        run_name="test_run",
        solver_params=SolverParams(),
        ndim=3,
    )
    widget.view_run_widget.run = run

    # PRESOLVE event sets status
    event_data = {"event_type": "PRESOLVE"}
    widget._on_solver_event(run, event_data)
    assert run.status == "presolving"
    assert run.gaps == []

    # MIPSOL event sets status and gap
    event_data = {"event_type": "MIPSOL", "gap": 0.5}
    widget._on_solver_event(run, event_data)
    assert run.status == "solving"
    assert len(run.gaps) == 1
    assert run.gaps[0] == 0.5

    # Appends multiple gaps
    event_data2 = {"event_type": "MIPSOL", "gap": 0.3}
    widget._on_solver_event(run, event_data2)
    assert len(run.gaps) == 2
    assert run.gaps[0] == 0.5
    assert run.gaps[1] == 0.3

    # Emits solver_update signal
    event_data = {"event_type": "MIPSOL", "gap": 0.1}
    with qtbot.waitSignal(widget.solver_update, timeout=1000):
        widget._on_solver_event(run, event_data)

    # _on_solve_complete sets status to done
    widget._on_solve_complete(run)
    assert run.status == "done"

    # Emits solver_update signal
    with qtbot.waitSignal(widget.solver_update, timeout=1000):
        widget._on_solve_complete(run)

    # Emits new_run signal with correct args
    with qtbot.waitSignal(widget.new_run, timeout=1000) as blocker:
        widget._on_solve_complete(run)
    assert blocker.args[0] is run
    assert blocker.args[1] == "test_run"
