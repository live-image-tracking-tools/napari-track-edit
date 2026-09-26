from dataclasses import fields

import numpy as np
import pytest
from napari.components import ViewerModel
from napari.layers import Points
from napari.layers.points._slice import _PointSliceRequest

from napari_track_edit.data_views.views.layers.out_of_slice_points import ZOnlyPoints

# napari < 0.9 renders points that "spill" into the current slice based on their
# size, along every non-displayed axis, controlled by ``out_of_slice_display``.
# napari 0.9 removed that (deprecating the flag in favour of ``projection_mode``):
# a point is only ever shown if it falls inside the - possibly thick - slice, so
# per-axis margins now give the control ZOnlyPoints had to add by hand, and
# ZOnlyPoints is plain Points there. Skip what only applies to the subclass.
overrides_slicing = pytest.mark.skipif(
    ZOnlyPoints is Points,
    reason="napari >= 0.9 has no size-based out-of-slice display to restrict",
)


def get_visible_indices(layer):
    """
    visible points are those in the current view_data,
    but we recover indices via comparison to full data.
    """
    visible = layer._view_data

    # match rows back to original data
    idx = []
    for row in visible:
        matches = np.where((layer.data[:, -2:] == row).all(axis=1))[0]
        idx.extend(matches.tolist())

    return sorted(set(idx))


def add_points(viewer, data, out_of_slice_display=False):
    """Add a ZOnlyPoints and a plain Points layer for the same data.

    Returns the (zonly, normal) pair.
    """
    zonly = ZOnlyPoints(data, size=20)
    normal = Points(data, size=20)

    viewer.add_layer(zonly)
    viewer.add_layer(normal)

    if out_of_slice_display:
        zonly.out_of_slice_display = True
        normal.out_of_slice_display = True

    return zonly, normal


def test_zonly_points_only_subclasses_points_where_needed():
    """ZOnlyPoints is a real subclass only while napari spills by point size."""

    assert issubclass(ZOnlyPoints, Points)
    assert (ZOnlyPoints is Points) == (
        "out_of_slice_display" not in {f.name for f in fields(_PointSliceRequest)}
    )


# Uses ViewerModel rather than napari's ``make_napari_viewer`` fixture: these
# tests only need viewer dims and layer slicing, no Qt window, and
# ``make_napari_viewer`` cannot be mixed with the module scoped ``viewer``
# fixture in tests/data_views/conftest.py (see the note there).


@overrides_slicing
def test_zonly_vs_normal_points():
    viewer = ViewerModel()
    viewer.add_labels(np.zeros((20, 20, 20, 20), dtype=np.uint8))  # to set viewer dims

    data = np.array(
        [
            [1, 4, 20, 20],  # idx 0
            [2, 5, 34, 22],  # idx 1
        ]
    )

    zonly, normal = add_points(viewer, data, out_of_slice_display=True)

    viewer.dims.current_step = (1, 5, 20, 20)

    zonly.refresh()
    normal.refresh()

    n_idx = get_visible_indices(normal)
    z_idx = get_visible_indices(zonly)

    assert set(n_idx) == {0, 1}
    assert z_idx == [0]


@overrides_slicing
def test_zonly_vs_normal_points_5d():
    viewer = ViewerModel()
    viewer.add_labels(
        np.zeros((20, 20, 20, 20, 20), dtype=np.uint8)
    )  # to set viewer dims

    data = np.array(
        [
            [1, 1, 4, 20, 20],  # idx 0
            [3, 2, 5, 34, 22],  # idx 1
            [3, 1, 5, 34, 22],  # idx 2
        ]
    )

    zonly, normal = add_points(viewer, data, out_of_slice_display=True)

    viewer.dims.current_step = (1, 1, 5, 20, 20)

    zonly.refresh()
    normal.refresh()

    n_idx = get_visible_indices(normal)
    z_idx = get_visible_indices(zonly)

    assert set(n_idx) == {0, 1, 2}
    assert z_idx == [0]


def test_zonly_thick_z_slice():
    """A thick slice along z only must not pull in points from other time points.

    This is the napari >= 0.9 way of getting out-of-slice display, and it has to
    keep working on older napari too, where ZOnlyPoints only ever *removes* points
    that spilled along a non-spill axis. Runs on every napari version because the
    ortho views depend on the behaviour whichever class provides it.
    """

    viewer = ViewerModel()
    viewer.add_labels(np.zeros((20, 20, 20, 20), dtype=np.uint8))  # to set viewer dims

    data = np.array(
        [
            [1, 4, 20, 20],  # idx 0: same t, neighbouring z
            [2, 5, 34, 22],  # idx 1: neighbouring t, same z
        ]
    )

    zonly, normal = add_points(viewer, data)

    zonly.projection_mode = "all"  # set explicitily for napari 0.6.2
    normal.projection_mode = "all"

    viewer.dims.current_step = (1, 5, 20, 20)
    viewer.dims.margin_left = (0, 5, 0, 0)
    viewer.dims.margin_right = (0, 5, 0, 0)

    zonly.refresh()
    normal.refresh()

    assert get_visible_indices(zonly) == [0]
    assert get_visible_indices(normal) == [0]


def test_zonly_respects_shown():
    """Points hidden via ``shown`` stay hidden when sliced by ZOnlyPoints.

    Runs on every napari version, as above.
    """

    viewer = ViewerModel()
    viewer.add_labels(np.zeros((20, 20, 20, 20), dtype=np.uint8))  # to set viewer dims

    data = np.array(
        [
            [1, 5, 20, 20],  # idx 0
            [1, 5, 34, 22],  # idx 1
        ]
    )

    zonly, _ = add_points(viewer, data)

    viewer.dims.current_step = (1, 5, 20, 20)
    zonly.refresh()
    assert get_visible_indices(zonly) == [0, 1]

    zonly.shown = [True, False]
    zonly.refresh()
    assert get_visible_indices(zonly) == [0]
