import numpy as np
import pytest

from motile_tracker.data_views.colormap import CategoricalColorSource, TrackColormap


class ConstantColorSource:
    """A trivial ColorSource for testing: every value maps to the same color."""

    def __init__(self, color=(1.0, 0.0, 0.0, 1.0)):
        self.color = np.asarray(color, dtype=float)

    def map(self, values: np.ndarray) -> np.ndarray:
        return np.tile(self.color, (len(np.atleast_1d(values)), 1))


def _tracks_subset(tracks, nodes):
    """A `Tracks`-like object exposing only a subset of `tracks`'s nodes, for
    exercising set_tracks() with a shrunk node set."""

    class NodeSubsetGraph:
        def node_ids(self):
            return list(nodes)

    class TracksSubset:
        graph = NodeSubsetGraph()
        features = tracks.features

        def get_nodes_attr(self, nodes, attr):
            return tracks.get_nodes_attr(nodes, attr)

    return TracksSubset()


class TestCategoricalColorSource:
    def test_maps_same_id_to_same_color(self):
        source = CategoricalColorSource()
        colors = source.map(np.asarray([1, 2, 1]))
        assert np.array_equal(colors[0], colors[2])
        assert not np.array_equal(colors[0], colors[1])

    def test_background_id_zero_is_transparent(self):
        source = CategoricalColorSource()
        color = source.map(np.asarray([0]))[0]
        assert color[3] == 0

    def test_shuffle_changes_colors(self):
        source = CategoricalColorSource(num_colors=49, seed=0.5)
        before = source.map(np.asarray([1, 2, 3])).copy()
        source.shuffle(num_colors=60, seed=0.9)
        after = source.map(np.asarray([1, 2, 3]))
        assert not np.array_equal(before, after)

    def test_not_specific_to_track_ids(self):
        # nothing about this source cares what the ids "mean" - it works
        # identically for e.g. cell-type or lineage-id categories
        source = CategoricalColorSource()
        cell_type_ids = np.asarray([3, 7, 3, 12])
        colors = source.map(cell_type_ids)
        assert np.array_equal(colors[0], colors[2])
        assert not np.array_equal(colors[0], colors[1])


class TestTrackColormapSetAlpha:
    def test_set_alpha_never_touches_node_colors(self, solution_tracks_2d, monkeypatch):
        # set_alpha is the hot path (fires on every selection/hover change);
        # it must never call color_source.map() or otherwise recompute colors.
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        calls = []
        monkeypatch.setattr(cmap.color_source, "map", lambda values: calls.append(values))

        cmap.set_alpha([1], 0.3)

        assert calls == []

    def test_set_alpha_ignores_nodes_removed_by_a_later_set_tracks(
        self, solution_tracks_2d
    ):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_tracks(_tracks_subset(solution_tracks_2d, [2, 3]))  # node 1 removed
        cmap.set_alpha([1], 0.3)  # must not silently "work" for a removed node

        assert cmap.get_alpha(1, default=None) is None


class TestTrackColormapSetTracks:
    def test_set_tracks_none_clears_mapping(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_tracks(None)

        assert list(cmap.nodes) == []

    def test_populates_a_color_per_node(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        nodes = solution_tracks_2d.graph.node_ids()
        assert set(cmap.nodes) == set(nodes)
        for node in nodes:
            assert cmap.get_color(node) is not None

    def test_nodes_sharing_a_track_id_share_a_color(self, solution_tracks_2d):
        # nodes 3, 4, 5 in solution_tracks_2d all belong to track_id 3
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        color_3 = cmap.get_color(3)
        color_4 = cmap.get_color(4)
        color_5 = cmap.get_color(5)
        assert np.array_equal(color_3, color_4)
        assert np.array_equal(color_4, color_5)

    def test_different_track_ids_get_different_colors(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        color_1 = cmap.get_color(1)  # track_id 1
        color_3 = cmap.get_color(3)  # track_id 3
        assert not np.array_equal(color_1, color_3)

    def test_new_nodes_default_to_fully_opaque(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        for node in solution_tracks_2d.graph.node_ids():
            assert cmap.get_alpha(node) == 1.0

    def test_preserves_alpha_for_nodes_still_present(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1, 2], 0.3)

        # re-set the same tracks (simulating a refresh where the node set
        # didn't actually change)
        cmap.set_tracks(solution_tracks_2d)

        assert cmap.get_alpha(1) == 0.3
        assert cmap.get_alpha(2) == 0.3
        assert cmap.get_alpha(3) == 1.0

    def test_drops_alpha_overrides_for_removed_nodes(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1], 0.3)

        cmap.set_tracks(_tracks_subset(solution_tracks_2d, [2, 3]))

        assert set(cmap.nodes) == {2, 3}
        assert cmap.get_alpha(1, default=None) is None


class TestTrackColormapGetColors:
    def test_matches_get_color_per_node(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        nodes = [1, 2, 3]
        colors = cmap.get_colors(np.asarray(nodes))

        for i, node in enumerate(nodes):
            assert np.array_equal(colors[i], cmap.get_color(node))

    def test_unknown_node_is_transparent(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        colors = cmap.get_colors(np.asarray([999]))

        assert np.array_equal(colors[0], [0, 0, 0, 0])

    def test_get_color_unknown_node_matches_get_colors(self, solution_tracks_2d):
        # get_color and get_colors must agree on unknown nodes: both transparent
        # black, not one returning None and the other a placeholder color.
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        assert np.array_equal(cmap.get_color(999), [0, 0, 0, 0])

    def test_reflects_alpha_overrides(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1], 0.4)

        colors = cmap.get_colors(np.asarray([1]))

        assert colors[0][3] == 0.4


class TestTrackColormapColorAlphaSeparation:
    def test_set_alpha_does_not_change_color(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        rgb_before = cmap.get_color(1)[:3].copy()

        cmap.set_alpha([1], 0.2)

        assert np.array_equal(cmap.get_color(1)[:3], rgb_before)
        assert cmap.get_color(1)[3] == 0.2

    def test_set_alpha_ignores_unknown_nodes(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        # should not raise, and should not add the unknown node
        cmap.set_alpha([999], 0.5)
        assert 999 not in cmap.nodes

    def test_add_node_colors_via_color_source_from_track_id(self, solution_tracks_2d):
        # add_node never takes a color directly - a node's color is always
        # color_source.map(track_id), so that "what color is this node" stays
        # a pure function of its track id, not of which method last touched it.
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.add_node(999, 1)

        assert np.array_equal(
            cmap.get_color(999)[:3], cmap.color_source.map(np.asarray([1]))[0][:3]
        )

    def test_add_node_on_new_node_defaults_to_opaque(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.add_node(999, 1)

        assert cmap.get_alpha(999) == 1.0

    def test_recolor_via_color_source_preserves_existing_alpha(self, solution_tracks_2d):
        # Recoloring is a color_source concern (e.g. shuffle), not a per-node
        # setter - existing alpha must survive a resync after a recolor.
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1], 0.4)

        cmap.color_source.shuffle(num_colors=60, seed=0.9)
        cmap.set_tracks(solution_tracks_2d)

        assert cmap.get_alpha(1) == 0.4

    def test_remove_node_drops_both_color_and_alpha(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.remove_node(1)

        assert 1 not in cmap.nodes
        assert np.array_equal(cmap.get_color(1), [0, 0, 0, 0])
        assert cmap.get_alpha(1, default=None) is None


class TestTrackColormapDefaultAlpha:
    def test_set_tracks_uses_configured_default_alpha(self, solution_tracks_2d):
        cmap = TrackColormap(default_alpha=0.5)
        cmap.set_tracks(solution_tracks_2d)

        for node in solution_tracks_2d.graph.node_ids():
            assert cmap.get_alpha(node) == 0.5

    def test_add_node_uses_configured_default_alpha(self, solution_tracks_2d):
        cmap = TrackColormap(default_alpha=0.5)
        cmap.set_tracks(solution_tracks_2d)

        cmap.add_node(999, 1)

        assert cmap.get_alpha(999) == 0.5


class TestTrackColormapMap:
    def test_map_delegates_to_color_source(self):
        source = ConstantColorSource(color=(0.5, 0.5, 0.5, 1.0))
        cmap = TrackColormap(color_source=source)

        result = cmap.map(np.asarray([1, 2, 3]))

        assert result.shape == (3, 4)
        assert np.all(result == [0.5, 0.5, 0.5, 1.0])

    def test_default_color_source_is_track_id_based(self, solution_tracks_2d):
        cmap = TrackColormap()
        colors = cmap.map(np.asarray([1, 3]))
        assert not np.array_equal(colors[0], colors[1])


class TestTrackColormapFeatureKey:
    def test_defaults_to_track_id(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        # nodes 3, 4, 5 share track_id 3 -> should share a color by default
        assert np.array_equal(cmap.get_color(3), cmap.get_color(4))

    def test_can_color_by_a_different_feature(self, solution_tracks_2d):
        # nodes 4 and 5 both have area 16.0, despite different track ids (3, 5)
        cmap = TrackColormap(feature_key="area")
        cmap.set_tracks(solution_tracks_2d)

        assert np.array_equal(cmap.get_color(4), cmap.get_color(5))
        # and now nodes 3 and 4 (same track id, different area) should differ
        assert not np.array_equal(cmap.get_color(3), cmap.get_color(4))

    def test_reassigning_feature_key_resyncs_colors(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        assert np.array_equal(cmap.get_color(3), cmap.get_color(4))  # by track id

        cmap.feature_key = "area"

        assert np.array_equal(cmap.get_color(4), cmap.get_color(5))  # now by area
        assert not np.array_equal(cmap.get_color(3), cmap.get_color(4))

    def test_reassigning_color_source_resyncs_colors(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.color_source = ConstantColorSource(color=(0.2, 0.4, 0.6, 1.0))

        assert np.allclose(cmap.get_color(1)[:3], [0.2, 0.4, 0.6])


class TestTrackColormapDirectColormap:
    def test_set_tracks_before_any_build_still_populates_it(self, solution_tracks_2d):
        # to_direct_colormap() may be called before any tracks are set (e.g.
        # right after construction, producing an empty colormap); a later
        # set_tracks() must be reflected the next time it's called.
        cmap = TrackColormap()
        cmap.to_direct_colormap()

        cmap.set_tracks(solution_tracks_2d)
        direct = cmap.to_direct_colormap()

        for node in solution_tracks_2d.graph.node_ids():
            assert node in direct.color_dict

    def test_produces_direct_colormap_with_all_nodes(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        direct = cmap.to_direct_colormap()

        for node in solution_tracks_2d.graph.node_ids():
            assert node in direct.color_dict

    def test_none_key_maps_to_transparent(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        direct = cmap.to_direct_colormap()

        assert np.array_equal(direct.color_dict[None], [0, 0, 0, 0])

    def test_alpha_change_is_reflected(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_alpha([1], 0.2)
        direct = cmap.to_direct_colormap()

        assert direct.color_dict[1][3] == 0.2

    def test_recolor_is_reflected(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        before_color = cmap.to_direct_colormap().color_dict[1][:3].copy()

        cmap.color_source.shuffle(num_colors=60, seed=0.9)
        cmap.set_tracks(solution_tracks_2d)
        direct_after = cmap.to_direct_colormap()

        assert not np.allclose(direct_after.color_dict[1][:3], before_color)

    def test_new_node_is_reflected(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.add_node(999, 1)
        direct = cmap.to_direct_colormap()

        assert 999 in direct.color_dict

    def test_removed_node_is_reflected(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.remove_node(1)
        direct = cmap.to_direct_colormap()

        assert 1 not in direct.color_dict

    def test_set_tracks_drops_stale_entries(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_tracks(_tracks_subset(solution_tracks_2d, [2, 3]))
        direct = cmap.to_direct_colormap()

        assert 1 not in direct.color_dict
        assert 2 in direct.color_dict
        assert 3 in direct.color_dict

    def test_never_pays_pydantic_validation(self, solution_tracks_2d, monkeypatch):
        # to_direct_colormap() must always use DirectLabelColormap.model_construct
        # (which skips pydantic's per-color validation), never the normal
        # constructor - not even on the first call.
        import motile_tracker.data_views.colormap as colormap_module

        calls = []
        original_init = colormap_module.DirectLabelColormap.__init__
        monkeypatch.setattr(
            colormap_module.DirectLabelColormap,
            "__init__",
            lambda self, *a, **k: (calls.append(1), original_init(self, *a, **k))[1],
        )

        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.to_direct_colormap()
        cmap.set_alpha([1], 0.2)
        cmap.add_node(999, 1)
        cmap.remove_node(2)
        cmap.color_source.shuffle(num_colors=60, seed=0.9)
        cmap.set_tracks(solution_tracks_2d)
        cmap.to_direct_colormap()

        assert calls == []

    def test_reflects_alpha_set_before_first_build(self, solution_tracks_2d):
        # alpha set before to_direct_colormap() has ever been called should
        # still show up in the first built colormap
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1], 0.0)

        direct = cmap.to_direct_colormap()

        assert direct.color_dict[1][3] == 0.0

    def test_empty_colormap_has_default_key(self):
        cmap = TrackColormap()
        direct = cmap.to_direct_colormap()
        assert set(direct.color_dict.keys()) == {None}
        assert np.array_equal(direct.color_dict[None], [0, 0, 0, 0])


@pytest.fixture
def solution_tracks_2d_empty():
    """A Tracks-like object with no nodes, to exercise the empty-graph path."""
    from funtracks.data_model import SolutionTracks
    from funtracks.utils.tracksdata_utils import create_empty_graphview_graph

    empty_graph = create_empty_graphview_graph(
        node_attributes=["pos", "area", "track_id", "lineage_id"],
        edge_attributes=["iou"],
        ndim=3,
    )
    return SolutionTracks(graph=empty_graph, ndim=3, time_attr="t")


class TestTrackColormapEmptyTracks:
    def test_set_tracks_with_no_nodes(self, solution_tracks_2d_empty):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d_empty)

        assert list(cmap.nodes) == []
        direct = cmap.to_direct_colormap()
        assert set(direct.color_dict.keys()) == {None}
