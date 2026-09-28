"""Tests for relating tracks axes to viewer axes.

The first class pins the napari behaviour the whole design rests on. If napari
ever changes how it aligns layers to the viewer, or starts reindexing
``dims.point`` on a roll, these fail first and say so directly, rather than
leaving the plugin to misbehave somewhere far away.
"""

import numpy as np
import pytest
from napari.components import Dims
from napari.layers import Image

from napari_track_edit.data_views.dims_utils import TracksDims


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


class TestToTracksAxis:
    def test_agrees_with_napari(self):
        """Cross-check the trailing alignment against napari itself.

        ``Layer.world_to_data`` keeps the last ``layer.ndim`` entries of a world
        position and drops the leading ones, which is the rule ``to_tracks_axis``
        encodes. Going through that rather than napari's internal dims mapping
        keeps this test on public API, so it holds across the napari versions the
        plugin supports (the internals moved in 0.7).
        """

        for ndim_world in range(2, 6):
            for ndim_tracks in range(2, ndim_world + 1):
                layer = Image(np.zeros((3,) * ndim_tracks))
                # each slot of the world position names its own world axis, so the
                # data position reads back as "which world axis landed here"
                data = [
                    round(float(value))
                    for value in layer.world_to_data(list(range(ndim_world)))
                ]
                dims = TracksDims(ndim_world=ndim_world, ndim_tracks=ndim_tracks)

                for world_axis in range(ndim_world):
                    expected = data.index(world_axis) if world_axis in data else None
                    assert dims.to_tracks_axis(world_axis) == expected

    @pytest.mark.parametrize(
        ("world_axis", "expected"),
        [(0, None), (1, 0), (3, 2), (4, None)],
    )
    def test_is_none_outside_the_tracks_own_axes(self, world_axis, expected):
        """The guard that matters: without it a leading axis gives -1, which numpy
        silently wraps to the wrong end instead of raising."""

        dims = TracksDims(ndim_world=4, ndim_tracks=3)

        assert dims.to_tracks_axis(world_axis) == expected


class TestTracksDims:
    @pytest.mark.parametrize(
        ("ndim_world", "ndim_offset"),
        [(3, 0), (4, 1), (5, 2)],
    )
    def test_the_tracks_take_the_trailing_axes(self, ndim_world, ndim_offset):
        """The extra axes sit in front, so the tracks start at ``ndim_offset``."""

        dims = TracksDims(ndim_world=ndim_world, ndim_tracks=3)

        assert dims.ndim_offset == ndim_offset
        # time is the tracks' first axis, so it lands on the first non-extra axis
        assert dims.time_axis == ndim_offset

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
