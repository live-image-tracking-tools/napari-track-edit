import numpy as np
import pytest
from funtracks.utils.tracksdata_utils import assert_node_attrs_equal_with_masks

from motile_tracker.motile.backend import SolverParams, solve


# capsys is a pytest fixture that captures stdout and stderr output streams
def test_solve_2d(graph_2d, segmentation_2d):
    params = SolverParams()
    params.appear_cost = None
    soln_graph = solve(params, segmentation_2d)

    # remove nodes that don't make the solution
    # node 4 is too far from node 3
    # node 5 is two frames from node 4
    # node 6 is isolated and has no edges
    for node in [4, 5, 6]:
        graph_2d.remove_node(node)
    assert set(soln_graph.node_ids()) == set(graph_2d.node_ids())


def test_solve_3d(graph_3d, segmentation_3d):
    params = SolverParams()
    params.appear_cost = None
    soln_graph = solve(params, segmentation_3d)
    assert set(soln_graph.node_ids()) == set(graph_3d.node_ids())


def test_solve_chunked(segmentation_3d):
    """Test that chunked solving produces same results as full solve."""
    # First solve without chunking
    params = SolverParams()
    params.appear_cost = None
    full_solution = solve(params, segmentation_3d)

    # Then solve with chunking
    params_chunked = SolverParams()
    params_chunked.appear_cost = None
    params_chunked.window_size = 3
    params_chunked.overlap_size = 1
    chunked_solution = solve(params_chunked, segmentation_3d)

    # Solutions should have the same nodes and edges
    assert set(full_solution.node_ids()) == set(chunked_solution.node_ids())
    assert_node_attrs_equal_with_masks(
        full_solution, chunked_solution, check_row_order=False
    )
    assert {tuple(e) for e in full_solution.edge_list()} == {
        tuple(e) for e in chunked_solution.edge_list()
    }


def test_solve_chunked_overlap_required():
    """Test that overlap_size must be at least 1."""
    params = SolverParams()
    params.window_size = 3

    with pytest.raises(ValueError, match="overlap_size must be at least 1"):
        params.overlap_size = 0


def test_solve_single_window(segmentation_3d):
    """Test solving just a single window for interactive testing."""
    params = SolverParams()
    params.appear_cost = None
    params.window_size = 3
    params.single_window_start = 1  # Start at frame 1

    solution = solve(params, segmentation_3d)

    # Should only have nodes from frames 1, 2, 3
    assert solution.num_nodes() > 0
    # Verify all nodes are within the window
    for node in solution.node_ids():
        node_time = solution.nodes[node]["t"]
        assert 1 <= node_time < 4, f"Node {node} has time {node_time}, expected 1-3"


def test_solve_single_window_start_0(segmentation_2d):
    """Window starting at frame 0 — no t-shift should be applied."""
    params = SolverParams()
    params.appear_cost = None
    params.window_size = 2
    params.single_window_start = 0

    solution = solve(params, segmentation_2d)

    assert solution.num_nodes() > 0
    for node in solution.node_ids():
        node_time = solution.nodes[node]["t"]
        assert 0 <= node_time < 2, f"Node {node} has time {node_time}, expected 0-1"


def test_solve_single_window_points():
    """Single-window mode with a points list (ndim==2 branch) as input."""
    # Columns: (t, y, x) — points close enough to form edges within default max_edge_distance
    points = np.array(
        [
            [0, 50.0, 50.0],
            [1, 51.0, 51.0],
            [2, 52.0, 52.0],
            [3, 53.0, 53.0],
        ]
    )
    params = SolverParams()
    params.appear_cost = None
    params.iou_cost = None  # points graphs have no iou edge attribute
    params.window_size = 2
    params.single_window_start = 1

    solution = solve(params, points)

    assert solution.num_nodes() > 0
    for node in solution.node_ids():
        node_time = solution.nodes[node]["t"]
        assert 1 <= node_time < 3, f"Node {node} has time {node_time}, expected 1-2"


def test_solve_single_window_invalid_start(segmentation_3d):
    """Test that invalid window_start raises ValueError."""

    params = SolverParams()
    params.appear_cost = None
    params.window_size = 3
    params.single_window_start = 100  # Beyond data range (5 frames)

    with pytest.raises(ValueError, match="beyond last frame"):
        solve(params, segmentation_3d)


def test_solve_points_uses_world_distances():
    """Positions stay in pixels; the scale governs the distance-based decisions.

    The points move 6 pixels along y and 0 along x per frame. With an isotropic
    scale that is well inside max_edge_distance, but stretching y by 5 puts every
    link 30 world units apart, beyond the candidate-edge budget, so nothing links
    up. Either way the solved graph carries the original pixel coordinates.
    """
    points = np.array(
        [
            [0, 50.0, 50.0],
            [1, 56.0, 50.0],
            [2, 62.0, 50.0],
        ]
    )
    params = SolverParams()
    params.appear_cost = None
    params.iou_cost = None  # points graphs have no iou edge attribute
    params.max_edge_distance = 10

    solution = solve(params, points)
    assert solution.num_edges() == 2

    scaled = solve(params, points, scale=[1.0, 5.0, 1.0])
    assert scaled.num_edges() == 0

    for graph in (solution, scaled):
        positions = {node: list(graph.nodes[node]["pos"]) for node in graph.node_ids()}
        for node, pos in positions.items():
            np.testing.assert_allclose(pos, points[node][1:])
