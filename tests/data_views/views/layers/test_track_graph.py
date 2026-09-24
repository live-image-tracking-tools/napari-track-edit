"""Tests for update_napari_tracks with the graph returned by solve()."""

from funtracks.data_model import Tracks

from motile_tracker.data_views.views.layers.track_graph import update_napari_tracks
from motile_tracker.motile.backend import SolverParams, solve


def test_update_napari_tracks_division_edges(solution_tracks_3d_with_division):
    """napari edges dict must map each daughter track_id to its parent track_id.

    graph_3d_with_division has: node1(t=0) -> node2(t=1) -> node3(t=2)
                                                          -> node4(t=2)
    So node2 divides into node3 and node4. The napari edges dict should contain
    one entry per daughter, pointing back to the parent track.
    """
    tracks = solution_tracks_3d_with_division
    data, edges, _node_ids = update_napari_tracks(tracks)

    assert data.shape[1] == 5  # track_id, t, z, y, x
    assert len(edges) == 2, "expect one entry per daughter of the division"
    # each daughter track must list the parent track as its parent
    parent_track_ids = set()
    for _, parent_list in edges.items():
        assert len(parent_list) == 1
        parent_track_ids.add(parent_list[0])
    assert len(parent_track_ids) == 1, "both daughters share the same parent track"


def test_update_napari_tracks_with_solve_output(segmentation_2d):
    """update_napari_tracks must work with the graph returned by solve().

    solve() returns a GraphView whose _root is a SQLGraph. Previously,
    update_napari_tracks called graph.detach() which triggered
    SQLGraph.metadata() and crashed with OperationalError if the Metadata
    table was missing (databases from older tracksdata versions).
    """
    params = SolverParams()
    params.appear_cost = None
    soln_graph = solve(params, segmentation_2d)

    tracks = Tracks(graph=soln_graph, ndim=3, time_attr="t")
    data, edges, _node_ids = update_napari_tracks(tracks)

    assert data.shape[0] == soln_graph.num_nodes()
    assert data.shape[1] == 4  # track_id, t, y, x
    assert isinstance(edges, dict)
