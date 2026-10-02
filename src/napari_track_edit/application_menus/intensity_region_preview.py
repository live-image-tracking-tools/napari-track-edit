from __future__ import annotations

import napari
import numpy as np
from napari.components import Dims
from napari_orthogonal_views.ortho_view_manager import _VIEWER_MANAGERS
from psygnal import Signal

from napari_track_edit.data_views.views.layers.out_of_slice_points import (
    _HAS_SIZE_BASED_OUT_OF_SLICE,
    ZOnlyPoints,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


class IntensityRegionPreview:
    """Outlines the disk (2D) or sphere (3D) that point intensity is measured in.

    A points layer with one point per node, sized to the previewed diameter. Points
    are in world units, like the diameter, so each point covers the measured region.

    The layer automatically applies out-of-slice display (napari < 0.9) or thick slicing
    (napari >= 0.9) to display the preview across slices. The display settings are
    restored when the preview is hidden.

    Args:
        viewer: The viewer to show the preview in.
        tracks_viewer: Holds the tracks whose points are previewed.
    """

    LAYER_NAME = "Intensity region preview"

    # emitted when the user deletes the preview layer
    removed = Signal()

    def __init__(self, viewer: napari.Viewer, tracks_viewer: TracksViewer):
        self.viewer = viewer
        self.tracks_viewer = tracks_viewer
        self.layer: napari.layers.Points | None = None
        self.diameter: float | None = None
        # Display settings changed to show the preview, restored when it is hidden:
        # id -> (image layer, its projection mode) and id -> (dims, its margins)
        self._saved_projection: dict[int, tuple[napari.layers.Image, str]] = {}
        self._saved_margins: dict[int, tuple[Dims, tuple, tuple]] = {}

        self.viewer.layers.events.removed.connect(self._on_layer_removed)

    @property
    def is_shown(self) -> bool:
        return self.layer is not None

    def show(self, diameter: float) -> None:
        """Show the preview with the given diameter, or update it if it is shown.

        Args:
            diameter: The diameter of the region, in world units.
        """

        self.diameter = diameter
        if self.layer is None:
            if not self._has_point_intensity():
                return
            self.layer = self.viewer.add_layer(self._create_layer())
        else:
            self.refresh()
        self._thicken_slices()

    def refresh(self) -> None:
        """Follow the nodes, after they were added, moved or deleted."""

        if self.layer is None:
            return
        if not self._has_point_intensity():
            self.hide()
            return
        self.layer.data = self._data()
        self.layer.size = self.diameter
        self.layer.events.size()  # emit event for ortho views

    def hide(self) -> None:
        """Remove the preview layer and restore the display settings."""

        layer, self.layer = self.layer, None
        if layer is not None and layer in self.viewer.layers:
            self.viewer.layers.remove(layer)
        self._restore_slices()

    def _has_point_intensity(self) -> bool:
        tracks = self.tracks_viewer.tracks
        return tracks is not None and tracks.point_intensity_annotator is not None

    def _data(self) -> np.ndarray:
        """The (t, [z], y, x) positions of the nodes in the solution."""

        tracks = self.tracks_viewer.tracks
        nodes = list(tracks.graph_solution.node_ids())
        if not nodes:
            return np.empty((0, tracks.ndim))
        return tracks.get_positions(nodes, incl_time=True)

    def _create_layer(self) -> napari.layers.Points:
        layer = ZOnlyPoints(
            self._data(),
            name=self.LAYER_NAME,
            size=self.diameter,
            face_color="transparent",
            border_color="yellow",
            border_width=0.05,
            blending="translucent",
        )
        if _HAS_SIZE_BASED_OUT_OF_SLICE:
            # older napari: shrink each point away from its center plane, along z
            layer.out_of_slice_display = True
        else:
            # shrink each point within the thick slice, as a sphere's cross-section
            layer.projection_mode = "rescale_spherical"
        layer.editable = False
        return layer

    def _sliced_dims(self) -> list[Dims]:
        """The dims of the main viewer and of the orthogonal views, if shown."""

        dims = [self.viewer.dims]
        manager = _VIEWER_MANAGERS.get(self.viewer)
        if manager is not None and manager.is_shown():
            dims += [
                widget.vm_container.viewer_model.dims
                for widget in (manager.right_widget, manager.bottom_widget)
            ]
        return dims

    def _thicken_slices(self) -> None:
        """Show each previewed sphere in every slice it crosses (napari >= 0.9).

        Slices along the spatial axes that are not displayed are made at least the
        sphere radius thick in either direction, in the main viewer and in the
        orthogonal views. Image layers are kept to a single plane.
        """

        if _HAS_SIZE_BASED_OUT_OF_SLICE:
            return  # out_of_slice_display does this on older napari

        for layer in self.viewer.layers:
            if (
                isinstance(layer, napari.layers.Image)
                and layer.projection_mode != "none"
            ):
                self._saved_projection.setdefault(
                    id(layer), (layer, layer.projection_mode)
                )
                layer.projection_mode = "none"

        radius = self.diameter / 2
        num_spatial = self.tracks_viewer.tracks.ndim - 1
        for dims in self._sliced_dims():
            spatial = range(dims.ndim - num_spatial, dims.ndim)
            axes = [axis for axis in spatial if axis in dims.not_displayed]
            left, right = list(dims.margin_left), list(dims.margin_right)
            if all(left[a] >= radius and right[a] >= radius for a in axes):
                continue
            self._saved_margins.setdefault(
                id(dims), (dims, dims.margin_left, dims.margin_right)
            )
            for axis in axes:
                left[axis] = max(left[axis], radius)
                right[axis] = max(right[axis], radius)
            dims.margin_left = tuple(left)
            dims.margin_right = tuple(right)

    def _restore_slices(self) -> None:
        """Undo the display changes made for the preview."""

        for layer, mode in self._saved_projection.values():
            if layer in self.viewer.layers:
                layer.projection_mode = mode
        for dims, left, right in self._saved_margins.values():
            dims.margin_left = left
            dims.margin_right = right
        self._saved_projection.clear()
        self._saved_margins.clear()

    def _on_layer_removed(self, event=None) -> None:
        """Notice the user deleting the preview layer."""

        if self.layer is not None and self.layer not in self.viewer.layers:
            self.layer = None
            self._restore_slices()
            self.removed.emit()
