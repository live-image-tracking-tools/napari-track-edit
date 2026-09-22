import napari
import numpy as np
import pandas as pd
import polars as pl
from funtracks.annotators import TrackAnnotator
from funtracks.data_model import SolutionTracks
from funtracks.features import Feature
from funtracks.user_actions import UserDeleteEdge, UserDeleteNodes
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph

from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_sorted_tracks,
    get_features_from_tracks,
    get_sorted_track_ids,
    get_tracklets,
    order_roots_by_prev,
)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Make a track_df comparable: stable row order, hashable color/state cells."""
    df = df.sort_values("node_id").reset_index(drop=True)
    df = df.copy()
    df["color"] = df["color"].apply(lambda c: tuple(np.asarray(c).tolist()))
    df["state"] = df["state"].astype(str)
    return df[sorted(df.columns)]


def _assert_reuse_matches_full(tracks, colormap, prev_attrs, prev_axis):
    """The cached-attr reuse path must produce the same track_df as a full fetch."""
    reuse_df, reuse_axis, _ = extract_sorted_tracks(
        tracks, colormap, prev_axis, cached_node_attrs=prev_attrs
    )
    full_df, full_axis, _ = extract_sorted_tracks(
        tracks, colormap, prev_axis, cached_node_attrs=None
    )
    pd.testing.assert_frame_equal(_normalize(reuse_df), _normalize(full_df))
    assert reuse_axis == full_axis


def test_extract_sorted_tracks_attr_reuse_equivalence(solution_tracks_2d):
    """Reusing cached node attributes (refetching only tracklet_id) must yield the
    exact same dataframe as a full fetch, for a no-op, a plain delete, a
    division-adjacent delete (relabels a tracklet), and an edge delete."""
    tracks = solution_tracks_2d
    colormap = napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)

    # Full build → cache the node attributes.
    _, axis, attrs = extract_sorted_tracks(tracks, colormap)

    # (a) no edit: cache == current node set
    _assert_reuse_matches_full(tracks, colormap, attrs, axis)

    # (b) delete a child node at the division (relabels the sibling's tracklet, so
    # the tracklet_id refetch must reflect the change)
    UserDeleteNodes(tracks, nodes=[2])
    _assert_reuse_matches_full(tracks, colormap, attrs, axis)


def test_extract_sorted_tracks_attr_reuse_after_edge_delete(solution_tracks_2d):
    """Deleting an edge changes tracklet structure; the tracklet refetch in the reuse
    path must capture it so the result matches a full fetch."""
    import tracksdata as td

    tracks = solution_tracks_2d
    colormap = napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)
    _, axis, attrs = extract_sorted_tracks(tracks, colormap)

    # delete the edge from the division parent (1) to child (3)
    edge_df = tracks.graph.edge_attrs(
        attr_keys=[td.DEFAULT_ATTR_KEYS.EDGE_SOURCE, td.DEFAULT_ATTR_KEYS.EDGE_TARGET]
    )
    src = edge_df[td.DEFAULT_ATTR_KEYS.EDGE_SOURCE].to_list()
    tgt = edge_df[td.DEFAULT_ATTR_KEYS.EDGE_TARGET].to_list()
    UserDeleteEdge(tracks, (int(src[0]), int(tgt[0])))

    _assert_reuse_matches_full(tracks, colormap, attrs, axis)


def test_track_df(solution_tracks_2d):
    tracks = solution_tracks_2d
    ann = TrackAnnotator(tracks, lineage_key="lineage_id", tracklet_key="track_id")
    tracks.graph.add_node_attr_key("custom_attr", default_value=0, dtype=pl.Int64)

    for node in tracks.graph.node_ids():
        if node != 2:
            tracks.graph.nodes[node]["custom_attr"] = node * 10
    tracks.features["custom_attr"] = Feature(
        feature_type="node",
        value_type="int",
        num_values=1,
    )

    ann.compute()

    colormap = napari.utils.colormaps.label_colormap(
        49,
        seed=0.5,
        background_value=0,
    )

    track_df, _, _ = extract_sorted_tracks(tracks, colormap)
    assert isinstance(track_df, pd.DataFrame)
    assert track_df.loc[track_df["node_id"] == 1, "custom_attr"].values[0] == 10
    assert track_df.loc[track_df["node_id"] == 2, "custom_attr"].values[0] == 0


def test_get_features_from_tracks_individual_pos_attrs():
    """get_features_from_tracks must not crash when pos_attr is a list.

    When SolutionTracks is built with pos_attr=["y", "x"], funtracks registers
    each axis as a Feature without a display_name key (NotRequired per the TypedDict).
    The function must fall back to the dict key instead of raising KeyError.
    """
    graph = create_empty_graphview_graph(
        node_attributes=["y", "x"],
        ndim=3,
    )
    graph.bulk_add_nodes(
        nodes=[{"t": 0, "y": 10.0, "x": 20.0, "solution": True}],
        indices=[1],
    )
    tracks = SolutionTracks(graph=graph, ndim=3, time_attr="t", pos_attr=["y", "x"])

    features = get_features_from_tracks(tracks)

    assert "y" in features
    assert "x" in features


def test_extract_sorted_tracks_incomplete_lineage():
    """BFS must not merge tracklets across track_id boundaries in incomplete graphs.

    Full lineage: A(tk=1) -> B(tk=1, divides) -> C(tk=2) and B -> D(tk=3).
    Loaded subset: only A, B, C (D is missing). B appears to have a single child
    (C), so topology alone does not identify it as a division node. Without the
    track_id guard the BFS follows A->B->C and merges all three into one tracklet.
    With the fix, the BFS stops at the B->C edge (track_id 1 != 2), producing
    separate tracklets {A, B} and {C}.
    """
    graph = create_empty_graphview_graph(
        node_attributes=["pos", "track_id"],
        ndim=3,
    )
    graph.bulk_add_nodes(
        nodes=[
            {"t": 0, "pos": [0.0, 0.0], "track_id": 1, "solution": True},  # A, node 1
            {"t": 1, "pos": [0.0, 0.0], "track_id": 1, "solution": True},  # B, node 2
            {"t": 2, "pos": [0.0, 0.0], "track_id": 2, "solution": True},  # C, node 3
        ],
        indices=[1, 2, 3],
    )
    graph.bulk_add_edges(
        [
            {"source_id": 1, "target_id": 2, "solution": True},  # A -> B
            {
                "source_id": 2,
                "target_id": 3,
                "solution": True,
            },  # B -> C (cross boundary)
        ]
    )
    tracks = SolutionTracks(
        graph=graph, ndim=3, time_attr="t", tracklet_attr="track_id"
    )

    colormap = napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)
    track_df, _, _ = extract_sorted_tracks(tracks, colormap)

    # C (node 3) must be in its own tracklet with track_id=2, not merged into A+B (track_id=1)
    node_c_track_id = track_df.loc[track_df["node_id"] == 3, "track_id"].values[0]
    assert node_c_track_id == 2, (
        f"Node C was merged into track {node_c_track_id} instead of its own track (2). "
        "BFS crossed a track_id boundary in an incomplete lineage."
    )


# --- get_tracklets unit tests ---


def _run_get_tracklets(
    parent_to_children, child_to_parent, node_ids, dividing, track_ids
):
    return get_tracklets(
        parent_to_children,
        child_to_parent,
        node_ids,
        dividing,
        track_ids,
    )


def _as_frozensets(tracklets):
    return {frozenset(t) for t in tracklets}


def test_get_tracklets_linear_chain():
    # 1 -> 2 -> 3, single track_id
    result = _run_get_tracklets(
        parent_to_children={1: [2], 2: [3]},
        child_to_parent={2: 1, 3: 2},
        node_ids=[1, 2, 3],
        dividing=set(),
        track_ids={1: 0, 2: 0, 3: 0},
    )
    assert _as_frozensets(result) == {frozenset({1, 2, 3})}


def test_get_tracklets_isolated_nodes():
    result = _run_get_tracklets(
        parent_to_children={},
        child_to_parent={},
        node_ids=[1, 2, 3],
        dividing=set(),
        track_ids={1: 0, 2: 1, 3: 2},
    )
    assert _as_frozensets(result) == {frozenset({1}), frozenset({2}), frozenset({3})}


def test_get_tracklets_division_splits_into_three():
    # Node 1 divides into 2 and 3 — node 1 is in dividing_node_set.
    # Expected tracklets: {1}, {2}, {3}
    result = _run_get_tracklets(
        parent_to_children={1: [2, 3]},
        child_to_parent={2: 1, 3: 1},
        node_ids=[1, 2, 3],
        dividing={1},
        track_ids={1: 0, 2: 1, 3: 2},
    )
    assert _as_frozensets(result) == {frozenset({1}), frozenset({2}), frozenset({3})}


def test_get_tracklets_division_children_continue():
    # 1 divides into 2 and 3; each child continues: 2->4, 3->5
    # Expected: {1}, {2, 4}, {3, 5}
    result = _run_get_tracklets(
        parent_to_children={1: [2, 3], 2: [4], 3: [5]},
        child_to_parent={2: 1, 3: 1, 4: 2, 5: 3},
        node_ids=[1, 2, 3, 4, 5],
        dividing={1},
        track_ids={1: 0, 2: 1, 3: 2, 4: 1, 5: 2},
    )
    assert _as_frozensets(result) == {
        frozenset({1}),
        frozenset({2, 4}),
        frozenset({3, 5}),
    }


def test_get_tracklets_track_id_boundary():
    # 1(tk=0) -> 2(tk=0) -> 3(tk=1): BFS must stop at the 2->3 edge.
    result = _run_get_tracklets(
        parent_to_children={1: [2], 2: [3]},
        child_to_parent={2: 1, 3: 2},
        node_ids=[1, 2, 3],
        dividing=set(),
        track_ids={1: 0, 2: 0, 3: 1},
    )
    assert _as_frozensets(result) == {frozenset({1, 2}), frozenset({3})}


def test_get_tracklets_partition_property():
    # Every node appears in exactly one tracklet.
    result = _run_get_tracklets(
        parent_to_children={1: [2, 3], 2: [4]},
        child_to_parent={2: 1, 3: 1, 4: 2},
        node_ids=[1, 2, 3, 4],
        dividing={1},
        track_ids={1: 0, 2: 1, 3: 2, 4: 1},
    )
    all_nodes = [n for t in result for n in t]
    assert sorted(all_nodes) == [1, 2, 3, 4]
    assert len(all_nodes) == len(set(all_nodes))


def test_extract_sorted_tracks_cache_ignored_when_feature_set_changes(
    solution_tracks_2d,
):
    """Enabling a feature must not reuse a cache that predates it.

    Enabling or disabling a feature changes which columns the dataframe needs,
    but goes through no action, so nothing marks the cache stale. Reusing it
    then raised ColumnNotFoundError for the new column. The guard is on the
    column set, so it covers enable, disable and re-enable alike.
    """
    tracks = solution_tracks_2d
    colormap = napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)

    _, axis, attrs = extract_sorted_tracks(tracks, colormap)

    # A feature that was not in the frame the cache was built from.
    tracks.graph.add_node_attr_key("extra_attr", default_value=0, dtype=pl.Int64)
    tracks.features["extra_attr"] = Feature(
        feature_type="node", value_type="int", num_values=1
    )

    # Must fall back to a full fetch rather than raise.
    df, _, new_attrs = extract_sorted_tracks(
        tracks, colormap, axis, cached_node_attrs=attrs
    )
    assert "extra_attr" in df.columns
    assert "extra_attr" in new_attrs.columns

    # And the other direction: dropping the feature again also invalidates.
    del tracks.features["extra_attr"]
    df_after, _, _ = extract_sorted_tracks(
        tracks, colormap, axis, cached_node_attrs=new_attrs
    )
    assert "extra_attr" not in df_after.columns


def test_get_sorted_track_ids_handles_tracklet_id_zero():
    """Track ids numbered from 0 must order normally, not hang.

    0 used to double as the "no parent" sentinel, so a tracklet numbered 0 was
    its own parent and the traversal never terminated. That input is reachable
    in normal use: CSV and geff files commonly number tracks from 0, and
    funtracks adopts ids already on the graph rather than renumbering them.
    """
    # 0 -> 1, plus an unrelated root 2. Node ids differ from track ids so a
    # mix-up cannot pass.
    order = get_sorted_track_ids(
        node_ids=[10, 11, 12],
        node_to_track_id={10: 0, 11: 1, 12: 2},
        child_to_parent={11: 10},
        parent_to_children={10: [11]},
    )
    assert sorted(order) == [0, 1, 2]
    # The daughter sits beside its parent, and the unrelated root stays separate.
    assert order.index(1) == order.index(0) - 1


def test_get_sorted_track_ids_zero_based_division():
    """A division among 0-based ids puts the parent between its daughters."""
    assert get_sorted_track_ids(
        node_ids=[10, 11, 12],
        node_to_track_id={10: 0, 11: 1, 12: 2},
        child_to_parent={11: 10, 12: 10},
        parent_to_children={10: [11, 12]},
    ) == [1, 0, 2]


def _reference_sorted_track_ids(
    tracklet_to_parent_tracklet: dict[int, int],
    roots: list[int],
) -> list[int]:
    """The pre-optimisation ordering algorithm, kept as a test oracle.

    Quadratic in the number of tracklets - it rescans the parent mapping for
    every tracklet and calls list.index() inside insert() - which is why
    get_sorted_track_ids no longer works this way. Preserved verbatim so the
    replacement is checked against it rather than against hand-written
    expectations, which would only cover the cases someone thought of.
    """
    x_axis_order = list(roots)
    while len(roots) > 0:
        children_list = []
        for tracklet_id in roots:
            children = [
                tid
                for tid, ptid in tracklet_to_parent_tracklet.items()
                if ptid == tracklet_id
            ]
            for i, child in enumerate(children):
                children_list.append(child)
                x_axis_order.insert(x_axis_order.index(tracklet_id) + i, child)
        roots = children_list
    return x_axis_order


def _build_forest(rng, n_tracklets: int, max_children: int = 2):
    """A random forest of tracklets, as nodes carrying one tracklet each.

    Node ids and tracklet ids are deliberately different numbers so a mix-up
    between the two cannot pass. Tracklet ids start at 1 because the *oracle*
    below cannot handle 0 - it uses 0 as its "no parent" sentinel and would
    never terminate. get_sorted_track_ids itself handles 0 fine, which
    test_get_sorted_track_ids_handles_tracklet_id_zero covers separately.
    """
    parent_of = {}
    for tracklet in range(1, n_tracklets + 1):
        # Only earlier tracklets may be parents, so the result is acyclic.
        candidates = [
            other
            for other in range(1, tracklet)
            if sum(1 for p in parent_of.values() if p == other) < max_children
        ]
        parent_of[tracklet] = int(rng.choice(candidates)) if candidates else 0

    node_of_tracklet = {tracklet: 1000 + tracklet for tracklet in parent_of}
    node_to_track_id = {node: t for t, node in node_of_tracklet.items()}
    child_to_parent = {
        node_of_tracklet[t]: node_of_tracklet[p] for t, p in parent_of.items() if p != 0
    }
    parent_to_children: dict[int, list[int]] = {}
    for child, parent in child_to_parent.items():
        parent_to_children.setdefault(parent, []).append(child)

    return {
        "node_ids": list(node_to_track_id),
        "node_to_track_id": node_to_track_id,
        "child_to_parent": child_to_parent,
        "parent_to_children": parent_to_children,
    }, parent_of


def test_get_sorted_track_ids_matches_the_previous_algorithm():
    """The ordering must be identical to the quadratic version it replaced.

    That order is the tree's vertical layout, so a different-but-plausible one
    would be a silent visual regression. Checked over random forests rather
    than a fixed example.
    """
    rng = np.random.default_rng(0)
    for trial in range(40):
        kwargs, parent_of = _build_forest(rng, n_tracklets=int(rng.integers(1, 25)))
        got = get_sorted_track_ids(**kwargs)

        roots = sorted([t for t, p in parent_of.items() if p == 0])
        expected = _reference_sorted_track_ids(dict(parent_of), list(roots))

        assert got == expected, f"trial {trial}: {got} != {expected}"


def test_get_sorted_track_ids_places_parent_between_daughters():
    """A division puts the parent between its two daughters."""
    assert get_sorted_track_ids(
        node_ids=[1, 2, 3],
        node_to_track_id={1: 10, 2: 20, 3: 30},
        child_to_parent={2: 1, 3: 1},
        parent_to_children={1: [2, 3]},
    ) == [20, 10, 30]


def test_get_sorted_track_ids_keeps_every_tracklet_once():
    rng = np.random.default_rng(7)
    kwargs, _ = _build_forest(rng, n_tracklets=60)
    order = get_sorted_track_ids(**kwargs)
    assert sorted(order) == sorted(set(kwargs["node_to_track_id"].values()))


def test_order_roots_by_prev_keeps_all_roots():
    """Roots absent from the previous order are inserted, never dropped."""
    assert order_roots_by_prev([5, 3, 1], [1, 3, 4, 5]) == [5, 3, 4, 1]
