"""Tests for turning napari paint events into the masks funtracks consumes."""

import numpy as np
from funtracks.user_actions.user_update_segmentation import _create_mask_per_label
from funtracks.utils.tracksdata_utils import pixels_to_td_mask

from motile_tracker.data_views.views.layers.contour_labels import as_index_atom
from motile_tracker.data_views.views.layers.track_labels import split_paint_atom

NDIM = 4  # (t, z, y, x)


def masked_atom(time, start, mask, old_region, new_value=9):
    """Build a napari >= 0.8 ``_MaskedPaintAtom`` for a 3D+time segmentation."""
    slice_key = (slice(time, time + 1),) + tuple(
        slice(begin, begin + size)
        for begin, size in zip(start, mask.shape[1:], strict=True)
    )
    return (slice_key, mask, old_region[mask], new_value)


def as_updates_the_old_way(event_val):
    """The multi-index route this replaced: expand every atom, group, rebuild.

    Kept as the reference for what the mask route has to reproduce.
    """
    atoms = [as_index_atom(atom) for atom in event_val]
    indices = tuple(
        np.concatenate([atom[0][dim] for atom in atoms]) for dim in range(NDIM)
    )
    old_values = np.concatenate(
        [np.broadcast_to(np.asarray(a[1]), a[0][0].shape) for a in atoms]
    )
    updates = []
    for old_value in np.unique(old_values):
        of_value = old_values == old_value
        selected = tuple(axis[of_value] for axis in indices)
        for time in np.unique(selected[0]):
            in_slice = selected[0] == time
            pixels = tuple(axis[in_slice] for axis in selected)
            updates.append((pixels_to_td_mask(pixels, NDIM), int(time), int(old_value)))
    return sorted(updates, key=lambda update: (update[2], update[1]))


def combine(event_val):
    """Split the event as TrackLabels does, then combine as funtracks does."""
    updates = [update for atom in event_val for update in split_paint_atom(atom)]
    return _create_mask_per_label(updates, NDIM)


def assert_same_updates(actual, expected):
    assert [(t, v) for _, t, v in actual] == [(t, v) for _, t, v in expected]
    for (got, _, _), (want, _, _) in zip(actual, expected, strict=True):
        assert np.array_equal(np.asarray(got.bbox), np.asarray(want.bbox))
        assert np.array_equal(got.mask, want.mask)


def test_masked_atom_splits_per_label():
    """One update per label painted over, each with a box around just its pixels."""
    mask = np.zeros((1, 1, 4, 4), dtype=bool)
    mask[0, 0, 1:3, 1:3] = True
    old_region = np.zeros(mask.shape, dtype=np.uint32)
    old_region[0, 0, 1, 1:3] = 5  # one label on the top row of the brush
    old_region[0, 0, 2, 1:3] = 6  # another on the bottom row

    updates = combine([masked_atom(2, (10, 20, 30), mask, old_region)])

    assert [(time, old_value) for _, time, old_value in updates] == [(2, 5), (2, 6)]
    for mask_update, _, _ in updates:
        assert mask_update.mask.sum() == 2
    # boxes are in data coordinates and tight around that label's own pixels
    assert np.array_equal(np.asarray(updates[0][0].bbox), [10, 21, 31, 11, 22, 33])
    assert np.array_equal(np.asarray(updates[1][0].bbox), [10, 22, 31, 11, 23, 33])


def test_masked_atom_without_mask_covers_whole_box():
    """napari drops the mask when the whole box changed; the snapshot stands in."""
    old_region = np.full((1, 2, 2, 2), 4, dtype=np.uint32)
    atom = ((slice(1, 2), slice(5, 7), slice(8, 10), slice(0, 2)), None, old_region, 9)

    updates = combine([atom])

    assert len(updates) == 1
    mask, time, old_value = updates[0]
    assert (time, old_value) == (1, 4)
    assert mask.mask.all() and mask.mask.shape == (2, 2, 2)
    assert np.array_equal(np.asarray(mask.bbox), [5, 8, 0, 7, 10, 2])


def test_matches_the_multi_index_route():
    """Masked atoms must land on exactly what expanding to coordinates gave."""
    rng = np.random.default_rng(3)
    mask = rng.random((1, 5, 6, 6)) < 0.6
    old_region = rng.integers(0, 4, size=mask.shape).astype(np.uint32)
    event = [masked_atom(7, (40, 50, 60), mask, old_region)]

    assert_same_updates(combine(event), as_updates_the_old_way(event))


def test_drag_combines_atoms_of_the_same_label():
    """A drag emits one atom per mouse event; each label ends up with one mask."""
    rng = np.random.default_rng(4)
    event = []
    for step in range(5):
        mask = rng.random((1, 3, 4, 4)) < 0.7
        old_region = rng.integers(0, 2, size=mask.shape).astype(np.uint32)
        event.append(masked_atom(1, (10 + step, 20 + 2 * step, 30), mask, old_region))

    updates = combine(event)

    # the atoms overlap in label but not in position, so they must be merged
    assert len(updates) == len({old_value for _, _, old_value in updates})
    assert_same_updates(updates, as_updates_the_old_way(event))


def test_data_setitem_atom_still_supported():
    """napari <= 0.7, and the read-only path, only ever report coordinates."""
    indices = (
        np.array([3, 3, 3, 3]),
        np.array([1, 1, 2, 2]),
        np.array([4, 5, 4, 5]),
        np.array([7, 7, 8, 8]),
    )
    event = [(indices, np.array([1, 1, 2, 2], dtype=np.uint32), 9)]

    updates = combine(event)

    assert [(time, old_value) for _, time, old_value in updates] == [(3, 1), (3, 2)]
    assert_same_updates(updates, as_updates_the_old_way(event))


def test_atom_spanning_several_time_points():
    """Each time point is reported separately, so callers can reject or split them."""
    indices = (
        np.array([3, 3, 4, 4]),
        np.array([1, 2, 1, 2]),
        np.array([4, 5, 4, 5]),
        np.array([7, 8, 7, 8]),
    )
    event = [(indices, np.array([1, 1, 1, 1], dtype=np.uint32), 9)]

    updates = combine(event)

    assert [(time, old_value) for _, time, old_value in updates] == [(3, 1), (4, 1)]
