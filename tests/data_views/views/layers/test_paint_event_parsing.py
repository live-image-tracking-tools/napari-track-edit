"""End-to-end tests for ``TrackLabels._parse_paint_event``.

``test_paint_atoms.py`` checks the two parsing functions against hand-built atoms.
These tests instead drive a real napari labels layer through real ``paint`` calls
and check the parsed updates against the change the paint actually made to the
array: every changed pixel must be reported under the value it held before the
stroke, nothing else may be reported, and once funtracks has combined the updates
each pixel must belong to exactly one label.

Which atom form a real paint emits depends on the installed napari (masks from
0.8, multi-indices before that), and the project supports both. The helpers here
therefore take either form, so every test runs on either version, and
``test_mask_atoms_are_checked_the_same_way`` builds the mask form by hand so it
stays covered on an older napari.

Both data backends are covered too, because they make napari behave differently:

- a writable numpy array takes the paint, so napari's own "this pixel already
  holds the new label" check suppresses repeat visits and one brush position
  yields at most one atom;
- a read-only array (what the plugin really runs on, since funtracks owns the
  write) never takes it, so every brush position reports its whole box afresh and
  a stroke arrives as dozens of duplicate atoms.

Both must parse to the same updates.
"""

import numpy as np
import pytest
from funtracks.user_actions.user_update_segmentation import (
    _create_masks_from_bboxes,
    _create_masks_from_multi_index,
)
from napari.layers import Labels
from napari.utils import DirectLabelColormap

from napari_track_edit.data_views.lazy_array_wrapper import LazyArrayWrapper
from napari_track_edit.data_views.views.layers.contour_labels import ContourLabels
from napari_track_edit.data_views.views.layers.track_labels import TrackLabels

TIME = 1  # the frame every stroke is painted on
NEW = 9  # the label painted with
NDIM = 3  # (t, y, x)


class ReadOnlyArray:
    """Stands in for tracksdata's ``GraphArrayView``.

    The two properties that matter: it has no ``__setitem__``, and reading from it
    rasterizes into a fresh buffer rather than handing out a view of the stored
    segmentation. Without the second one, napari's read-modify-write would reach
    the array through the returned view and the test would silently exercise the
    writable path.
    """

    def __init__(self, data):
        self._data = data

    shape = property(lambda self: self._data.shape)
    dtype = property(lambda self: self._data.dtype)
    ndim = property(lambda self: self._data.ndim)
    size = property(lambda self: self._data.size)

    def __getitem__(self, index):
        return np.array(self._data[index])

    def __array__(self, dtype=None, copy=None):
        return np.array(self._data, dtype=dtype, copy=copy)


def segmentation():
    """A frame with two labels side by side, and background around them."""
    seg = np.zeros((3, 20, 20), dtype=np.uint32)
    seg[TIME, 5:10, 5:10] = 1
    seg[TIME, 5:10, 12:16] = 2
    return seg


def make_layer(data, brush_size=3):
    colors = {label: [0, 0, 0, 1] for label in (1, 2, NEW)}
    layer = ContourLabels(
        data=data,
        name="seg",
        opacity=1.0,
        scale=(1, 1, 1),
        colormap=DirectLabelColormap(color_dict={**colors, None: [0, 0, 0, 0]}),
    )
    layer.brush_size = brush_size
    layer.n_edit_dimensions = 2  # never paint across time, as TrackLabels enforces
    return layer


def paint_stroke(layer, coords, value=NEW):
    """Run one stroke and return the atoms of the paint event it emits.

    ``block_history`` is what napari's own drag callback uses: the atoms are
    staged and a single event fires when the stroke ends.
    """
    events = []
    layer.events.paint.connect(lambda event: events.append(event.value))
    with layer.block_history():
        for coord in coords:
            layer.paint(coord, value, refresh=False)
    assert len(events) <= 1, "a stroke must emit at most one paint event"
    return events[0] if events else []


def pixels_of(update):
    """The (time, row, column) index of an update, in whichever form it came.

    The parse reports masks on napari >= 0.8 and multi-indices on napari <= 0.7;
    everything these tests assert holds for both, so the helpers take both.
    """
    if len(update) == 2:  # (multi-index, old value)
        return update[0]
    mask, time, _old_value = update
    rows, cols = mask.mask_indices()
    return np.full(rows.shape, time), rows, cols


def old_value_of(update):
    """Both forms carry the old value last."""
    return update[-1]


def time_of(update):
    return update[1] if len(update) == 3 else int(update[0][0][0])


def combine(updates):
    """Hand the updates to whichever funtracks combiner takes that form."""
    if len(updates[0]) == 3:
        return _create_masks_from_bboxes(updates)
    return _create_masks_from_multi_index(updates, NDIM)


def assert_updates_match_diff(updates, before, after, new_value=NEW):
    """The updates must describe exactly the change the paint made to the array.

    Every changed pixel is reported, carrying the value it held before the stroke,
    and nothing else is reported. A pixel may appear in more than one update here:
    the parse reports per brush position, and brush positions overlap. It cannot
    appear under two different labels, because each update's pixels are checked
    against ``before``.
    """
    reported = np.zeros(before.shape, dtype=bool)
    for update in updates:
        index = pixels_of(update)
        old_value = old_value_of(update)
        assert np.all(before[index] == old_value), (
            f"update claims old value {old_value} for pixels that held "
            f"{np.unique(before[index])}"
        )
        assert np.all(after[index] == new_value), "pixel was not actually painted"
        reported[index] = True

    assert np.array_equal(reported, before != after), (
        f"{reported.sum()} pixels reported, {(before != after).sum()} actually changed"
    )


def assert_combined_partitions_diff(updates, before, after, new_value=NEW):
    """What funtracks ends up acting on: one mask per label, and no pixel twice."""
    combined = combine(updates)

    keys = [(time, old_value) for _, time, old_value in combined]
    assert len(keys) == len(set(keys)), "a label was left with more than one mask"

    reported = np.zeros(before.shape, dtype=bool)
    for entry in combined:
        index = pixels_of(entry)
        assert not reported[index].any(), "pixel reported by two labels"
        reported[index] = True
    assert np.array_equal(reported, before != after)

    for mask, _time, _old_value in combined:
        # every box is tight: each face of it holds at least one set pixel
        assert mask.mask[0].any() and mask.mask[-1].any()
        assert mask.mask[:, 0].any() and mask.mask[:, -1].any()

    return combined


def parse(event_val):
    return TrackLabels._parse_paint_event(event_val)


# --------------------------------------------------------------------------- #
# mask atoms (napari >= 0.8)
# --------------------------------------------------------------------------- #


def test_stroke_over_two_labels_and_background_matches_the_array_diff():
    """The headline case: one stroke crossing label 1, label 2 and background."""
    before = segmentation()
    layer = make_layer(before.copy())

    # a drag straight across the gap between the two labels
    event_val = paint_stroke(layer, [(TIME, 7, col) for col in range(8, 14)])
    after = np.asarray(layer.data)

    updates = parse(event_val)

    assert {old_value_of(update) for update in updates} == {0, 1, 2}
    assert all(time_of(update) == TIME for update in updates)
    assert_updates_match_diff(updates, before, after)
    assert_combined_partitions_diff(updates, before, after)


def test_read_only_layer_repeats_atoms_but_parses_the_same():
    """The real backend: many duplicate atoms, and the array is never written.

    The same stroke on a writable twin gives the ground truth to check against.
    """
    before = segmentation()
    coords = [(TIME, 7, col) for col in (8, 8, 8, 9, 9, 10, 10, 10, 10, 11, 12, 13)]

    writable = make_layer(before.copy())
    writable_event = paint_stroke(writable, coords)
    after = np.asarray(writable.data)

    read_only = make_layer(LazyArrayWrapper(ReadOnlyArray(before.copy())))
    read_only_event = paint_stroke(read_only, coords)

    # nothing can be suppressed here: every brush position reports afresh
    assert len(read_only_event) == len(coords)
    # whereas napari drops what the writable array already holds
    assert len(writable_event) <= len(read_only_event)
    # and the segmentation itself is untouched: funtracks owns that write
    assert np.array_equal(np.asarray(read_only.data), before)

    updates = parse(read_only_event)
    assert_updates_match_diff(updates, before, after)

    # both routes must land on the same masks once funtracks has combined them
    from_writable = assert_combined_partitions_diff(
        parse(writable_event), before, after
    )
    from_read_only = assert_combined_partitions_diff(updates, before, after)
    assert [(t, v) for _, t, v in from_writable] == [
        (t, v) for _, t, v in from_read_only
    ]
    for (got, _, _), (want, _, _) in zip(from_read_only, from_writable, strict=True):
        assert np.array_equal(np.asarray(got.bbox), np.asarray(want.bbox))
        assert np.array_equal(got.mask, want.mask)


def test_erasing_matches_the_array_diff():
    """Erasing is a paint with the background label, and parses the same way."""
    before = segmentation()
    layer = make_layer(before.copy())

    event_val = paint_stroke(layer, [(TIME, 6, 6), (TIME, 7, 7)], value=0)
    after = np.asarray(layer.data)

    updates = parse(event_val)

    assert {old_value_of(update) for update in updates} == {1}
    assert_updates_match_diff(updates, before, after, new_value=0)
    assert_combined_partitions_diff(updates, before, after, new_value=0)


def test_repainting_the_same_pixels_reports_nothing():
    """A stroke that changes nothing must not reach funtracks at all."""
    before = segmentation()
    layer = make_layer(before.copy())
    paint_stroke(layer, [(TIME, 7, 7)])

    # paint the exact same spot again, now already holding the new label
    second = paint_stroke(layer, [(TIME, 7, 7)])

    assert second == []
    assert parse(second) == []


def test_a_label_touched_in_two_places_stays_one_mask():
    """Two passes over label 1 must combine into a single update for it."""
    before = segmentation()
    layer = make_layer(before.copy())

    # top edge of label 1, then its bottom edge, with a gap between
    event_val = paint_stroke(layer, [(TIME, 6, 6), (TIME, 6, 8), (TIME, 9, 6)])
    after = np.asarray(layer.data)

    updates = parse(event_val)
    assert_updates_match_diff(updates, before, after)

    combined = assert_combined_partitions_diff(updates, before, after)
    for_label_1 = [entry for entry in combined if entry[2] == 1]
    assert len(for_label_1) == 1

    mask = for_label_1[0][0]
    rows, cols = mask.mask_indices()
    assert np.all(before[TIME, rows, cols] == 1)
    assert np.all(after[TIME, rows, cols] == NEW)


@pytest.mark.parametrize("brush_size", [1, 2, 5, 8])
def test_any_brush_size_matches_the_array_diff(brush_size):
    """Brush shape and clipping at the frame edge must not confuse the parse."""
    before = segmentation()
    layer = make_layer(before.copy(), brush_size=brush_size)

    # includes a position at the corner, where napari clips the brush box
    event_val = paint_stroke(layer, [(TIME, 0, 0), (TIME, 6, 6), (TIME, 7, 13)])
    after = np.asarray(layer.data)

    updates = parse(event_val)
    assert_updates_match_diff(updates, before, after)
    assert_combined_partitions_diff(updates, before, after)


def test_mask_atoms_are_checked_the_same_way():
    """Cover the mask form even when the installed napari never produces it.

    Which form a real paint emits depends on the napari version, so the layer
    cannot be relied on to exercise both. This builds the ``_MaskedPaintAtom``
    shape directly - including the repeats a read-only backend causes - and runs
    it through the same checks.
    """
    before = segmentation()
    box = (slice(TIME, TIME + 1), slice(8, 11), slice(8, 11))  # straddles label 1
    # the whole box changed, so napari drops the mask and keeps a snapshot
    atom = (box, None, before[box].copy(), NEW)
    after = before.copy()
    after[box] = NEW

    updates = parse([atom] * 4)

    assert len(updates[0]) == 3, "atoms in the mask form must parse to the mask form"
    assert {old_value_of(update) for update in updates} == {0, 1}
    assert_updates_match_diff(updates, before, after)
    assert_combined_partitions_diff(updates, before, after)


# --------------------------------------------------------------------------- #
# multi-index atoms (napari <= 0.7, and ContourLabels.data_setitem)
# --------------------------------------------------------------------------- #


def test_data_setitem_event_matches_the_array_diff():
    """The legacy form reports coordinates, so it is checked against them."""
    before = segmentation()
    layer = make_layer(before.copy())

    indices = (
        np.array([TIME, TIME, TIME, TIME]),
        np.array([6, 6, 7, 7]),
        np.array([6, 13, 6, 13]),  # two pixels of label 1, two of label 2
    )
    events = []
    layer.events.paint.connect(lambda event: events.append(event.value))
    with layer.block_history():
        layer.data_setitem(indices, NEW, refresh=False)
    after = np.asarray(layer.data)

    updates = parse(events[0])

    # the multi-index form: (multi-index, old value), one entry per label
    assert [old_value for _, old_value in updates] == [1, 2]
    reported = np.zeros(before.shape, dtype=bool)
    for index, old_value in updates:
        assert np.all(before[index] == old_value)
        assert np.all(after[index] == NEW)
        reported[index] = True
    assert np.array_equal(reported, before != after)


# --------------------------------------------------------------------------- #
# reverting a paint (ContourLabels.undo)
# --------------------------------------------------------------------------- #


def displayed_segmentation():
    """The same content on frame 0, so the layer's default slice shows it."""
    seg = np.zeros((2, 20, 20), dtype=np.uint32)
    seg[0, 5:10, 5:10] = 1
    seg[0, 5:10, 12:16] = 2
    return seg


def read_only_layer_showing_the_painted_frame():
    return make_layer(LazyArrayWrapper(ReadOnlyArray(displayed_segmentation())))


def test_undo_restores_the_display_from_the_untouched_array():
    """The revert path: the buffer goes back to what the array still holds.

    Nothing was written during the stroke, so re-slicing restores the pre-stroke
    state; the history atoms never have to be replayed.
    """
    layer = read_only_layer_showing_the_painted_frame()
    before = np.array(layer._slice.image.raw)

    paint_stroke(layer, [(0, 7, col) for col in (6, 6, 7, 7, 8, 9, 13)])
    assert not np.array_equal(np.array(layer._slice.image.raw), before), (
        "the stroke should have shown up in the display buffer"
    )

    layer.undo()

    assert np.array_equal(np.array(layer._slice.image.raw), before)


def test_undo_emits_no_paint_event():
    """Why this override exists: a paint event here would re-enter _on_paint."""
    layer = read_only_layer_showing_the_painted_frame()
    paint_stroke(layer, [(0, 7, 7)])

    events = []
    layer.events.paint.connect(lambda event: events.append(event.value))
    layer.undo()

    assert events == []


def test_undo_drops_the_item_instead_of_queueing_it_for_redo():
    """A paint that never reached the data cannot be re-applied by this layer.

    Keeping the redo queue empty is also what makes the inherited
    ``Labels.redo()`` harmless, so the two belong together.
    """
    layer = read_only_layer_showing_the_painted_frame()
    assert len(paint_stroke(layer, [(0, 7, 6), (0, 7, 8)])) > 1

    layer.undo()

    assert len(layer._undo_history) == 0
    assert len(layer._redo_history) == 0


def test_redo_on_read_only_data_does_not_raise():
    """napari binds Ctrl+Shift+Z to Labels.redo() on every labels layer.

    The ortho-view copies are plain ContourLabels, so they do not route redo to
    the tracks viewer the way TrackLabels does. Without the override, the
    inherited implementation assigns into self.data and raises
    ``TypeError: 'LazyArrayWrapper' object does not support item assignment``.
    """
    layer = read_only_layer_showing_the_painted_frame()
    before = np.array(layer._slice.image.raw)
    paint_stroke(layer, [(0, 7, 6), (0, 7, 8)])
    layer.undo()

    layer.redo()  # must not raise

    # the display still shows what the data holds, which the paint never reached
    assert np.array_equal(np.array(layer._slice.image.raw), before)


def test_redo_on_read_only_data_leaves_the_display_alone():
    """Inert means inert: it must not re-slice the painted buffer away either.

    A redo keypress has nothing to do at this level, so it should not double as a
    resync that silently discards what is on screen.
    """
    layer = read_only_layer_showing_the_painted_frame()
    paint_stroke(layer, [(0, 7, 6), (0, 7, 8)])
    painted = np.array(layer._slice.image.raw)

    layer.redo()

    assert np.array_equal(np.array(layer._slice.image.raw), painted)


def test_redo_on_writable_data_still_replays_the_paint():
    """Writable data keeps napari's own undo/redo pair intact."""
    before = displayed_segmentation()
    layer = make_layer(before.copy())
    paint_stroke(layer, [(0, 7, col) for col in (6, 7, 8)])
    painted = np.asarray(layer.data).copy()

    layer.undo()
    assert np.array_equal(np.asarray(layer.data), before)

    layer.redo()
    assert np.array_equal(np.asarray(layer.data), painted)


def test_undo_with_no_history_does_nothing():
    layer = read_only_layer_showing_the_painted_frame()
    before = np.array(layer._slice.image.raw)

    layer.undo()

    assert np.array_equal(np.array(layer._slice.image.raw), before)


def test_undo_on_writable_data_still_restores_the_array():
    """Writable data keeps napari's own undo, which rolls the array back."""
    before = displayed_segmentation()
    layer = make_layer(before.copy())

    paint_stroke(layer, [(0, 7, col) for col in (6, 7, 8, 13)])
    assert not np.array_equal(np.asarray(layer.data), before)

    layer.undo()

    assert np.array_equal(np.asarray(layer.data), before)


# ContourLabels defines _abort_stroke itself, so the probe has to be the napari
# class: only napari >= 0.8 stages a stroke and can abort one.
needs_staged_strokes = pytest.mark.skipif(
    not hasattr(Labels, "_abort_stroke"),
    reason="napari < 0.8 has no encircle-and-fill stroke to abort",
)


@needs_staged_strokes
def test_abort_stroke_on_read_only_data_does_not_raise():
    """Aborting the encircle-and-fill stroke must not write to the array.

    napari >= 0.8 stages that stroke and aborts it when the tool is disabled
    mid-stroke (a mode switch, say). Without the override, the inherited
    implementation writes every staged atom back and raises
    ``TypeError: 'LazyArrayWrapper' object does not support item assignment``.
    """
    layer = read_only_layer_showing_the_painted_frame()
    before = np.array(layer._slice.image.raw)

    layer._begin_stroke()
    for col in (6, 7, 8):
        layer.paint((0, 7, col), NEW, refresh=False)
    assert layer._staged_history, "the stroke should have staged something"

    layer._abort_stroke()  # must not raise

    assert np.array_equal(np.array(layer._slice.image.raw), before)
    assert layer._staged_history == []


@needs_staged_strokes
def test_abort_stroke_emits_no_paint_event():
    """As with undo: a paint event here would re-enter _on_paint."""
    layer = read_only_layer_showing_the_painted_frame()
    layer._begin_stroke()
    layer.paint((0, 7, 7), NEW, refresh=False)

    events = []
    layer.events.paint.connect(lambda event: events.append(event.value))
    layer._abort_stroke()

    assert events == []
    assert len(layer._undo_history) == 0


@needs_staged_strokes
def test_abort_stroke_on_writable_data_still_reverts_the_array():
    """Writable data keeps napari's own abort, which rolls the array back."""
    before = displayed_segmentation()
    layer = make_layer(before.copy())

    layer._begin_stroke()
    for col in (6, 7, 8):
        layer.paint((0, 7, col), NEW, refresh=False)
    assert not np.array_equal(np.asarray(layer.data), before)

    layer._abort_stroke()

    assert np.array_equal(np.asarray(layer.data), before)
