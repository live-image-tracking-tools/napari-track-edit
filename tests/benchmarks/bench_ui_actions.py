"""UI action benchmarks (require a napari GUI / display).

Cover the common interactive actions at scale: loading, selection, display-mode
switching, tree-view rendering, and editing. Each benchmark builds its own app in
``setup`` (not timed) and measures a single action with
``benchmark.pedantic(..., rounds=ROUNDS, iterations=1)``. Each action triggers a
full refresh cascade that can take seconds at scale; we collect a few rounds
(``ROUNDS``) so the report can gate on the median and ignore a single noisy run.
pytest-benchmark re-runs ``setup`` before every round, so mutating benchmarks
still start each round from fresh state.

In CI these run under aganders3/headless-gui (Xvfb-backed GL). They will segfault
under the ``offscreen`` Qt platform, which lacks a real GL context.
"""

from __future__ import annotations

from synthetic_data import pick_nodes, tracklet_nodes

# Rounds pytest-benchmark collects per measurement. The report gates on the *median*
# across rounds, so >=3 rounds lets a single transient spike be ignored (see
# benchmark_pr.py). We run everything with 3 rounds for that noise robustness, except
# the two ~50s bulk operations -- for them the expensive work is in the action or the
# setup (which pedantic re-runs every round), so 3 rounds would triple an already
# minutes-long test. Those stay single-shot to keep CI time bounded.
ROUNDS = 3  # default: enough samples for a robust median
ROUNDS_BULK = 1  # ~50s bulk delete / its undo -- too expensive to repeat

# ----------------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------------


def test_add_tracks(benchmark, make_napari_viewer, shared_tracks):
    """Open viewer + add tracks (creates points/graph/labels layers + tree data)."""
    from motile_tracker.application_menus import StartupWidget
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

    def setup():
        viewer = make_napari_viewer()
        StartupWidget(viewer, mode="editing")
        tv = TracksViewer.get_instance(viewer)
        return (tv, shared_tracks), {}

    benchmark.pedantic(
        lambda tv, tracks: tv.tracks_list.add_tracks(tracks, "synthetic"),
        setup=setup,
        rounds=ROUNDS,
        iterations=1,
    )


# ----------------------------------------------------------------------------------
# Selection / interaction (read-only w.r.t. the graph)
# ----------------------------------------------------------------------------------


def test_click_node_treeview(benchmark, build_app, shared_tracks):
    def setup():
        _, _, tree = build_app(shared_tracks)
        return (tree, pick_nodes(shared_tracks)["tree_node"]), {}

    benchmark.pedantic(
        lambda tree, node: tree.tree_widget.node_clicked.emit(node, False),
        setup=setup,
        rounds=ROUNDS,
        iterations=1,
    )


def test_click_node_canvas(benchmark, build_app, shared_tracks):
    def setup():
        _, tv, _ = build_app(shared_tracks)
        return (tv, pick_nodes(shared_tracks)["canvas_node"]), {}

    benchmark.pedantic(
        lambda tv, node: tv.selected_nodes.add(node, False),
        setup=setup,
        rounds=ROUNDS,
        iterations=1,
    )


def test_set_display_mode_lineage(benchmark, build_app, shared_tracks):
    """Toggle to lineage mode with a node selected (filter + extract_lineage + update)."""

    def setup():
        _, tv, _ = build_app(shared_tracks)
        tv.selected_nodes.reset()
        tv.selected_nodes.add(pick_nodes(shared_tracks)["canvas_node"], False)
        return (tv,), {}

    benchmark.pedantic(
        lambda tv: tv.set_display_mode("lineage"),
        setup=setup,
        rounds=ROUNDS,
        iterations=1,
    )


# ----------------------------------------------------------------------------------
# Tree view rendering (read-only)
# ----------------------------------------------------------------------------------


def test_tree_flip_axes(benchmark, build_app, shared_tracks):
    def setup():
        _, _, tree = build_app(shared_tracks)
        return (tree,), {}

    benchmark.pedantic(
        lambda tree: tree.flip_axes(), setup=setup, rounds=ROUNDS, iterations=1
    )


def test_tree_feature_recolor(benchmark, build_app, shared_tracks):
    """Switch tree coloring to a feature (full pyqtgraph redraw)."""

    def setup():
        _, _, tree = build_app(shared_tracks)
        return (tree,), {}

    benchmark.pedantic(
        lambda tree: tree.toggle_feature_mode(),
        setup=setup,
        rounds=ROUNDS,
        iterations=1,
    )


def test_label_colormap_rebuild(benchmark, build_app, shared_tracks):
    """Rebuild the DirectLabelColormap for the segmentation layer."""

    def setup():
        _, tv, _ = build_app(shared_tracks)
        return (tv.tracking_layers.seg_layer,), {}

    benchmark.pedantic(
        lambda seg: seg._get_colormap(),
        setup=setup,
        rounds=ROUNDS,
        iterations=1,
    )


# ----------------------------------------------------------------------------------
# Editing (mutating -> fresh_tracks each time)
# ----------------------------------------------------------------------------------


def test_delete_node(benchmark, build_app, fresh_tracks):
    def setup():
        _, tv, _ = build_app(fresh_tracks)
        tv.selected_nodes.reset()
        tv.selected_nodes.add(pick_nodes(fresh_tracks)["del_node"], False)
        return (tv,), {}

    benchmark.pedantic(
        lambda tv: tv.delete_node(), setup=setup, rounds=ROUNDS, iterations=1
    )


def test_delete_nodes_bulk(benchmark, build_app, fresh_tracks):
    """Delete a whole tracklet (many nodes) in a single action.

    Exercises the multi-node UserDeleteNodes path. Since the refresh runs once
    regardless of count, this vs test_delete_node shows fixed-refresh overhead vs
    marginal per-node cost, and catches a regression to refresh-per-node.
    """

    def setup():
        _, tv, _ = build_app(fresh_tracks)
        nodes = tracklet_nodes(fresh_tracks, pick_nodes(fresh_tracks)["del_node"])
        tv.selected_nodes.reset()
        tv.selected_nodes.add_list(nodes)
        return (tv,), {}

    benchmark.pedantic(
        lambda tv: tv.delete_node(), setup=setup, rounds=ROUNDS_BULK, iterations=1
    )


def test_undo_bulk_delete(benchmark, build_app, fresh_tracks):
    """Undo a bulk (whole-tracklet) delete -- restores many nodes in one action."""

    def setup():
        _, tv, _ = build_app(fresh_tracks)
        nodes = tracklet_nodes(fresh_tracks, pick_nodes(fresh_tracks)["del_node"])
        tv.selected_nodes.reset()
        tv.selected_nodes.add_list(nodes)
        tv.delete_node()
        return (tv,), {}

    benchmark.pedantic(
        lambda tv: tv.undo(), setup=setup, rounds=ROUNDS_BULK, iterations=1
    )


def test_delete_edge(benchmark, build_app, fresh_tracks):
    def setup():
        _, tv, _ = build_app(fresh_tracks)
        u, v = pick_nodes(fresh_tracks)["del_edge"]
        tv.selected_nodes.reset()
        tv.selected_nodes.add(u, False)
        tv.selected_nodes.add(v, True)
        return (tv,), {}

    benchmark.pedantic(
        lambda tv: tv.delete_edge(), setup=setup, rounds=ROUNDS, iterations=1
    )


def test_create_edge(benchmark, build_app, fresh_tracks):
    """Recreate an edge that was just broken (guaranteed-valid, no force dialog)."""

    def setup():
        _, tv, _ = build_app(fresh_tracks)
        u, v = pick_nodes(fresh_tracks)["del_edge"]
        # Break the edge first so re-adding it is a valid action.
        tv.selected_nodes.reset()
        tv.selected_nodes.add(u, False)
        tv.selected_nodes.add(v, True)
        tv.delete_edge()
        tv.selected_nodes.reset()
        tv.selected_nodes.add(u, False)
        tv.selected_nodes.add(v, True)
        return (tv,), {}

    benchmark.pedantic(
        lambda tv: tv.create_edge(), setup=setup, rounds=ROUNDS, iterations=1
    )


def test_undo(benchmark, build_app, fresh_tracks):
    def setup():
        _, tv, _ = build_app(fresh_tracks)
        tv.selected_nodes.reset()
        tv.selected_nodes.add(pick_nodes(fresh_tracks)["del_node"], False)
        tv.delete_node()
        return (tv,), {}

    benchmark.pedantic(lambda tv: tv.undo(), setup=setup, rounds=ROUNDS, iterations=1)


def test_redo(benchmark, build_app, fresh_tracks):
    def setup():
        _, tv, _ = build_app(fresh_tracks)
        tv.selected_nodes.reset()
        tv.selected_nodes.add(pick_nodes(fresh_tracks)["del_node"], False)
        tv.delete_node()
        tv.undo()
        return (tv,), {}

    benchmark.pedantic(lambda tv: tv.redo(), setup=setup, rounds=ROUNDS, iterations=1)
