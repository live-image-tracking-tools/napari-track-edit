"""Tests for relating tracks axes to viewer axes.

The first class pins the napari behaviour the whole design rests on. If napari
ever changes how it aligns layers to the viewer, or starts reindexing
``dims.point`` on a roll, these fail first and say so directly, rather than
leaving the plugin to misbehave somewhere far away.
"""

import numpy as np
import pytest
from napari.components.dims import Dims
from napari.layers.base.base import _LayerSlicingState

from motile_tracker.data_views.dims_utils import TracksDims, world_to_layer_axis


class TestNapariDimsInvariants:
    """The napari guarantees TracksDims is built on."""

    def test_layers_align_on_their_trailing_dimensions(self):
        """A 3-dim layer in a 4-dim viewer spans world axes 1, 2, 3 and not 0."""

        assert list(_LayerSlicingState._world_to_layer_dims_impl([0], 4, 3)) == []
        for world_axis, layer_axis in ((1, 0), (2, 1), (3, 2)):
            assert list(
                _LayerSlicingState._world_to_layer_dims_impl([world_axis], 4, 3)
            ) == [layer_axis]

    def test_roll_and_transpose_leave_point_alone(self):
        """dims.point stays indexed by world axis; only `order` is permuted.

        This is why the tracks-to-world map does not have to be remembered
        across a roll: a roll does not move any axis to a different world index.
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

        With 2D+time tracks behind a channel axis, axis 0 is the channel, so
        code reading `dims.displayed` cannot assume it got a tracks axis.
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
    def test_maps_trailing_axes(self):
        assert world_to_layer_axis(1, 4, 3) == 0
        assert world_to_layer_axis(3, 4, 3) == 2

    def test_returns_none_for_an_axis_the_layer_does_not_span(self):
        """The guard that matters: without it this is -1, which numpy wraps."""

        assert world_to_layer_axis(0, 4, 3) is None

    def test_returns_none_above_the_layers_range(self):
        assert world_to_layer_axis(4, 4, 3) is None

    def test_is_the_identity_when_the_dimensions_match(self):
        for axis in range(3):
            assert world_to_layer_axis(axis, 3, 3) == axis

    def test_agrees_with_napari(self):
        """Cross-check against napari's own implementation."""

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


class TestTracksDims:
    def test_no_extra_dimensions(self):
        dims = TracksDims(ndim_world=3, ndim_tracks=3)

        assert dims.offset == 0
        assert dims.extra_axes == ()
        assert dims.world_axes == (0, 1, 2)
        assert dims.time_axis == 0
        assert dims.spatial_axes == (1, 2)

    def test_one_extra_dimension(self):
        """2D+time tracks behind a channel axis."""

        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        assert dims.offset == 1
        assert dims.extra_axes == (0,)
        assert dims.world_axes == (1, 2, 3)
        assert dims.time_axis == 1
        assert dims.spatial_axes == (2, 3)

    def test_is_tracks_axis(self):
        dims = TracksDims(ndim_world=5, ndim_tracks=3)

        assert not dims.is_tracks_axis(0)
        assert not dims.is_tracks_axis(1)
        assert dims.is_tracks_axis(2)
        assert dims.is_tracks_axis(4)
        assert not dims.is_tracks_axis(5)

    def test_to_world_and_back(self):
        dims = TracksDims(ndim_world=5, ndim_tracks=4)

        for tracks_axis in range(4):
            world_axis = dims.to_world(tracks_axis)
            assert dims.to_tracks(world_axis) == tracks_axis

    def test_to_tracks_is_none_for_an_extra_axis(self):
        assert TracksDims(ndim_world=4, ndim_tracks=3).to_tracks(0) is None

    def test_to_world_rejects_an_axis_the_tracks_do_not_have(self):
        with pytest.raises(IndexError):
            TracksDims(ndim_world=4, ndim_tracks=3).to_world(3)

    def test_rejects_a_viewer_smaller_than_the_tracks(self):
        with pytest.raises(ValueError, match="fewer dimensions"):
            TracksDims(ndim_world=3, ndim_tracks=4)

    def test_rejects_degenerate_tracks(self):
        with pytest.raises(ValueError, match="at least a time"):
            TracksDims(ndim_world=4, ndim_tracks=1)


class TestEmbedPoint:
    def test_fills_the_tracks_axes_and_keeps_the_extra_ones(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        embedded = dims.embed_point(
            location=[5.0, 60.0, 70.0], point=[1.0, 0.0, 0.0, 0.0]
        )

        # the channel the user is on is preserved, the tracks axes are replaced
        assert embedded == [1.0, 5.0, 60.0, 70.0]

    def test_is_a_plain_copy_when_the_dimensions_match(self):
        dims = TracksDims(ndim_world=3, ndim_tracks=3)

        assert dims.embed_point([5.0, 60.0, 70.0], [0.0, 0.0, 0.0]) == [
            5.0,
            60.0,
            70.0,
        ]

    def test_accepts_a_numpy_location(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        embedded = dims.embed_point(np.array([5.0, 60.0, 70.0]), (2.0, 0.0, 0.0, 0.0))

        assert embedded == [2.0, 5.0, 60.0, 70.0]

    def test_rejects_a_location_of_the_wrong_length(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        with pytest.raises(ValueError, match="expected 3"):
            dims.embed_point([5.0, 60.0], [0.0] * 4)

    def test_rejects_a_point_of_the_wrong_length(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        with pytest.raises(ValueError, match="expected 4"):
            dims.embed_point([5.0, 60.0, 70.0], [0.0] * 3)


class TestTake:
    def test_takes_the_trailing_values(self):
        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        assert dims.take([1, 5, 60, 70]) == (5, 60, 70)

    def test_rejects_the_wrong_length(self):
        with pytest.raises(ValueError, match="Expected 4 values"):
            TracksDims(ndim_world=4, ndim_tracks=3).take([1, 2, 3])
