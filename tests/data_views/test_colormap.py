import numpy as np
import pytest

from napari_track_edit.data_views.colormap import (
    GREY,
    PINK,
    BinaryColorSource,
    CategoricalColorSource,
    ConstantColorSource,
    TrackColormap,
    categorical_feature_keys,
    feature_display_name,
    make_color_source,
)


def _tracks_subset(tracks, nodes):
    """A `Tracks`-like object exposing only a subset of `tracks`'s nodes, for
    exercising set_tracks() with a shrunk node set."""

    class NodeSubsetGraph:
        def node_ids(self):
            return list(nodes)

    class TracksSubset:
        graph_solution = NodeSubsetGraph()
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
        monkeypatch.setattr(
            cmap.color_source, "map", lambda values: calls.append(values)
        )

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

        nodes = solution_tracks_2d.graph_solution.node_ids()
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

        for node in solution_tracks_2d.graph_solution.node_ids():
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

    def test_does_not_reflect_alpha_overrides(self, solution_tracks_2d):
        # alpha is display state, reachable via get_alpha and folded in by
        # to_direct_colormap for the labels layer - it is not part of a node's
        # color, and no get_colors consumer wants it
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1], 0.4)

        colors = cmap.get_colors(np.asarray([1]))

        assert colors[0][3] == 1.0
        assert cmap.get_alpha(1) == 0.4


class TestTrackColormapColorAlphaSeparation:
    def test_set_alpha_does_not_change_color(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        rgb_before = cmap.get_color(1)[:3].copy()

        cmap.set_alpha([1], 0.2)

        assert np.array_equal(cmap.get_color(1)[:3], rgb_before)
        assert cmap.get_alpha(1) == 0.2

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

    def test_recolor_via_color_source_preserves_existing_alpha(
        self, solution_tracks_2d
    ):
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

        for node in solution_tracks_2d.graph_solution.node_ids():
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

        for node in solution_tracks_2d.graph_solution.node_ids():
            assert node in direct.color_dict

    def test_produces_direct_colormap_with_all_nodes(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        direct = cmap.to_direct_colormap()

        for node in solution_tracks_2d.graph_solution.node_ids():
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
        import napari_track_edit.data_views.colormap as colormap_module

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


class TestGetColorsIsOpaque:
    def test_ignores_per_node_alpha(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_alpha([1], 0.3)

        colors = cmap.get_colors([1])

        assert colors[0][3] == 1.0
        assert np.array_equal(colors[0][:3], cmap.get_color(1)[:3])

    def test_unknown_node_is_transparent(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        colors = cmap.get_colors([1, 999])

        assert np.array_equal(colors[1], np.zeros(4))
        assert colors[0][3] == 1.0

    def test_empty_inputs(self, solution_tracks_2d):
        cmap = TrackColormap()

        assert cmap.get_colors([]).shape == (0, 4)
        assert np.array_equal(cmap.get_colors([1])[0], np.zeros(4))

    def test_reflects_nodes_added_and_removed_since_the_last_set_tracks(
        self, solution_tracks_2d
    ):
        # the vectorized lookup caches the node set, so add_node/remove_node
        # have to invalidate it
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.get_colors([1])  # populate the cache

        cmap.add_node(999, 1)
        cmap.remove_node(1)

        assert cmap.get_colors([999])[0][3] == 1.0
        assert np.array_equal(cmap.get_colors([1])[0], np.zeros(4))

    def test_matches_get_color_per_node(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        nodes = list(cmap.nodes)

        base = cmap.get_colors(nodes)

        for row, node in zip(base, nodes, strict=True):
            assert np.array_equal(row[:3], cmap.get_color(node)[:3])

    def test_follows_the_feature_key(self, solution_tracks_2d):
        # nodes 4 and 5 both have area 16.0, despite different track ids
        cmap = TrackColormap(feature_key="area")
        cmap.set_tracks(solution_tracks_2d)

        colors = cmap.get_colors([4, 5])

        assert np.array_equal(colors[0], colors[1])

    def test_accepts_float_node_ids(self, solution_tracks_2d):
        # the napari Tracks layer maps its vertex colors through get_colors and
        # hands back whatever dtype its property table holds
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        colors = cmap.get_colors(np.asarray([1, 2], dtype=float))

        assert np.array_equal(colors, cmap.get_colors([1, 2]))


class TestColorsByTrackId:
    def test_true_for_the_tracklet_key_and_the_default(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        assert cmap.colors_by_track_id

        cmap.feature_key = solution_tracks_2d.features.tracklet_key
        assert cmap.colors_by_track_id

    def test_false_for_any_other_feature(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.feature_key = solution_tracks_2d.features.lineage_key

        assert not cmap.colors_by_track_id


class TestPendingNodes:
    def test_colored_by_track_id_when_that_is_the_feature(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.add_node(999, 1)

        assert np.array_equal(cmap.get_color(999)[:3], cmap.map(np.asarray([1]))[0][:3])

    def test_new_lineage_when_the_track_has_no_nodes_yet(self, solution_tracks_2d):
        # a brand-new track is a new root, so UserAddNode will mint it a new
        # lineage - which is knowable up front
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.feature_key = solution_tracks_2d.features.lineage_key

        cmap.add_node(999, solution_tracks_2d.get_next_track_id())

        expected = cmap.map(np.asarray([solution_tracks_2d.get_next_lineage_id()]))[0]
        assert np.allclose(cmap.get_color(999)[:3], expected[:3])

    def test_lineage_of_the_track_when_it_already_has_nodes(self, solution_tracks_2d):
        # continuing an existing track: UserAddNode takes the lineage from its
        # other nodes
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.feature_key = solution_tracks_2d.features.lineage_key
        track = solution_tracks_2d.get_track_id(1)

        cmap.add_node(999, track)

        assert np.array_equal(cmap.get_color(999)[:3], cmap.get_color(1)[:3])

    def test_grey_when_the_value_cannot_be_known(self, solution_tracks_2d):
        # nothing says what area a node that has not been drawn yet will have
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.feature_key = "area"

        cmap.add_node(999, 1)

        assert np.allclose(cmap.get_color(999)[:3], GREY)

    def test_survives_a_refresh_before_the_node_is_committed(self, solution_tracks_2d):
        # set_tracks runs on every refresh; dropping the pending node there
        # leaves the label being painted with colorless mid-edit
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.add_node(999, 1)
        before = cmap.get_color(999).copy()

        cmap.set_tracks(solution_tracks_2d)

        assert np.array_equal(cmap.get_color(999), before)
        assert 999 in cmap.to_direct_colormap().color_dict

    def test_real_color_takes_over_once_tracks_has_the_node(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.feature_key = "area"  # nothing can be known about it up front
        cmap.add_node(1, 1)  # node 1 *is* in the graph
        assert np.allclose(cmap.get_color(1)[:3], GREY)

        cmap.set_tracks(solution_tracks_2d)

        assert not np.allclose(cmap.get_color(1)[:3], GREY)

    def test_dropped_by_remove_node(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.add_node(999, 1)

        cmap.remove_node(999)
        cmap.set_tracks(solution_tracks_2d)

        assert np.array_equal(cmap.get_color(999), np.zeros(4))

    def test_dropped_when_the_tracks_go_away(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.add_node(999, 1)

        cmap.set_tracks(None)

        assert list(cmap.nodes) == []


def _add_group_feature(tracks, name, members):
    """Register a group the way CollectionWidget._add_group does, with
    `members` in it."""
    tracks.add_feature(
        name,
        {
            "feature_type": "node",
            "value_type": "bool",
            "num_values": 1,
            "display_name": name,
            "default_value": False,
        },
    )
    for node in tracks.graph_solution.node_ids():
        tracks.graph_solution.nodes[node][name] = node in members
    return name


class TestBinaryColorSource:
    def test_two_colors_for_the_two_values(self):
        colors = BinaryColorSource().map(np.asarray([True, False, True]))

        assert np.array_equal(colors[0], colors[2])
        assert np.allclose(colors[0][:3], PINK)
        assert np.allclose(colors[1][:3], GREY)

    def test_missing_values_count_as_not_in_the_group(self):
        # a node that never got a value for the group feature reads as None
        colors = BinaryColorSource().map(np.asarray([None, False], dtype=object))

        assert np.array_equal(colors[0], colors[1])

    def test_scalar_maps_to_a_single_rgba(self):
        # matches napari's colormaps, which TrackColormap.map relies on
        assert BinaryColorSource().map(np.asarray(True)).shape == (4,)

    def test_shuffle_picks_two_new_colors(self):
        source = BinaryColorSource()
        before = (source.false_color.copy(), source.true_color.copy())

        source.shuffle()

        assert not np.array_equal(source.false_color, before[0])
        assert not np.array_equal(source.true_color, before[1])
        assert not np.array_equal(source.false_color, source.true_color)


class TestCategoricalColorSourceCoercion:
    def test_maps_booleans_a_cyclic_colormap_would_reject(self):
        # napari's cyclic colormap raises "Invalid integer data type 'b'" on a
        # bool array - the crash coloring by a group used to produce
        colors = CategoricalColorSource().map(np.asarray([True, False, True]))

        assert colors.shape == (3, 4)
        assert np.array_equal(colors[0], colors[2])

    def test_maps_missing_values(self):
        # lineage id defaults to None, so its values arrive as an object array
        colors = CategoricalColorSource().map(np.asarray([None, 3, None], dtype=object))

        assert np.array_equal(colors[0], colors[2])
        assert colors[0][3] == 0  # None -> 0 -> the transparent background entry

    def test_shuffle_without_arguments_randomizes(self):
        source = CategoricalColorSource()
        before = source.map(np.asarray([1, 2, 3]))

        source.shuffle()

        assert not np.array_equal(source.map(np.asarray([1, 2, 3])), before)


class TestMakeColorSource:
    def test_boolean_feature_gets_two_colors(self, solution_tracks_2d):
        _add_group_feature(solution_tracks_2d, "my_group", {1})

        assert isinstance(
            make_color_source(solution_tracks_2d, "my_group"), BinaryColorSource
        )

    def test_other_features_get_the_cyclic_colors(self, solution_tracks_2d):
        assert isinstance(
            make_color_source(
                solution_tracks_2d, solution_tracks_2d.features.tracklet_key
            ),
            CategoricalColorSource,
        )


class TestSetFeature:
    def test_boolean_feature_does_not_crash(self, solution_tracks_2d):
        _add_group_feature(solution_tracks_2d, "my_group", {1, 2})
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_feature("my_group")

        assert isinstance(cmap.color_source, BinaryColorSource)
        assert np.array_equal(cmap.get_color(1)[:3], cmap.get_color(2)[:3])
        assert np.allclose(cmap.get_color(1)[:3], PINK)
        assert np.allclose(cmap.get_color(3)[:3], GREY)

    def test_an_explicit_source_wins_over_the_feature_type(self, solution_tracks_2d):
        _add_group_feature(solution_tracks_2d, "my_group", {1})
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_feature("my_group", CategoricalColorSource())

        assert isinstance(cmap.color_source, CategoricalColorSource)

    def test_recomputes_colors_only_once(self, solution_tracks_2d, monkeypatch):
        # set_feature exists so that changing key and source together costs one
        # O(node count) recompute, not one per assignment
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        calls = []
        monkeypatch.setattr(
            TrackColormap, "set_tracks", lambda self, t: calls.append(t)
        )

        cmap.set_feature(solution_tracks_2d.features.lineage_key)

        assert len(calls) == 1

    def test_a_new_node_is_in_no_group(self, solution_tracks_2d):
        # a group value *is* knowable up front: nothing has been added to it,
        # so the node is painted exactly as a committed node outside the group
        # (node 2), and not as one inside it (node 1)
        _add_group_feature(solution_tracks_2d, "my_group", {1})
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)
        cmap.set_feature("my_group")

        cmap.add_node(999, 1)

        assert np.array_equal(cmap.get_color(999)[:3], cmap.get_color(2)[:3])
        assert not np.array_equal(cmap.get_color(999)[:3], cmap.get_color(1)[:3])


class TestConstantColorSource:
    """What "color by: None" installs."""

    def test_every_value_gets_the_same_color(self):
        colors = ConstantColorSource().map(np.asarray([1, 7, 3, 0]))

        assert np.all(colors == colors[0])
        assert np.allclose(colors[0][:3], GREY)

    def test_scalar_maps_to_a_single_rgba(self):
        assert ConstantColorSource().map(np.asarray(3)).shape == (4,)

    def test_shuffle_picks_a_new_color(self):
        source = ConstantColorSource()
        before = source.color.copy()

        source.shuffle()

        assert not np.array_equal(source.color, before)

    def test_no_feature_gets_one(self, solution_tracks_2d):
        assert isinstance(
            make_color_source(solution_tracks_2d, None), ConstantColorSource
        )

    def test_gives_every_node_one_color(self, solution_tracks_2d):
        cmap = TrackColormap()
        cmap.set_tracks(solution_tracks_2d)

        cmap.set_feature(None)

        colors = cmap.get_colors(list(cmap.nodes))
        assert np.all(colors[:, :3] == colors[0, :3])
        assert np.allclose(colors[0][:3], GREY)


class TestFeatureMenu:
    """What the "Color by" dropdown offers."""

    def test_lists_track_lineage_and_groups(self, solution_tracks_2d):
        _add_group_feature(solution_tracks_2d, "my_group", {1})

        keys = categorical_feature_keys(solution_tracks_2d)

        assert keys[:2] == [
            solution_tracks_2d.features.tracklet_key,
            solution_tracks_2d.features.lineage_key,
        ]
        assert "my_group" in keys

    def test_excludes_solution_and_continuous_features(self, solution_tracks_2d):
        keys = categorical_feature_keys(solution_tracks_2d)

        assert "solution" not in keys
        assert "t" not in keys
        assert "pos" not in keys

    def test_no_tracks_no_keys(self):
        assert categorical_feature_keys(None) == []

    def test_display_names(self, solution_tracks_2d):
        assert feature_display_name(solution_tracks_2d, None) == "None"
        assert (
            feature_display_name(
                solution_tracks_2d, solution_tracks_2d.features.lineage_key
            )
            == "Lineage ID"
        )
