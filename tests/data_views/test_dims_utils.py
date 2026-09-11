"""Tests for relating tracks axes to viewer axes.

The first class pins the napari behaviour the whole design rests on. If napari
ever changes how it aligns layers to the viewer, or starts reindexing
``dims.point`` on a roll, these fail first and say so directly, rather than
leaving the plugin to misbehave somewhere far away.
"""

import pytest
from napari.components.dims import Dims
from napari.layers.base.base import _LayerSlicingState

from motile_tracker.data_views.dims_utils import TracksDims, world_to_layer_axis


class TestNapariDimsInvariants:
    """The napari guarantees TracksDims is built on."""

    def test_roll_and_transpose_leave_point_alone(self):
        """dims.point stays indexed by world axis; only `order` is permuted.

        This is why the tracks-to-world map does not have to be remembered across
        a roll: a roll does not move any axis to a different world index.
        """

        dims = Dims(ndim=4, ndisplay=2)
        dims.range = ((0, 2, 1), (0, 10, 1), (0, 100, 1), (0, 100, 1))
        dims.point = (1.0, 3.0, 50.0, 60.0)

        dims.roll()
        assert tuple(dims.point) == (1.0, 3.0, 50.0, 60.0)
        assert dims.order != (0, 1, 2, 3)

        dims.transpose()
        assert tuple(dims.point) == (1.0, 3.0, 50.0, 60.0)

    def test_rolling_can_put_a_non_tracks_axis_on_screen(self):
        """Two rolls of a 4-dim viewer display world axes 0 and 1.

        With 2D+time tracks behind a channel axis, axis 0 is the channel, so code
        reading `dims.displayed` cannot assume it got a tracks axis.
        """

        dims = Dims(ndim=4, ndisplay=2)
        dims.range = ((0, 2, 1), (0, 10, 1), (0, 100, 1), (0, 100, 1))

        displayed = []
        for _ in range(4):
            displayed.append(dims.displayed)
            dims.roll()

        assert (0, 1) in displayed

    def test_growing_ndim_prepends_and_keeps_the_tracks_on_the_tail(self):
        """Adding a bigger layer pads dims.point at the front, not the back."""

        dims = Dims(ndim=3, ndisplay=2)
        dims.range = ((0, 10, 1), (0, 100, 1), (0, 100, 1))
        dims.point = (3.0, 50.0, 60.0)

        dims.ndim = 4

        assert tuple(dims.point) == (0.0, 3.0, 50.0, 60.0)


class TestWorldToLayerAxis:
    def test_agrees_with_napari(self):
        """Cross-check the trailing alignment against napari's own version."""

        for ndim_world in range(2, 6):
            for ndim_layer in range(2, ndim_world + 1):
                for world_axis in range(ndim_world):
                    napari_result = list(
                        _LayerSlicingState._world_to_layer_dims_impl(
                            [world_axis], ndim_world, ndim_layer
                        )
                    )
                    ours = world_to_layer_axis(world_axis, ndim_world, ndim_layer)
                    assert ours == (napari_result[0] if napari_result else None)

    @pytest.mark.parametrize(
        ("world_axis", "expected"),
        [(0, None), (1, 0), (3, 2), (4, None)],
    )
    def test_is_none_outside_the_layers_own_axes(self, world_axis, expected):
        """The guard that matters: without it a leading axis gives -1, which numpy
        silently wraps to the wrong end instead of raising."""

        assert world_to_layer_axis(world_axis, 4, 3) == expected


class TestTracksDims:
    @pytest.mark.parametrize(
        ("ndim_world", "offset", "extra", "world_axes", "time", "spatial"),
        [
            (3, 0, (), (0, 1, 2), 0, (1, 2)),
            (4, 1, (0,), (1, 2, 3), 1, (2, 3)),
            (5, 2, (0, 1), (2, 3, 4), 2, (3, 4)),
        ],
    )
    def test_axis_bookkeeping(
        self, ndim_world, offset, extra, world_axes, time, spatial
    ):
        dims = TracksDims(ndim_world=ndim_world, ndim_tracks=3)

        assert dims.offset == offset
        assert dims.extra_axes == extra
        assert dims.world_axes == world_axes
        assert dims.time_axis == time
        assert dims.spatial_axes == spatial
        assert not any(dims.is_tracks_axis(axis) for axis in extra)
        assert all(dims.is_tracks_axis(axis) for axis in world_axes)
        assert not dims.is_tracks_axis(ndim_world)

    def test_axes_round_trip(self):
        dims = TracksDims(ndim_world=5, ndim_tracks=4)

        for tracks_axis in range(4):
            assert dims.to_tracks(dims.to_world(tracks_axis)) == tracks_axis
        assert dims.to_tracks(0) is None
        with pytest.raises(IndexError):
            dims.to_world(4)

    @pytest.mark.parametrize(
        ("ndim_world", "ndim_tracks", "match"),
        [(3, 4, "fewer dimensions"), (4, 1, "at least a time")],
    )
    def test_rejects_impossible_combinations(self, ndim_world, ndim_tracks, match):
        with pytest.raises(ValueError, match=match):
            TracksDims(ndim_world=ndim_world, ndim_tracks=ndim_tracks)

    def test_embed_point_fills_the_tail_and_keeps_the_extra_axes(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        # the channel the user is on is preserved, the tracks axes are replaced
        assert dims.embed_point([5.0, 60.0, 70.0], [1.0, 0.0, 0.0, 0.0]) == [
            1.0,
            5.0,
            60.0,
            70.0,
        ]
        # and it is a plain copy when there are no extra axes
        no_extra = TracksDims(ndim_world=3, ndim_tracks=3)
        assert no_extra.embed_point([5.0, 60.0, 70.0], [0.0] * 3) == [
            5.0,
            60.0,
            70.0,
        ]

    def test_embed_point_rejects_wrong_lengths(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        with pytest.raises(ValueError, match="expected 3"):
            dims.embed_point([5.0, 60.0], [0.0] * 4)
        with pytest.raises(ValueError, match="expected 4"):
            dims.embed_point([5.0, 60.0, 70.0], [0.0] * 3)

    def test_take_reads_the_tracks_part_of_a_world_indexed_sequence(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        assert dims.take([1, 5, 60, 70]) == (5, 60, 70)
        with pytest.raises(ValueError, match="Expected 4 values"):
            dims.take([1, 2, 3])
