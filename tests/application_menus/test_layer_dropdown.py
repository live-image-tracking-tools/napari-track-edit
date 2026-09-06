"""Tests for LayerDropdown, the combo box that mirrors the viewer's layer list.

Uses ``napari.components.ViewerModel`` rather than ``make_napari_viewer``: the
dropdown only touches ``viewer.layers`` (its events and name lookup), so no Qt
window is needed, and a ViewerModel is much cheaper to build. A ``qapp`` is still
required because the dropdown itself is a QComboBox.
"""

import numpy as np
import pytest
from napari.components import ViewerModel
from napari.layers import Image, Labels, Points

from motile_tracker.application_menus.layer_dropdown import LayerDropdown


@pytest.fixture
def viewer(qapp):
    """A headless viewer model (qapp requested so QWidgets can be constructed)."""

    return ViewerModel()


@pytest.fixture
def collect():
    """Return (emissions, connect) to record layer_changed emissions."""

    def _collect(dropdown: LayerDropdown) -> list[str]:
        emissions: list[str] = []
        dropdown.layer_changed.connect(emissions.append)
        return emissions

    return _collect


def add_image(viewer, name: str, shape=(5, 10, 10)) -> Image:
    return viewer.add_image(np.zeros(shape, dtype=np.uint16), name=name)


def add_labels(viewer, name: str, shape=(5, 10, 10)) -> Labels:
    return viewer.add_labels(np.zeros(shape, dtype=np.uint16), name=name)


def items(dropdown: LayerDropdown) -> list[str]:
    return [dropdown.itemText(i) for i in range(dropdown.count())]


def test_lists_only_matching_layer_types(viewer):
    """Only layers of the requested types show up in the dropdown."""

    add_image(viewer, "img")
    add_labels(viewer, "seg")
    viewer.add_points(np.zeros((2, 3)), name="pts")

    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    assert items(dropdown) == ["img"]

    dropdown = LayerDropdown(viewer, (Image, Points), follow_active=False)
    assert set(items(dropdown)) == {"img", "pts"}


def test_exclude_types_are_left_out(viewer):
    """exclude_types wins over layer_types for layers matching both."""

    add_image(viewer, "img")
    viewer.add_points(np.zeros((2, 3)), name="pts")

    dropdown = LayerDropdown(
        viewer, (Image, Points), exclude_types=(Points,), follow_active=False
    )
    assert items(dropdown) == ["img"]


def test_allow_none_adds_no_selection_entry(viewer, collect):
    """'No selection' is listed first and maps to a None layer and an empty name."""

    add_image(viewer, "img")

    dropdown = LayerDropdown(viewer, (Image,), allow_none=True, follow_active=False)
    emissions = collect(dropdown)

    assert items(dropdown) == ["No selection", "img"]
    assert dropdown.currentText() == "No selection"
    assert dropdown.selected_layer is None

    dropdown.setCurrentText("img")
    assert dropdown.selected_layer is viewer.layers["img"]
    assert emissions == ["img"]

    dropdown.setCurrentText("No selection")
    assert dropdown.selected_layer is None
    assert emissions == ["img", ""]


def test_empty_viewer_selects_nothing(viewer, collect):
    """With no matching layers there is nothing to select and nothing to emit."""

    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    emissions = collect(dropdown)

    assert items(dropdown) == []
    assert dropdown.selected_layer is None
    assert emissions == []


def test_insert_adds_layer_and_registers_rename_callback(viewer, collect):
    """A newly added matching layer is listed, selected, and watched for renames."""

    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    emissions = collect(dropdown)

    layer = add_image(viewer, "img")

    assert items(dropdown) == ["img"]
    assert dropdown.selected_layer is layer
    assert emissions == ["img"]
    assert id(layer) in dropdown._rename_callbacks


def test_insert_of_unlisted_type_is_ignored(viewer, collect):
    """Adding a layer of an excluded type leaves the dropdown alone."""

    add_image(viewer, "img")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    emissions = collect(dropdown)

    points = viewer.add_points(np.zeros((2, 3)), name="pts")

    assert items(dropdown) == ["img"]
    assert dropdown.selected_layer is viewer.layers["img"]
    assert emissions == []
    assert id(points) not in dropdown._rename_callbacks


def test_unrelated_insert_keeps_selection_without_re_emitting(viewer, collect):
    """Rebuilding the list for an unrelated layer must not re-emit layer_changed.

    Regression guard: clear()/addItem() emit currentTextChanged for the transient
    empty state, which used to report a None selection and tear down the connected
    source layer just because another layer was added.
    """

    first = add_image(viewer, "img")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    emissions = collect(dropdown)

    add_image(viewer, "other")

    assert set(items(dropdown)) == {"img", "other"}
    assert dropdown.currentText() == "img"
    assert dropdown.selected_layer is first
    assert emissions == []


def test_rename_updates_dropdown(viewer, collect):
    """Renaming a layer added after construction refreshes the entries."""

    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    layer = add_image(viewer, "img")
    emissions = collect(dropdown)

    layer.name = "renamed"

    assert items(dropdown) == ["renamed"]
    assert dropdown.selected_layer is layer
    assert emissions == ["renamed"]


def test_rename_of_pre_existing_layer_updates_dropdown(viewer):
    """Layers loaded before the dropdown was built are watched for renames too.

    Regression guard: rename callbacks used to be hooked up only in _on_insert, so
    renaming an image that was loaded before the menu left a stale dropdown entry.
    """

    layer = add_image(viewer, "img")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    assert id(layer) in dropdown._rename_callbacks

    layer.name = "renamed"

    assert items(dropdown) == ["renamed"]
    assert dropdown.selected_layer is layer


def test_pre_existing_layers_of_other_types_are_not_watched(viewer):
    """Only listed layers get a rename hook, whenever they were added."""

    points = viewer.add_points(np.zeros((2, 3)), name="pts")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)

    assert dropdown._rename_callbacks == {}

    points.name = "renamed"
    assert items(dropdown) == []


def test_set_layer_types_watches_newly_listed_layers(viewer):
    """Layers that only become listed after set_layer_types are watched from then on."""

    image = add_image(viewer, "img")
    points = viewer.add_points(np.zeros((2, 3)), name="pts")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    assert id(points) not in dropdown._rename_callbacks

    dropdown.set_layer_types((Image, Points))

    points.name = "renamed_pts"
    assert set(items(dropdown)) == {"img", "renamed_pts"}

    # the already-watched image is not connected a second time
    image.name = "renamed_img"
    assert set(items(dropdown)) == {"renamed_img", "renamed_pts"}
    assert len(dropdown._rename_callbacks) == 2


def test_removed_layer_is_dropped_and_disconnected(viewer):
    """Removing a layer removes its entry and its rename callback."""

    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    layer = add_image(viewer, "img")
    other = add_image(viewer, "other")
    assert set(items(dropdown)) == {"img", "other"}

    viewer.layers.remove(layer)

    assert items(dropdown) == ["other"]
    assert id(layer) not in dropdown._rename_callbacks
    assert id(other) in dropdown._rename_callbacks

    # the disconnected layer no longer drives updates
    layer.name = "renamed_after_removal"
    assert items(dropdown) == ["other"]


def test_removing_the_selected_layer_moves_selection(viewer, collect):
    """When the selected layer disappears, the dropdown falls back and re-emits."""

    layer = add_image(viewer, "img")
    add_image(viewer, "other")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    dropdown.setCurrentText("img")
    emissions = collect(dropdown)

    viewer.layers.remove(layer)

    assert dropdown.currentText() == "other"
    assert dropdown.selected_layer is viewer.layers["other"]
    assert emissions == ["other"]


def test_follow_active_tracks_viewer_selection(viewer, collect):
    """With follow_active, selecting a layer in the viewer moves the dropdown."""

    first = add_image(viewer, "img")
    second = add_image(viewer, "other")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=True)
    viewer.layers.selection.active = first
    emissions = collect(dropdown)

    viewer.layers.selection.active = second
    assert dropdown.currentText() == "other"
    assert dropdown.selected_layer is second
    assert emissions[-1] == "other"

    viewer.layers.selection.active = first
    assert dropdown.currentText() == "img"
    assert dropdown.selected_layer is first
    assert emissions[-1] == "img"


def test_follow_active_ignores_unlisted_and_multi_selection(viewer):
    """Layers of another type, and multi-selections, leave the dropdown alone."""

    image = add_image(viewer, "img")
    other = add_image(viewer, "other")
    points = viewer.add_points(np.zeros((2, 3)), name="pts")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=True)
    viewer.layers.selection.active = image
    assert dropdown.currentText() == "img"

    # a layer that is not listed does not steal the selection
    viewer.layers.selection.active = points
    assert dropdown.currentText() == "img"
    assert dropdown.selected_layer is image

    # neither does selecting several layers at once
    viewer.layers.selection.clear()
    viewer.layers.selection.update({image, other})
    assert dropdown.currentText() == "img"
    assert dropdown.selected_layer is image


def test_follow_active_false_ignores_viewer_selection(viewer, collect):
    """Without follow_active the dropdown only changes when the user picks a layer."""

    first = add_image(viewer, "img")
    second = add_image(viewer, "other")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    dropdown.setCurrentText("img")
    viewer.layers.selection.active = first
    emissions = collect(dropdown)

    viewer.layers.selection.active = second

    assert dropdown.currentText() == "img"
    assert dropdown.selected_layer is first
    assert emissions == []


def test_set_layer_types_refilters(viewer, collect):
    """set_layer_types swaps both the included and the excluded types."""

    add_image(viewer, "img")
    viewer.add_points(np.zeros((2, 3)), name="pts")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    emissions = collect(dropdown)
    assert items(dropdown) == ["img"]

    dropdown.set_layer_types((Points,))
    assert items(dropdown) == ["pts"]
    assert dropdown.selected_layer is viewer.layers["pts"]
    assert emissions == ["pts"]

    dropdown.set_layer_types((Image, Points), exclude_types=(Points,))
    assert items(dropdown) == ["img"]
    assert dropdown.layer_types == (Image, Points)
    assert dropdown.exclude_types == (Points,)


def test_destroy_disconnects_from_the_viewer(viewer, collect):
    """After teardown the dropdown stops responding to viewer events."""

    dropdown = LayerDropdown(viewer, (Image,), follow_active=True)
    layer = add_image(viewer, "img")
    emissions = collect(dropdown)
    assert dropdown._rename_callbacks  # a live rename hook to be cleaned up

    dropdown._on_destroyed()

    assert dropdown._deleted
    assert dropdown._rename_callbacks == {}

    # none of the viewer events reach the dropdown anymore
    second = add_image(viewer, "other")
    viewer.layers.selection.active = second
    layer.name = "renamed"
    viewer.layers.remove(second)

    assert items(dropdown) == ["img"]
    assert emissions == []


def test_destroy_is_idempotent(viewer):
    """Tearing down twice (e.g. explicit cleanup plus Qt destroyed) does not raise."""

    dropdown = LayerDropdown(viewer, (Image,), follow_active=True)
    add_image(viewer, "img")

    dropdown._on_destroyed()
    dropdown._on_destroyed()

    assert dropdown._deleted


def test_handlers_are_inert_after_teardown(viewer, collect):
    """Every handler bails out on a deleted widget, even if called directly.

    Qt can still deliver a queued event after ``destroyed``, so the ``_deleted``
    guards are the second line of defence behind disconnecting.
    """

    dropdown = LayerDropdown(viewer, (Image,), follow_active=True)
    layer = add_image(viewer, "img")
    emissions = collect(dropdown)
    dropdown._on_destroyed()

    class _Event:
        value = layer

    dropdown._on_insert(_Event())
    dropdown._on_removed(_Event())
    dropdown._on_selection_changed()
    dropdown._update_dropdown()
    dropdown._emit_layer_changed()

    assert items(dropdown) == ["img"]
    assert dropdown._rename_callbacks == {}
    assert emissions == []


def test_rename_callback_is_a_noop_once_the_widget_is_gone(viewer):
    """The rename callback holds only a weak reference and stays silent afterwards."""

    add_image(viewer, "img")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=False)
    callback = dropdown._make_weak_rename_cb()

    dropdown._deleted = True
    callback()  # must not raise, and must not touch the deleted widget

    assert items(dropdown) == ["img"]


def test_handlers_survive_a_broken_viewer(viewer):
    """A viewer that is being torn down must not turn into an exception."""

    add_image(viewer, "img")
    dropdown = LayerDropdown(viewer, (Image,), follow_active=True)

    class BrokenViewer:
        @property
        def layers(self):
            raise RuntimeError("C++ object deleted")

    dropdown.viewer = BrokenViewer()

    # all handlers swallow the teardown errors instead of propagating them
    dropdown._update_dropdown()
    dropdown._emit_layer_changed()
    dropdown._on_selection_changed()
    dropdown._on_destroyed()
