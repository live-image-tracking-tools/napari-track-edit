from __future__ import annotations

import logging
import time
from collections.abc import Callable

import ilpy
import numpy as np
import tracksdata as td
from funtracks.candidate_graph import (
    compute_graph_from_points_list,
    compute_graph_from_seg,
)
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from motile import Solver, TrackGraph
from motile.constraints import MaxChildren, MaxParents, Pin
from motile.costs import (
    EdgeDistanceCost,
    EdgeSelectedCost,
    NodeAppearCost,
    NodeSplitCost,
)

from .solver_params import SolverParams

logger = logging.getLogger(__name__)

PIN_ATTR = "pinned"


def solve(
    solver_params: SolverParams,
    input_data: np.ndarray,
    on_solver_update: Callable | None = None,
    scale: list | None = None,
    cand_graph: td.graph.GraphView | None = None,
) -> td.graph.GraphView:
    """Get a tracking solution for the given segmentation and parameters.

    Constructs a candidate graph from the segmentation (unless one is
    provided), a solver from the parameters, and then runs solving and
    returns a networkx graph with the solution. Most of this functionality
    is implemented in the motile toolbox.

    Args:
        solver_params (SolverParams): The solver parameters to use when
            initializing the solver
        input_data (np.ndarray): The input segmentation or points list to run
            tracking on. If 2D, assumed to be a list of points, otherwise a
            segmentation.
        on_solver_update (Callable, optional): A function that is called
            whenever the motile solver emits an event. The function should take
            a dictionary of event data, and can be used to track progress of
            the solver. Defaults to None.
        scale (list, optional): The scale of the data in each dimension.
        cand_graph (td.graph.GraphView, optional): A pre-built candidate graph. If
            provided, skips candidate graph construction (except for
            single-window mode which always builds its own). Defaults to None.

    Returns:
        td.graph.GraphView: A solution graph where the ids of the nodes correspond to
            the time and ids of the passed in segmentation labels. See funtracks for exact
            implementation details.
    """
    # Single window mode: slice input, solve, and return early
    if (
        solver_params.window_size is not None
        and solver_params.single_window_start is not None
    ):
        result = _solve_single_window(
            input_data, solver_params, on_solver_update, scale
        )
    else:
        if cand_graph is None:
            cand_graph = build_candidate_graph(input_data, solver_params, scale)

        if solver_params.window_size is not None:
            result = _solve_chunked(cand_graph, solver_params, on_solver_update, scale)
        else:
            result = _solve_full(cand_graph, solver_params, on_solver_update, scale)

    if input_data.ndim != 2:
        result._update_metadata(shape=input_data.shape)

    return result


def build_candidate_graph(
    input_data: np.ndarray,
    solver_params: SolverParams,
    scale: list | None = None,
    time_offset: int = 0,
) -> td.graph.GraphView:
    """Build the candidate graph from input data."""
    if input_data.ndim == 2:
        cand_graph = compute_graph_from_points_list(
            input_data, solver_params.max_edge_distance, scale=scale
        )
    else:
        cand_graph = compute_graph_from_seg(
            input_data,
            solver_params.max_edge_distance,
            iou=solver_params.iou_cost is not None,
            scale=scale,
            t_start=time_offset,
        )
    logger.debug("Cand graph has %d nodes", cand_graph.num_nodes())
    return cand_graph


def _solve_full(
    cand_graph: td.graph.GraphView,
    solver_params: SolverParams,
    on_solver_update: Callable | None = None,
    scale: list | None = None,
) -> td.graph.GraphView:
    """Solve the tracking problem on the full candidate graph at once."""
    solver = construct_solver(cand_graph, solver_params, scale)
    start_time = time.time()
    solution = solver.solve(verbose=False, on_event=on_solver_update)
    logger.info("Solution took %.2f seconds", time.time() - start_time)

    solution_tg = solver.get_selected_subgraph(solution=solution)
    selected_nodes = list(solution_tg.nodes.keys())
    selected_edges = set(solution_tg.edges.keys())
    logger.debug("Solution graph has %d nodes", len(selected_nodes))
    result = cand_graph.filter(node_ids=selected_nodes).subgraph().detach()
    for u, v in list(result.edge_list()):
        if (u, v) not in selected_edges:
            result.remove_edge(u, v)
    return result.filter().subgraph()


def _solve_window(
    window_subgraph: td.graph.GraphView,
    solver_params: SolverParams,
    on_solver_update: Callable | None = None,
    scale: list | None = None,
) -> td.graph.GraphView | None:
    """Solve a single window subgraph.

    This is the core solving logic shared by both single window mode and
    chunked solving.

    Args:
        window_subgraph: The subgraph for this window. If any nodes or edges
            have the PIN_ATTR attribute set, a Pin constraint will be used.
        solver_params: The solver parameters.
        on_solver_update: Callback for solver progress updates.
        scale: The scale of the data in each dimension.

    Returns:
        The solution graph for this window, or None if the window has no nodes.
    """
    if window_subgraph.num_nodes() == 0:
        return None

    # Handle edge case: if no edges, motile can't solve — return all nodes directly
    if window_subgraph.num_edges() == 0:
        logger.info(
            "Window has no edges (%d nodes), returning nodes directly",
            window_subgraph.num_nodes(),
        )
        return window_subgraph

    solver = construct_solver(window_subgraph, solver_params, scale)
    start_time = time.time()
    solution = solver.solve(verbose=False, on_event=on_solver_update)
    logger.info("Window solved in %.2f seconds", time.time() - start_time)
    solution_tg = solver.get_selected_subgraph(solution=solution)
    selected_nodes = list(solution_tg.nodes.keys())
    selected_edges = set(solution_tg.edges.keys())
    result = window_subgraph.filter(node_ids=selected_nodes).subgraph().detach()
    for u, v in list(result.edge_list()):
        if (u, v) not in selected_edges:
            result.remove_edge(u, v)
    return result.filter().subgraph()


def _solve_single_window(
    input_data: np.ndarray,
    solver_params: SolverParams,
    on_solver_update: Callable | None = None,
    scale: list | None = None,
) -> td.graph.GraphView:
    """Solve a single window for interactive parameter testing.

    Builds the full candidate graph, filters it to the window frames, and solves.
    Node times are naturally correct (no adjustment needed).

    Args:
        input_data: The full input segmentation or points list.
        solver_params: The solver parameters including window_size and single_window_start.
        on_solver_update: Callback for solver progress updates.
        scale: The scale of the data in each dimension.

    Returns:
        The solution graph for the requested window.

    Raises:
        ValueError: If single_window_start is beyond the data range.
    """
    window_start = solver_params.single_window_start
    window_size = solver_params.window_size
    window_end = window_start + window_size

    # Validate window_start against data range
    max_time = (
        input_data.shape[0] - 1 if input_data.ndim != 2 else int(input_data[:, 0].max())
    )
    if window_start > max_time:
        raise ValueError(
            f"single_window_start ({window_start}) is beyond last frame ({max_time})"
        )

    logger.info(
        "Solving single window: frames %d to %d (exclusive)",
        window_start,
        window_end,
    )

    # Slice input to window frames only — avoids building full candidate graph
    if input_data.ndim == 2:
        # Points list: filter rows where time column (col 0) is in [window_start, window_end)
        row_mask = (input_data[:, 0] >= window_start) & (input_data[:, 0] < window_end)
        sliced_input = input_data[row_mask]
    else:
        # Segmentation: numpy slice is a view (no copy)
        sliced_input = input_data[window_start:window_end]

    cand_graph = build_candidate_graph(
        sliced_input, solver_params, scale, time_offset=window_start
    )

    start_time = time.time()
    solution = _solve_window(cand_graph, solver_params, on_solver_update, scale)
    logger.info("Single window solution took %.2f seconds", time.time() - start_time)

    if solution is None:
        logger.warning("Window has no nodes")
        return create_empty_graphview_graph()

    logger.debug(
        "Single window solution has %d nodes, %d edges",
        solution.num_nodes(),
        solution.num_edges(),
    )
    return solution


def _solve_chunked(
    cand_graph: td.graph.GraphView,
    solver_params: SolverParams,
    on_solver_update: Callable | None = None,
    scale: list | None = None,
) -> td.graph.GraphView:
    """Solve the tracking problem in chunks using a sliding window approach.

    This function solves the tracking problem in windows of `window_size` frames,
    with `overlap_size` frames of overlap between consecutive windows. The overlap
    region from the previous window is pinned (fixed) when solving the next window
    to maintain consistency across windows.

    Args:
        cand_graph: The full candidate graph with all nodes and edges.
        solver_params: The solver parameters including window_size and overlap_size.
        on_solver_update: Callback for solver progress updates.
        scale: The scale of the data in each dimension.

    Returns:
        The combined solution graph from all windows.
    """
    window_size = solver_params.window_size
    overlap_size = solver_params.overlap_size
    if overlap_size is None:
        raise ValueError("overlap_size is required when window_size is set")

    if overlap_size >= window_size:
        raise ValueError(
            f"overlap_size ({overlap_size}) must be less than window_size ({window_size})"
        )

    # Get the frame range from the candidate graph
    times = [cand_graph.nodes[n]["t"] for n in cand_graph.node_ids()]
    if not times:
        return create_empty_graphview_graph()

    min_time = min(times)
    max_time = max(times)
    total_frames = max_time - min_time + 1

    # Warn if window_size is larger than data - chunking won't help
    if window_size >= total_frames:
        logger.warning(
            "window_size (%d) is >= total frames (%d), "
            "chunked solving will behave like full solving",
            window_size,
            total_frames,
        )

    logger.info(
        "Starting chunked solve: %d frames, window_size=%d, overlap_size=%d",
        total_frames,
        window_size,
        overlap_size,
    )

    all_selected_nodes: set[int] = set()
    all_selected_edges: set[tuple] = set()
    window_start = min_time
    window_num = 0
    start_time = time.time()

    while window_start <= max_time:
        window_end = min(window_start + window_size, max_time + 1)
        window_num += 1

        logger.info(
            "Solving window %d: frames %d to %d (exclusive)",
            window_num,
            window_start,
            window_end,
        )

        # Extract subgraph for this window (includes PIN_ATTR if set on cand_graph)
        nodes_in_window = [
            n
            for n in cand_graph.node_ids()
            if window_start <= cand_graph.nodes[n]["t"] < window_end
        ]
        window_subgraph = cand_graph.filter(node_ids=nodes_in_window).subgraph()

        # Solve this window
        window_solution = _solve_window(
            window_subgraph, solver_params, on_solver_update, scale
        )

        if window_solution is None:
            logger.warning("Window %d has no nodes, skipping", window_num)
            window_start += window_size - overlap_size
            continue

        logger.debug(
            "Window %d solution has %d nodes, %d edges",
            window_num,
            window_solution.num_nodes(),
            window_solution.num_edges(),
        )

        # Collect selected nodes and edges from this window, excluding the pinned
        # overlap region that was already committed from the previous window.
        overlap_start = window_start + window_size - overlap_size
        from_frame = None if window_num == 1 else window_start + overlap_size
        for nid in window_solution.node_ids():
            if from_frame is None or window_solution.nodes[nid]["t"] >= from_frame:
                all_selected_nodes.add(nid)
        for u, v in window_solution.edge_list():
            u_time = window_solution.nodes[u]["t"]
            if from_frame is None or u_time >= from_frame:
                all_selected_edges.add((u, v))

        # Set PIN_ATTR on candidate graph for the overlap region (for next window)
        if window_end <= max_time:
            _set_pinning_on_graph(
                cand_graph, window_solution, overlap_start, window_end
            )

        # Move window
        window_start += window_size - overlap_size

    logger.info(
        "Chunked solve complete: %d windows, %.2f seconds total",
        window_num,
        time.time() - start_time,
    )

    if not all_selected_nodes:
        return create_empty_graphview_graph()

    result = cand_graph.filter(node_ids=list(all_selected_nodes)).subgraph().detach()
    for u, v in list(result.edge_list()):
        if (u, v) not in all_selected_edges:
            result.remove_edge(u, v)
    result = result.filter().subgraph()
    logger.debug(
        "Combined solution has %d nodes, %d edges",
        result.num_nodes(),
        result.num_edges(),
    )
    return result


def _set_pinning_on_graph(
    cand_graph: td.graph.GraphView,
    solution_graph: td.graph.GraphView,
    overlap_start: int,
    overlap_end: int,
) -> None:
    """Set PIN_ATTR on candidate graph nodes/edges in the overlap region.

    For all nodes and edges in the overlap region [overlap_start, overlap_end),
    sets PIN_ATTR to True if selected in the solution, False if not selected.

    Args:
        cand_graph: The full candidate graph to modify in place.
        solution_graph: The solution graph from the current window.
        overlap_start: Start frame of overlap region (inclusive).
        overlap_end: End frame of overlap region (exclusive).
    """
    import polars as pl

    solution_nodes = set(solution_graph.node_ids())
    solution_edges = {tuple(e) for e in solution_graph.edge_list()}

    # Ensure PIN_ATTR columns exist in schema (default None = not pinned)
    if PIN_ATTR not in cand_graph.node_attr_keys():
        cand_graph.add_node_attr_key(PIN_ATTR, pl.Boolean, default_value=None)
    if PIN_ATTR not in cand_graph.edge_attr_keys():
        cand_graph.add_edge_attr_key(PIN_ATTR, pl.Boolean, default_value=None)

    # Pin nodes in the overlap region
    nodes_to_pin = []
    pin_node_values = []
    for node in cand_graph.node_ids():
        node_time = cand_graph.nodes[node]["t"]
        if overlap_start <= node_time < overlap_end:
            nodes_to_pin.append(node)
            pin_node_values.append(node in solution_nodes)
    if nodes_to_pin:
        cand_graph.update_node_attrs(
            node_ids=nodes_to_pin, attrs={PIN_ATTR: pin_node_values}
        )

    # Pin edges where both endpoints are in the overlap region
    edges_to_pin = []
    pin_edge_values = []
    for u, v in cand_graph.edge_list():
        u_time = cand_graph.nodes[u]["t"]
        v_time = cand_graph.nodes[v]["t"]
        if (
            overlap_start <= u_time < overlap_end
            and overlap_start <= v_time < overlap_end
        ):
            edges_to_pin.append(cand_graph.edge_id(u, v))
            pin_edge_values.append((u, v) in solution_edges)
    if edges_to_pin:
        cand_graph.update_edge_attrs(
            edge_ids=edges_to_pin, attrs={PIN_ATTR: pin_edge_values}
        )


_SKIP_ATTRS = {td.DEFAULT_ATTR_KEYS.MASK, td.DEFAULT_ATTR_KEYS.BBOX}


def construct_solver(
    cand_graph: td.graph.GraphView,
    solver_params: SolverParams,
    scale: list | None = None,
) -> Solver:
    """Construct a motile solver with the parameters specified in the solver
    params object.

    Args:
        cand_graph (td.graph.GraphView): The candidate graph to use in the solver
        solver_params (SolverParams): The costs and constraints to use in
            the solver
        scale (list | None): The scale of the data in each dimension (including
            time). Node positions on the candidate graph are in pixel coordinates,
            so they are converted to world units before being handed to the
            solver, keeping the distance costs comparable across anisotropic axes.

    Returns:
        Solver: A motile solver with the specified graph, costs, and
            constraints.
    """
    tg = TrackGraph(frame_attribute="t")

    # Bulk-fetch node attributes (one polars scan instead of N individual scans)
    node_df = cand_graph.node_attrs()
    skip_cols = [c for c in node_df.columns if c in _SKIP_ATTRS]
    if skip_cols:
        node_df = node_df.drop(skip_cols)
    spatial_scale = None
    if scale is not None and not all(float(s) == 1.0 for s in scale[1:]):
        spatial_scale = np.asarray(scale[1:], dtype=float)
    node_id_col = td.DEFAULT_ATTR_KEYS.NODE_ID
    for row in node_df.rows(named=True):
        node_id = row.pop(node_id_col)
        if spatial_scale is not None and "pos" in row:
            row["pos"] = (np.asarray(row["pos"], dtype=float) * spatial_scale).tolist()
        tg.add_node(node_id, row)

    # Bulk-fetch edge attributes (one polars scan instead of N individual scans)
    edge_df = cand_graph.edge_attrs()
    src_col = td.DEFAULT_ATTR_KEYS.EDGE_SOURCE
    tgt_col = td.DEFAULT_ATTR_KEYS.EDGE_TARGET
    eid_col = td.DEFAULT_ATTR_KEYS.EDGE_ID
    for row in edge_df.rows(named=True):
        src = row.pop(src_col)
        tgt = row.pop(tgt_col)
        row.pop(eid_col)
        tg.add_edge((src, tgt), row)

    solver = Solver(tg)
    solver.add_constraint(MaxChildren(solver_params.max_children))
    solver.add_constraint(MaxParents(1))
    solver.add_constraint(Pin(PIN_ATTR))

    # Using EdgeDistance instead of EdgeSelection for the constant cost because
    # the attribute is not optional for EdgeSelection (yet)
    if solver_params.edge_selection_cost is not None:
        solver.add_cost(
            EdgeDistanceCost(
                weight=0,
                position_attribute="pos",
                constant=solver_params.edge_selection_cost,
            ),
            name="edge_const",
        )
    if solver_params.appear_cost is not None:
        solver.add_cost(NodeAppearCost(solver_params.appear_cost))
    if solver_params.division_cost is not None:
        solver.add_cost(NodeSplitCost(constant=solver_params.division_cost))

    if solver_params.distance_cost is not None:
        solver.add_cost(
            EdgeDistanceCost(
                position_attribute="pos",
                weight=solver_params.distance_cost,
            ),
            name="distance",
        )
    if solver_params.iou_cost is not None:
        solver.add_cost(
            EdgeSelectedCost(
                weight=solver_params.iou_cost,
                attribute="iou",
            ),
            name="iou",
        )
    return solver


def get_solver_name() -> str:
    """Return the name of the ILP solver backend that will be used.

    Attempts Gurobi first; falls back to SCIP.
    """
    try:
        ilpy.solver_backends.create_solver_backend(ilpy.Preference.Gurobi)
        return "Gurobi"
    except RuntimeError:
        return "SCIP"
