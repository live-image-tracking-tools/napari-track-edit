"""Tests for update_napari_tracks and for TrackGraph's visibility updates."""

import numpy as np
import pytest
from funtracks.data_model import Tracks

from motile_tracker.data_views.views.layers.track_graph import update_napari_tracks
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.motile.backend import SolverParams, solve


def test_update_napari_tracks_division_edges(solution_tracks_3d_with_division):
    """napari edges dict must map each daughter track_id to its parent track_id.

    graph_3d_with_division has: node1(t=0) -> node2(t=1) -> node3(t=2)
                                                          -> node4(t=2)
    So node2 divides into node3 and node4. The napari edges dict should contain
    one entry per daughter, pointing back to the parent track.
    """
    tracks = solution_tracks_3d_with_division
    data, edges = update_napari_tracks(tracks)

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
    data, edges = update_napari_tracks(tracks)

    assert data.shape[0] == soln_graph.num_nodes()
    assert data.shape[1] == 4  # track_id, t, y, x
    assert isinstance(edges, dict)


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.fixture
def tracks_layer(viewer, solution_tracks_2d):
    """A TrackGraph layer showing all tracks of the 2D fixture."""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")
    return tracks_viewer.tracking_layers.tracks_layer


def count_graph_rebuilds(layer, monkeypatch):
    """Count how often napari rebuilds the layer's graph vertices.

    This is the expensive half of the `Tracks.graph` setter: it looks every
    track id up against every point, so it must not run when the set of visible
    tracks did not change.
    """
    calls = []
    original = layer._manager.build_graph
    monkeypatch.setattr(
        layer._manager,
        "build_graph",
        lambda *args, **kwargs: (calls.append(1), original(*args, **kwargs))[1],
    )
    return calls


def test_showing_all_twice_does_not_rebuild_the_graph(tracks_layer, monkeypatch):
    """A selection in 'all' mode changes colours, not which tracks are shown."""
    tracks_layer.update_track_visibility("all")
    rebuilds = count_graph_rebuilds(tracks_layer, monkeypatch)

    tracks_layer.update_track_visibility("all")

    assert len(rebuilds) == 0
    assert tracks_layer.graph == tracks_layer.tracks_layer_graph


def test_repeating_a_lineage_does_not_rebuild_the_graph(tracks_layer, monkeypatch):
    """The same lineage, given in a different order, is the same visible set."""
    visible = list(tracks_layer.tracks_layer_graph.keys())
    tracks_layer.update_track_visibility(visible)
    rebuilds = count_graph_rebuilds(tracks_layer, monkeypatch)

    tracks_layer.update_track_visibility(list(reversed(visible)))

    assert len(rebuilds) == 0
    assert set(tracks_layer.graph) == set(visible)


def test_changing_the_visible_set_does_rebuild_the_graph(tracks_layer, monkeypatch):
    """The guard must not swallow a real change."""
    tracks_layer.update_track_visibility("all")
    full_graph = dict(tracks_layer.tracks_layer_graph)
    assert len(full_graph) > 0, "fixture has no division, so nothing to hide"
    rebuilds = count_graph_rebuilds(tracks_layer, monkeypatch)

    one_track = [next(iter(full_graph))]
    tracks_layer.update_track_visibility(one_track)
    assert len(rebuilds) == 1
    assert set(tracks_layer.graph) == set(one_track)

    tracks_layer.update_track_visibility("all")
    assert len(rebuilds) == 2
    assert tracks_layer.graph == full_graph


def test_visibility_emits_a_colour_event(tracks_layer):
    """The alphas have to reach the vispy layer.

    They are written in place, which bypasses the `track_colors` setter, so
    without an explicit assignment the new opacities would never be uploaded -
    and the graph assignment that used to do it by accident is now skipped.
    """
    events = []
    tracks_layer.events.color_by.connect(lambda event: events.append(event))

    tracks_layer.update_track_visibility("all")

    assert len(events) == 1
    assert np.all(tracks_layer.track_colors[:, 3] == 1)


def test_hiding_tracks_sets_only_their_alpha(tracks_layer):
    """Alphas still follow the visible set, guard or no guard."""
    track_ids = tracks_layer.properties["track_id"]
    visible = [int(track_ids[0])]

    tracks_layer.update_track_visibility(visible)

    shown = np.isin(track_ids, visible)
    assert np.all(tracks_layer.track_colors[shown, 3] == 1)
    assert np.all(tracks_layer.track_colors[~shown, 3] == 0)


def test_graph_display_is_restored_after_an_empty_lineage(tracks_layer):
    """A lineage without divisions disables the graph; 'all' must re-enable it."""
    track_ids = [int(tid) for tid in np.unique(tracks_layer.properties["track_id"])]
    childless = [tid for tid in track_ids if tid not in tracks_layer.tracks_layer_graph]
    assert childless, "fixture has no track without a parent edge"

    tracks_layer.update_track_visibility(childless[:1])
    assert tracks_layer.display_graph is False

    tracks_layer.update_track_visibility("all")
    assert tracks_layer.display_graph is True


def test_refresh_resets_the_remembered_graph(tracks_layer, monkeypatch):
    """After a refresh the layer holds a fresh graph, so the key must be reset."""
    tracks_layer.update_track_visibility([next(iter(tracks_layer.tracks_layer_graph))])
    tracks_layer._refresh()
    rebuilds = count_graph_rebuilds(tracks_layer, monkeypatch)

    tracks_layer.update_track_visibility("all")

    assert len(rebuilds) == 0
    assert tracks_layer.graph == tracks_layer.tracks_layer_graph
