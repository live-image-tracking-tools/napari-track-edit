import contextlib
import itertools
from collections.abc import Callable
from contextlib import contextmanager

import napari
import numpy as np
from fonticon_fa6 import FA6S
from napari.layers import Image, Labels, Points
from napari.layers.points._points_mouse_bindings import DRAG_DIST_THRESHOLD
from napari.layers.points._points_mouse_bindings import add as napari_add_point
from napari.layers.utils.plane import ClippingPlane
from napari.utils.geometry import point_in_bounding_box
from qtpy import QtCore
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledRangeSlider, QLabeledSlider
from superqt.fonticon import icon as qticon

from napari_track_edit.application_menus.layer_dropdown import LayerDropdown


@contextmanager
def silenced(slider):
    """Update a slider without it writing back to the layers

    Changing the range of a slider makes it re-emit its (stale) value, which would
    otherwise be applied to the layer whose settings we are about to restore.
    """

    was_blocked = slider.signalsBlocked()
    slider.blockSignals(True)
    try:
        yield
    finally:
        slider.blockSignals(was_blocked)


def offset_along(position, normal) -> float:
    """Signed distance of a position from the origin, along a (not necessarily unit) normal"""

    normal = np.asarray(normal, dtype=float)
    return np.dot(position, normal) / np.dot(normal, normal)


def create_compact_qwidget(*widgets) -> QWidget:
    """Lay out widgets side by side without margins, a None adds a stretch"""

    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(2, 2, 2, 2)
    layout.setSpacing(4)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        else:
            layout.addWidget(widget)
    return row


def displayed_layer_dims(layer, event) -> list[int]:
    """Map the displayed dimensions of the event onto the dimensions of the layer

    The event carries the displayed dimensions of the viewer, while the layer methods
    below index into the dimensions of the layer. Both are only the same when the layer
    has as many dimensions as the viewer.
    """

    return list(
        layer._world_to_layer_dims(
            world_dims=event.dims_displayed, ndim_world=len(event.position)
        )
    )


def plane_click_position(plane_layer, event):
    """Where the click of the event crosses the plane of the layer, in world coordinates

    Returns None if the click does not land on the plane within the layer.
    """

    dims_displayed = displayed_layer_dims(plane_layer, event)
    if len(dims_displayed) < 3:
        return None

    # the ray under the mouse, in the data coordinates of the plane layer
    position = np.asarray(plane_layer.world_to_data(event.position), dtype=float)
    direction = plane_layer._world_to_displayed_data_ray(
        np.asarray(event.view_direction), dims_displayed
    )

    intersection = plane_layer.plane.intersect_with_line(
        line_position=position[dims_displayed], line_direction=direction
    )
    if not point_in_bounding_box(
        intersection, plane_layer.extent.data[:, dims_displayed]
    ):
        return None

    # the dimensions the plane layer does not have keep the position of the event
    position[dims_displayed] = intersection
    world_position = np.asarray(event.position, dtype=float)
    world_position[-plane_layer.ndim :] = plane_layer.data_to_world(position)
    return world_position


class PlaneSliderWidget(QWidget):
    """Widget implementing sliders for 3D plane and 3D clipping plane visualization"""

    def __init__(
        self,
        viewer: napari.Viewer,
        link_group: Callable[[], list] | None = None,
    ):
        """
        Args:
            viewer (napari.Viewer): the viewer whose layers the controls act on.
            link_group (Callable, optional): returns the layers that share the plane
                controls, e.g. the tracking layers. An image layer can join them with
                the 'Link image' row. Only the plane, depiction and clipping planes are
                shared, not e.g. visibility or colormap. Without it, the controls act
                on the selected layer alone and the row is hidden.
        """

        super().__init__()

        self.viewer = viewer
        self._link_group = link_group if link_group is not None else list
        self.linked_images = []
        self.viewer.dims.events.ndisplay.connect(self._update_view_mode)
        self.viewer.layers.selection.events.changed.connect(self._on_selection_changed)

        # snap the reported cursor position to the plane, before any other callback reads it
        self.viewer.mouse_move_callbacks.insert(0, self._snap_cursor_to_plane)
        self.viewer.mouse_drag_callbacks.insert(0, self._snap_cursor_to_plane)
        self.viewer.mouse_double_click_callbacks.insert(0, self._snap_cursor_to_plane)

        self.mode = "slice"
        self.current_layer = None

        ### Widget layout
        self.setStyleSheet("QPushButton { padding: 2px 6px; }")

        # Buttons to switch between plane, clipping plane and volume mode. They
        # switch the viewer to 3D, which is the only display these modes apply to.
        self.plane_btn = QPushButton("Plane")
        self.plane_btn.setToolTip("Show a single plane through the volume")
        self.clipping_plane_btn = QPushButton("Clipping plane")
        self.clipping_plane_btn.setToolTip(
            "Show the volume between two parallel clipping planes"
        )
        self.volume_btn = QPushButton("Volume")
        self.volume_btn.setToolTip("Show the full volume")
        self._mode_buttons = {
            "plane": self.plane_btn,
            "clipping_plane": self.clipping_plane_btn,
            "volume": self.volume_btn,
        }
        for mode, button in self._mode_buttons.items():
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, mode=mode: self._set_mode(mode))

        # Buttons for the different viewing directions of the plane normal
        orientation_buttons = []
        for text, normal in (
            ("X", (0, 0, 1)),
            ("Y", (0, 1, 0)),
            ("Z", (1, 0, 0)),
            ("Oblique", None),
        ):
            button = QPushButton(text)
            button.clicked.connect(
                lambda _checked, normal=normal: self._set_orientation(normal)
            )
            orientation_buttons.append(button)
        orientation_buttons[-1].setToolTip(
            "Orient the plane along the current viewing direction"
        )
        self.orientation_widget = create_compact_qwidget(
            QLabel("Normal"), *orientation_buttons
        )

        # Single slider for plane position
        self.plane_slider = QLabeledSlider(QtCore.Qt.Horizontal)
        self.plane_slider.setSingleStep(1)
        self.plane_slider.valueChanged.connect(self._set_plane)

        # Snapping of the reported position and of new points to the plane
        self.snap_checkbox = QCheckBox("Snap to plane")
        self.snap_checkbox.setChecked(True)
        self.snap_checkbox.setToolTip(
            "Snap mouse position to the plane and place points added to a linked\n"
            "points layer on the plane"
        )
        self.snap_checkbox.toggled.connect(self._update_point_snapping)

        # Thickness of the slab that linked layers without a plane (e.g. Points) are clipped to
        self.slab_thickness_box = QSpinBox()
        self.slab_thickness_box.setRange(1, 1000)
        self.slab_thickness_box.setValue(5)
        self.slab_thickness_box.valueChanged.connect(self._update_linked_slab)
        slab_label = QLabel("Slab")
        self.slab_widget = create_compact_qwidget(slab_label, self.slab_thickness_box)
        self.slab_widget.setToolTip(
            "Thickness of the slab around the plane in which linked layers\n"
            "without a plane of their own (e.g. Points) are shown"
        )
        self.slab_widget.setVisible(False)

        # Assemble plane widget items
        self.plane_widget = QWidget()
        plane_layout = QVBoxLayout(self.plane_widget)
        plane_layout.setContentsMargins(0, 0, 0, 0)
        plane_layout.setSpacing(2)
        plane_layout.addWidget(
            create_compact_qwidget(QLabel("Position"), self.plane_slider)
        )
        plane_layout.addWidget(
            create_compact_qwidget(self.snap_checkbox, None, self.slab_widget)
        )

        # Range slider for clipping planes
        self.clipping_plane_slider = QLabeledRangeSlider(QtCore.Qt.Horizontal)
        self.clipping_plane_slider.setValue((0, 1))
        self.clipping_plane_slider.setSingleStep(1)
        self.clipping_plane_slider.valueChanged.connect(self._set_clipping_plane)
        self.clipping_plane_widget = create_compact_qwidget(self.clipping_plane_slider)

        # Image layer linked to the plane controls of the link group.
        # follow_active=False: the dropdown only changes when the user picks a layer
        self.link_dropdown = LayerDropdown(
            self.viewer,
            (Image,),
            follow_active=False,
            layer_filter=self._can_link,
            layer_icon=self._link_marker,
        )
        self.link_dropdown.setToolTip(
            "Image layers with the same shape as the layers to link to.\n"
            "Linked layers are marked with a chain."
        )
        self.link_dropdown.layer_changed.connect(self._on_link_layer_changed)
        self.link_btn = QPushButton()
        self.link_btn.setCheckable(True)
        self.link_btn.setToolTip(
            "Link or unlink the image layer picked in the dropdown to the plane controls.\n"
            "Only the plane, its depiction and the clipping planes are shared, not e.g.\n"
            "the visibility or opacity."
        )
        self.link_btn.toggled.connect(self._on_link_toggled)
        self._set_link_icon(linked=False)
        self.link_widget = create_compact_qwidget(
            QLabel("Link image"), self.link_dropdown, self.link_btn
        )
        self.link_widget.setVisible(link_group is not None)
        # the layers to link to can be replaced, which changes which images match
        self.viewer.layers.events.inserted.connect(self._update_link_options)
        self.viewer.layers.events.removed.connect(self._update_link_options)

        # Final layout
        self.mode_widget = create_compact_qwidget(*self._mode_buttons.values())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self.link_widget)
        layout.addWidget(self.mode_widget)
        layout.addWidget(self.orientation_widget)
        layout.addWidget(self.plane_widget)
        layout.addWidget(self.clipping_plane_widget)
        layout.addStretch()

        # Set initial mode
        self._set_mode("slice")

        # the controls only become active once a layer is selected
        self._set_controls_enabled(False)
        self._update_link_options()
        self._on_selection_changed()

    def cleanup(self) -> None:
        """Take the widget back off the viewer and its layers.

        The widget installs callbacks and event connections on the viewer itself, which
        would outlive it and raise when they touch its deleted Qt children. Without
        this, a reopened menu leaves the callbacks of the previous one behind.
        """

        with contextlib.suppress(TypeError, RuntimeError, ValueError):
            self.viewer.dims.events.ndisplay.disconnect(self._update_view_mode)
        with contextlib.suppress(TypeError, RuntimeError, ValueError):
            self.viewer.layers.selection.events.changed.disconnect(
                self._on_selection_changed
            )
        for emitter in (
            self.viewer.layers.events.inserted,
            self.viewer.layers.events.removed,
        ):
            with contextlib.suppress(TypeError, RuntimeError, ValueError):
                emitter.disconnect(self._update_link_options)

        for callbacks in (
            self.viewer.mouse_move_callbacks,
            self.viewer.mouse_drag_callbacks,
            self.viewer.mouse_double_click_callbacks,
        ):
            with contextlib.suppress(ValueError):
                callbacks.remove(self._snap_cursor_to_plane)

        for layer in self.viewer.layers:
            if hasattr(layer, "plane"):
                with contextlib.suppress(TypeError, RuntimeError, ValueError):
                    layer.events.plane.disconnect(self._update_plane_slider)
                with contextlib.suppress(TypeError, RuntimeError, ValueError):
                    layer.events.depiction.disconnect(self._update_view_mode)

            # restore the napari callback on any points layer whose add mode we took over
            if not isinstance(layer, Points):
                continue
            with contextlib.suppress(TypeError, RuntimeError, ValueError):
                layer.events.mode.disconnect(self._on_point_mode_changed)
            if self._add_point_on_plane in layer.mouse_drag_callbacks:
                layer.mouse_drag_callbacks.remove(self._add_point_on_plane)
                if str(layer.mode) == "add":
                    layer.mouse_drag_callbacks.append(napari_add_point)

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable the plane controls, the link row stays usable without a selection"""

        for widget in (
            self.mode_widget,
            self.orientation_widget,
            self.plane_widget,
            self.clipping_plane_widget,
        ):
            widget.setEnabled(enabled)

    def _link_reference(self):
        """The layer of the link group whose plane a linked image takes on, e.g. the
        segmentation. None if no layer in the group has a plane.
        """

        return next(
            (layer for layer in self._link_group() if hasattr(layer, "plane")), None
        )

    def _can_link(self, layer) -> bool:
        """Whether an image layer can be linked to the link group: it must have the
        shape of the layer in the group that has a plane, if there is one.
        """

        group = self._link_group()
        if not group or layer in group:
            return False
        reference = self._link_reference()
        if reference is not None:
            return tuple(layer.data.shape) == tuple(reference.data.shape)
        return layer.ndim >= 3

    def _set_link_icon(self, linked: bool) -> None:
        """Show a broken chain while linked (click to unlink), a chain otherwise."""

        icon = FA6S.link_slash if linked else FA6S.link
        self.link_btn.setIcon(qticon(icon, color="white"))

    def _link_marker(self, layer):
        """Mark the linked images in the dropdown with a chain"""

        if layer in self.linked_images:
            return qticon(FA6S.link, color="white")
        return None

    def _update_link_options(self, *_args) -> None:
        """List the image layers that match the (new) link group, and unlink the linked
        images that were removed or no longer match.
        """

        for image in list(self.linked_images):
            if image not in self.viewer.layers or not self._can_link(image):
                self._unlink_image(image)
        self.link_dropdown.refresh()
        self._on_link_layer_changed()

    def _on_link_layer_changed(self, *_args) -> None:
        """Show on the chain button whether the image picked in the dropdown is linked"""

        selected = self.link_dropdown.selected_layer
        linked = selected is not None and selected in self.linked_images
        with silenced(self.link_btn):
            self.link_btn.setChecked(linked)
        self._set_link_icon(linked=linked)
        self.link_btn.setEnabled(selected is not None)

    def _on_link_toggled(self, checked: bool) -> None:
        """Link the image picked in the dropdown to the plane controls, or unlink it."""

        image = self.link_dropdown.selected_layer
        if image is None:
            return
        if checked:
            self._link_image(image)
        else:
            self._unlink_image(image)
        # update the markers
        self.link_dropdown.refresh()
        self._on_link_layer_changed()

    def _link_image(self, image) -> None:
        """Let an image share the plane controls of the link group

        The image takes on the plane view of the group, so the group keeps showing the
        same plane instead of taking on the view of the image.
        """

        if image in self.linked_images:
            return
        self.linked_images.append(image)
        reference = self._link_reference()
        if reference is not None:
            self._adopt_plane(image, reference)
        self._update_group()

    def _unlink_image(self, image) -> None:
        """Release a linked image and return it to a plain volume, without clipping"""

        if image not in self.linked_images:
            return
        self.linked_images.remove(image)

        # the image may have been the layer the sliders followed
        with contextlib.suppress(TypeError, RuntimeError, ValueError):
            image.events.plane.disconnect(self._update_plane_slider)
        with contextlib.suppress(TypeError, RuntimeError, ValueError):
            image.events.depiction.disconnect(self._update_view_mode)

        if image in self.viewer.layers:
            image.depiction = "volume"
            for clip_plane in image.experimental_clipping_planes:
                clip_plane.enabled = False

        # derive the mode again, the image may be the selected layer
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        """Update the active layer"""

        if (
            len(self.viewer.layers.selection) == 1
        ):  # Only consider single layer selection
            selected_layer = self.viewer.layers.selection.active
            if isinstance(selected_layer, Labels | Image | Points):
                self.current_layer = selected_layer
            else:
                self.current_layer = None
            self._set_controls_enabled(self.current_layer is not None)
            if self.current_layer is None:
                return

            self._ensure_clipping_planes(self.current_layer)

            # a layer without a plane of its own can still drive the plane of a
            # layer it is linked to
            plane_layer = self._plane_layer()
            self.plane_btn.setVisible(plane_layer is not None)
            if plane_layer is not None:
                plane_layer.events.plane.connect(self._update_plane_slider)
                plane_layer.events.depiction.connect(self._update_view_mode)

            self._update_point_snapping()
            self._update_view_mode()
            self._update_linked_slab()

    def _ensure_clipping_planes(self, layer) -> None:
        """Give a layer the pair of clipping planes this widget operates on"""

        if len(layer.experimental_clipping_planes) != 0:
            return

        if hasattr(layer, "plane"):
            normal, position = layer.plane.normal, layer.plane.position
        else:
            # layers without a plane follow the orientation shown in the widget
            normal, position = self._plane_normal(), (0, 0, 0)

        layer.experimental_clipping_planes.append(
            ClippingPlane(normal=normal, position=position, enabled=False)
        )
        layer.experimental_clipping_planes.append(
            ClippingPlane(normal=[-n for n in normal], position=position, enabled=False)
        )

    def _group_of(self, layer) -> list:
        """The layer followed by the other layers that share its plane controls

        These are the layers of the link group plus the linked images, if the layer is
        one of them. The link group comes first, so that a layer without a plane (e.g.
        Points) keeps borrowing the plane of the segmentation when images are linked.
        """

        group = [
            other
            for other in (*self._link_group(), *self.linked_images)
            if other in self.viewer.layers
        ]
        if layer not in group:
            return [layer]
        return [layer, *(other for other in group if other is not layer)]

    def _linked_layers(self) -> list:
        """The layers that share the plane controls with the current layer"""

        if self.current_layer is None:
            return []
        return self._group_of(self.current_layer)[1:]

    def _update_group(self) -> None:
        """Apply the current mode to the group of the current layer again, after layers
        joined or left the plane group
        """

        mode = self.mode
        self._on_selection_changed()
        if mode != "slice" and self.mode != mode:
            self._set_mode(mode)

    def _adopt_plane(self, layer, source) -> None:
        """Give a layer that joins the group of source the plane, depiction and clipping
        planes of source, so that the group keeps its view instead of taking on the one
        of the new layer.
        """

        self._ensure_clipping_planes(layer)
        self._ensure_clipping_planes(source)
        if hasattr(layer, "plane") and hasattr(source, "plane"):
            layer.plane.normal = source.plane.normal
            layer.plane.position = source.plane.position
            layer.depiction = source.depiction
        for target, clip_plane in zip(
            layer.experimental_clipping_planes[:2],
            source.experimental_clipping_planes[:2],
            strict=False,
        ):
            target.normal = clip_plane.normal
            target.position = clip_plane.position
            target.enabled = clip_plane.enabled
        self._refresh(layer)

    def _target_layers(self) -> list:
        """The layers to apply clipping plane changes to: the current layer and the layers it is linked to"""

        if self.current_layer is None:
            return []

        layers = [self.current_layer, *self._linked_layers()]
        for layer in layers:
            self._ensure_clipping_planes(layer)
        return layers

    @staticmethod
    def _refresh(layer) -> None:
        """Redraw a layer whose visual does not update itself when the clipping planes change (e.g. Points)"""

        if not isinstance(layer, Image | Labels):
            layer.events.set_data()

    def _update_linked_layers(self) -> None:
        """Let the linked layers follow the plane of the current layer"""

        self._sync_linked_planes()
        self._update_linked_slab()
        self._update_point_snapping()

    def _snap_cursor_to_plane(self, viewer, event) -> None:
        """Report the position on the plane while a plane is shown, instead of where the
        click ray enters the data.
        """

        layer = self.viewer.layers.selection.active
        plane_layer = None if layer is None else self._plane_layer_for(layer)
        if plane_layer is None:
            return

        position = plane_click_position(plane_layer, event)
        if position is not None:
            viewer.cursor.position = tuple(position)

    def _plane_layer(self):
        """The layer whose plane the plane controls act on.

        A layer without a plane of its own, such as a points layer, falls back to a
        layer it is linked to, so that the plane can be moved while the points layer
        stays selected.
        """

        if self.current_layer is None:
            return None
        if hasattr(self.current_layer, "plane"):
            return self.current_layer

        for layer in self._linked_layers():
            if hasattr(layer, "plane") and layer.visible and layer.ndim >= 3:
                return layer
        return None

    def _plane_layer_for(self, layer):
        """The plane that positions on this layer snap to: its own, or that of a linked layer

        Snapping only applies while the plane is shown, in 3D, and is switched on.
        """

        if not self.snap_checkbox.isChecked() or self.viewer.dims.ndisplay != 3:
            return None

        for other in self._group_of(layer):
            if (
                getattr(other, "depiction", None) == "plane"
                and other.visible
                and other.ndim >= 3
            ):
                return other
        return None

    def _update_point_snapping(self) -> None:
        """Snap points added to a linked points layer onto the plane of the current layer"""

        for layer in self._target_layers():
            if not isinstance(layer, Points):
                continue
            layer.events.mode.connect(self._on_point_mode_changed)
            self._update_point_add_callback(layer)

    def _on_point_mode_changed(self, event) -> None:
        """napari restores its own callbacks whenever the mode of a layer changes"""

        self._update_point_add_callback(event.source)

    def _update_point_add_callback(self, layer) -> None:
        """Replace the callback that adds points while snapping applies"""

        callbacks = layer.mouse_drag_callbacks
        snapping = str(layer.mode) == "add" and self._plane_layer_for(layer) is not None

        if snapping:
            if napari_add_point in callbacks:
                callbacks.remove(napari_add_point)
            if self._add_point_on_plane not in callbacks:
                callbacks.append(self._add_point_on_plane)
        elif self._add_point_on_plane in callbacks:
            callbacks.remove(self._add_point_on_plane)
            if str(layer.mode) == "add" and napari_add_point not in callbacks:
                callbacks.append(napari_add_point)

    def _add_point_on_plane(self, layer, event):
        """Add a point where the click crosses the plane of the linked layer

        Same click and drag handling as the napari callback, but the point is placed
        on the plane. A click that does not land on the plane adds no point, rather
        than one somewhere along the line of sight.
        """

        plane_layer = self._plane_layer_for(layer)
        if plane_layer is None:
            yield from napari_add_point(layer, event)
            return

        start_pos = event.pos
        yield

        while event.type == "mouse_move":
            if np.linalg.norm(start_pos - event.pos) < DRAG_DIST_THRESHOLD:
                # prevent vispy from moving the canvas if below threshold
                event.handled = True
            yield

        if np.linalg.norm(start_pos - event.pos) >= DRAG_DIST_THRESHOLD:
            return

        position = plane_click_position(plane_layer, event)
        if position is not None:
            layer.add(layer.world_to_data(position))

    def _sync_linked_planes(self) -> None:
        """Copy the plane the widget acts on to the other layers in the group that have
        one, e.g. from the segmentation to the linked image
        """

        plane_layer = self._plane_layer()
        if plane_layer is None:
            return

        plane = plane_layer.plane
        for layer in self._linked_layers():
            if layer is plane_layer or not hasattr(layer, "plane"):
                continue

            # only the layer the widget acts on drives the sliders
            layer.events.plane.disconnect(self._update_plane_slider)
            layer.plane.normal = plane.normal
            layer.plane.position = plane.position

    def _update_linked_slab(self) -> None:
        """Clip the layers in the group that have no plane to a slab around the plane

        This lets layers such as Points mimic plane mode: they only show the points
        within `slab_thickness_box` slices of the plane of the image or labels layer
        they are linked to.
        """

        # only offer a slab thickness when a layer in the group has no plane of its own
        plane_layer = self._plane_layer()
        layers = [
            layer for layer in self._target_layers() if not hasattr(layer, "plane")
        ]
        self.slab_widget.setVisible(plane_layer is not None and bool(layers))
        if self.mode != "plane" or plane_layer is None:
            return

        normal = np.array(plane_layer.plane.normal)
        center = offset_along(plane_layer.plane.position, normal)
        half_thickness = self.slab_thickness_box.value() / 2

        for layer in layers:
            layer.experimental_clipping_planes[0].normal = normal
            layer.experimental_clipping_planes[1].normal = tuple(-n for n in normal)
            layer.experimental_clipping_planes[0].position = tuple(
                (center - half_thickness) * normal
            )
            layer.experimental_clipping_planes[1].position = tuple(
                (center + half_thickness) * normal
            )
            for clip_plane in layer.experimental_clipping_planes:
                clip_plane.enabled = True
            self._refresh(layer)

    def _plane_normal(self) -> np.ndarray:
        """Normal of the plane, or of the first clipping plane if there is no plane"""

        plane_layer = self._plane_layer()
        if plane_layer is not None:
            return np.array(plane_layer.plane.normal)
        if len(self.current_layer.experimental_clipping_planes) > 0:
            return np.array(self.current_layer.experimental_clipping_planes[0].normal)
        return np.array([1.0, 0.0, 0.0])

    def _layer_bounds(self):
        """Lower and upper corner of the bounding box of the current layer and its linked
        layers, excluding layers without data.
        """

        extents = [
            layer.extent.data[:, -3:]
            for layer in self._target_layers()
            if layer.extent.data.shape[1] >= 3
            and np.all(np.isfinite(layer.extent.data[:, -3:]))
        ]
        if not extents:
            return np.zeros(3), np.ones(3)

        extents = np.array(extents)
        return extents[:, 0].min(axis=0), extents[:, 1].max(axis=0)

    def _update_view_mode(self, event=None) -> None:
        """Restore the mode from the display and from the depiction and clipping planes of
        the group, after switching layers or display, or changing the depiction elsewhere
        """

        if self.viewer.dims.ndisplay != 3:
            self._set_mode("slice")
            return
        if self.current_layer is None:
            return

        plane_layer = self._plane_layer()
        if plane_layer is not None and plane_layer.depiction == "plane":
            self._set_mode("plane")
        elif (
            (plane_layer or self.current_layer).experimental_clipping_planes[0].enabled
        ):
            self._set_mode("clipping_plane")
        else:
            self._set_mode("volume")

    def compute_plane_range(self) -> tuple[int, int]:
        """Range of the sliders: the extent of the bounding box of the group along the normal"""

        corners = np.array(
            list(itertools.product(*zip(*self._layer_bounds(), strict=True)))
        )
        projections = corners @ self._plane_normal()
        return int(projections.min()), int(projections.max())

    def _set_orientation(self, normal=None) -> None:
        """Orient the plane and clipping planes along a normal, and center the sliders

        Without a normal, the plane is oriented along the viewing direction (oblique).
        """

        if self.current_layer is None:
            return

        plane_layer = self._plane_layer()
        if normal is None:
            normal = (plane_layer or self.current_layer)._world_to_displayed_data_ray(
                self.viewer.camera.view_direction, [-3, -2, -1]
            )

        if plane_layer is not None:
            plane_layer.plane.normal = normal
        for layer in self._target_layers():
            layer.experimental_clipping_planes[0].normal = normal
            layer.experimental_clipping_planes[1].normal = tuple(-n for n in normal)

        low, high = self.compute_plane_range()
        span = high - low
        with silenced(self.plane_slider):
            self.plane_slider.setRange(low, high)
            self.plane_slider.setValue(low + span // 2)
        with silenced(self.clipping_plane_slider):
            self.clipping_plane_slider.setRange(low, high)
            self.clipping_plane_slider.setValue((low + span // 3, low + 2 * span // 3))

        # apply explicitly, the slider values may not have changed with the normal
        self._set_plane()
        self._set_clipping_plane()
        self._update_linked_layers()

    def _set_depiction(self, depiction: str) -> None:
        """Set the depiction of the layers in the group that have one, without triggering the sync callback"""

        plane_layer = self._plane_layer()
        if plane_layer is None:
            # nothing in the group shows a plane, so there is no depiction to set
            return

        for layer in self._target_layers():
            # napari emits even when the depiction does not change, which would
            # needlessly redraw the layer and re-trigger mode updates
            if getattr(layer, "depiction", depiction) == depiction:
                continue
            # only the layer the widget acts on drives the sliders
            layer.events.depiction.disconnect(self._update_view_mode)
            layer.depiction = depiction

        plane_layer.events.depiction.connect(self._update_view_mode)
        self._update_point_snapping()

    def _update_plane_slider(self):
        """Updates the value of the plane slider when the user used the shift+drag method to shift the plane or when switching between different layers"""

        plane_layer = self._plane_layer()
        if plane_layer is None:
            return

        with silenced(self.plane_slider):
            self.plane_slider.setValue(
                int(offset_along(plane_layer.plane.position, plane_layer.plane.normal))
            )

        self._update_linked_layers()

    def _set_mode(self, mode: str) -> None:
        """Switch to 'slice' (2D display), 'plane', 'clipping_plane' or 'volume' mode

        The plane modes only apply in 3D, so the viewer switches to 3D for them.
        """

        if mode != "slice":
            if self.current_layer is None:
                return
            if self.viewer.dims.ndisplay != 3:
                # restores the mode stored on the layers, which is replaced below
                self.viewer.dims.ndisplay = 3

        self.mode = mode
        for button_mode, button in self._mode_buttons.items():
            button.setChecked(button_mode == mode)
        self.orientation_widget.setVisible(mode in ("plane", "clipping_plane"))
        self.plane_widget.setVisible(mode == "plane")
        self.clipping_plane_widget.setVisible(mode == "clipping_plane")
        if mode == "slice":
            return

        self._set_depiction("plane" if mode == "plane" else "volume")
        self._enable_clipping_planes(mode == "clipping_plane")
        if mode == "volume":
            return

        low, high = self.compute_plane_range()
        span = high - low

        if mode == "plane":
            with silenced(self.plane_slider):
                self.plane_slider.setRange(low, high)
            # restore the plane position that is stored on the layer
            self._update_plane_slider()
            if self.plane_slider.value() == 0:
                self.plane_slider.setValue(low + span // 2)
            return

        # restore the clipping plane positions that are stored on the layer, both
        # expressed along the normal of the first plane, which faces inwards
        planes = self.current_layer.experimental_clipping_planes
        with silenced(self.clipping_plane_slider):
            self.clipping_plane_slider.setRange(low, high)
            self.clipping_plane_slider.setValue(
                tuple(
                    int(offset_along(plane.position, planes[0].normal))
                    for plane in planes[:2]
                )
            )
            lower, upper = self.clipping_plane_slider.value()
            if lower >= upper:  # nothing meaningful stored yet
                self.clipping_plane_slider.setValue(
                    (low + span // 3, low + 2 * span // 3)
                )
        # (re-)apply, also in case a layer was linked since the positions were set
        self._set_clipping_plane()

    def _enable_clipping_planes(self, enabled: bool) -> None:
        """Enable or disable the clipping planes of the current layer and of the layers linked to it"""

        for layer in self._target_layers():
            if enabled and getattr(layer, "depiction", None) == "plane":
                continue  # this layer is showing a plane, it should not be clipped
            for clip_plane in layer.experimental_clipping_planes:
                clip_plane.enabled = enabled
            self._refresh(layer)

    def _dims_steps(self) -> np.ndarray:
        """Step size of the last three dimensions of the viewer

        Falls back to a step of one for a viewer that does not have three dimensions
        yet, for instance when the only layer is an empty points layer.
        """

        ranges = self.viewer.dims.range
        if len(ranges) < 3:
            return np.ones(3)
        return np.array([axis.step for axis in ranges[-3:]])

    def _set_clipping_plane(self) -> None:
        """Adjust the range of the clipping plane"""

        if self.current_layer is None:
            return

        normal = np.array(self.current_layer.experimental_clipping_planes[0].normal)
        steps = self._dims_steps()
        lower, upper = self.clipping_plane_slider.value()

        for layer in self._target_layers():
            layer.experimental_clipping_planes[0].position = tuple(
                lower * normal * steps
            )
            layer.experimental_clipping_planes[1].position = tuple(
                upper * normal * steps
            )
            self._refresh(layer)

    def _set_plane(self) -> None:
        """Move the plane to a new location"""

        plane_layer = self._plane_layer()
        if plane_layer is not None:
            plane_layer.plane.position = tuple(
                self.plane_slider.value() * np.array(plane_layer.plane.normal)
            )
