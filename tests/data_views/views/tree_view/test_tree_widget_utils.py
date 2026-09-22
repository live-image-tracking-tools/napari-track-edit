import pandas as pd
import polars as pl
from funtracks.annotators import TrackAnnotator
from funtracks.data_model import SolutionTracks
from funtracks.features import Feature
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph

from motile_tracker.data_views.colormap import TrackColormap
from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_sorted_tracks,
    get_features_from_tracks,
    get_tracklets,
)


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

    colormap = TrackColormap()
    colormap.set_tracks(tracks)

    track_df, _ = extract_sorted_tracks(tracks, colormap)
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

    colormap = TrackColormap()
    colormap.set_tracks(tracks)
    track_df, _ = extract_sorted_tracks(tracks, colormap)

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
