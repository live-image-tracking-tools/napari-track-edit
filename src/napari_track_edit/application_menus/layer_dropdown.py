import contextlib
import weakref

import napari
from psygnal import Signal
from qtpy.QtWidgets import QComboBox


class LayerDropdown(QComboBox):
    """QComboBox widget with functions for updating the selected layer and to update the
    list of options when the list of layers is modified.

    Args:
        viewer (napari.Viewer): the viewer whose layers are listed.
        layer_types (tuple): the layer types to list.
        allow_none (bool): whether to add a 'No selection' entry. Defaults to False.
        exclude_types (tuple): layer types to leave out of the list.
        follow_active (bool): when True (the default), the dropdown follows the active
            layer in the viewer. Set to False to only change the selection when the user
            explicitly picks a layer from the dropdown.
    """

    layer_changed = Signal(str)

    def __init__(
        self,
        viewer: napari.Viewer,
        layer_types: tuple,
        allow_none=False,
        exclude_types: tuple = (),
        follow_active: bool = True,
    ):
        super().__init__()

        self.viewer = viewer
        self.layer_types = layer_types
        self.exclude_types = exclude_types
        self.allow_none = allow_none
        self.follow_active = follow_active
        self.selected_layer = None
        self._deleted = False

        # track rename callbacks so we can disconnect them at cleanup
        self._rename_callbacks: dict[int, tuple[weakref.ref, callable]] = {}
        self.destroyed.connect(self._on_destroyed)  # for reference cleanup

        # viewer connections
        self.viewer.layers.events.inserted.connect(self._on_insert)
        self.viewer.layers.events.changed.connect(self._update_dropdown)
        self.viewer.layers.events.removed.connect(self._on_removed)
        if self.follow_active:
            self.viewer.layers.selection.events.changed.connect(
                self._on_selection_changed
            )

        self.currentTextChanged.connect(self._emit_layer_changed)

        # layers that are already present must be watched for renames too
        for layer in self.viewer.layers:
            self._watch_name(layer)

        self._update_dropdown()

    def _watch_name(self, layer) -> bool:
        """Start tracking name changes of this layer, if it is one we list.

        Returns:
            True if the layer is listed (and is now watched), False otherwise.
        """

        if not isinstance(layer, self.layer_types) or isinstance(
            layer, self.exclude_types
        ):
            return False

        if id(layer) not in self._rename_callbacks:  # never connect twice
            cb = self._make_weak_rename_cb()
            layer.events.name.connect(cb)
            self._rename_callbacks[id(layer)] = (weakref.ref(layer), cb)

        return True

    def _make_weak_rename_cb(self):
        """Create a weak callback to track name updates but do not let the layer keep the
        widget alive forever."""

        self_ref = weakref.ref(self)

        def _rename_cb(event=None):
            self_obj = self_ref()
            if self_obj is None or self_obj._deleted:
                return
            with contextlib.suppress(AttributeError, RuntimeError):
                self_obj._update_dropdown()

        return _rename_cb

    def _on_insert(self, event) -> None:
        """Update dropdown and make new layer responsive to name changes"""

        if self._deleted:
            return

        if self._watch_name(event.value):
            self._update_dropdown()

    def _on_removed(self, event) -> None:
        """Disconnect signals and update dropdown when a layer is removed."""

        if self._deleted:
            return

        layer = event.value
        pair = self._rename_callbacks.pop(id(layer), None)
        if pair is not None:
            layer_ref, cb = pair
            layer_obj = layer_ref() if layer_ref else None
            target = layer_obj if layer_obj else layer
            with contextlib.suppress(AttributeError, RuntimeError, TypeError):
                target.events.name.disconnect(cb)

        self._update_dropdown()

    def _on_selection_changed(self):
        """Update the active layer when the selection changes"""
        if self._deleted:
            return

        try:
            if len(self.viewer.layers.selection) == 1:
                selected = self.viewer.layers.selection.active
                if (
                    isinstance(selected, self.layer_types)
                    and not isinstance(selected, self.exclude_types)
                    and selected != self.selected_layer
                ):
                    self.setCurrentText(selected.name)
                    self._emit_layer_changed()
        except (AttributeError, RuntimeError, TypeError):
            pass

    def _update_dropdown(self, event=None) -> None:
        """Update the layers in the dropdown"""

        if self._deleted:
            return

        try:
            previous = self.currentText()
            # Block signals while rebuilding: clear()/addItem() emit currentTextChanged
            # for the transient empty/partial states, which would momentarily report a
            # None/other selection and (e.g.) tear down a connected source layer just
            # because an unrelated layer was added. Emit once at the end, only if the
            # effective selection really changed.
            self.blockSignals(True)
            try:
                self.clear()

                layers = [
                    layer
                    for layer in self.viewer.layers
                    if isinstance(layer, self.layer_types)
                    and not isinstance(layer, self.exclude_types)
                ]

                names = []
                if self.allow_none:
                    self.addItem("No selection")
                    names.append("No selection")

                for layer in layers:
                    self.addItem(layer.name)
                    names.append(layer.name)

                # restore previous selection if still valid
                if previous in names:
                    self.setCurrentText(previous)
            finally:
                self.blockSignals(False)

            if self.currentText() != previous:
                self._emit_layer_changed()
        except (AttributeError, RuntimeError, TypeError):
            pass

    def set_layer_types(self, layer_types: tuple, exclude_types: tuple = ()) -> None:
        """Change which layer types are listed (and which to exclude) and refresh."""

        self.layer_types = layer_types
        self.exclude_types = exclude_types

        # layers that were not listed before may be listed now
        for layer in self.viewer.layers:
            self._watch_name(layer)

        self._update_dropdown()

    def _emit_layer_changed(self) -> None:
        """Emit a signal holding the currently selected layer"""

        if self._deleted:
            return

        try:
            name = self.currentText()
            if name != "No selection" and name in self.viewer.layers:
                self.selected_layer = self.viewer.layers[name]
            else:
                self.selected_layer = None
                name = ""
            self.layer_changed.emit(name)
        except (AttributeError, RuntimeError, TypeError):
            pass

    def _on_destroyed(self, *args):
        """Disconnect everything cleanly"""

        self._deleted = True

        with contextlib.suppress(AttributeError, RuntimeError, TypeError):
            self.viewer.layers.events.inserted.disconnect(self._on_insert)
            self.viewer.layers.events.changed.disconnect(self._update_dropdown)
            self.viewer.layers.events.removed.disconnect(self._on_removed)
            if self.follow_active:
                self.viewer.layers.selection.events.changed.disconnect(
                    self._on_selection_changed
                )

        for layer_ref, cb in self._rename_callbacks.values():
            layer_obj = layer_ref() if layer_ref else None
            target = layer_obj
            if target:
                with contextlib.suppress(AttributeError, RuntimeError, TypeError):
                    target.events.name.disconnect(cb)

        self._rename_callbacks.clear()

        with contextlib.suppress(AttributeError, RuntimeError, TypeError):
            self.currentTextChanged.disconnect(self._emit_layer_changed)
