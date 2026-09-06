from __future__ import annotations

from typing import TYPE_CHECKING

import napari
from funtracks.data_model import Tracks
from napari.experimental import link_layers, unlink_layers

from motile_tracker.data_views.views.layers.track_graph import TrackGraph
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views.layers.track_points import TrackPoints

if TYPE_CHECKING:
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TracksLayerGroup:
    def __init__(
        self,
        viewer: napari.Viewer,
        tracks: Tracks,
        name: str,
        tracks_viewer: TracksViewer,
    ):
        self.viewer = viewer
        self.tracks_viewer = tracks_viewer
        self.tracks = tracks
        self.name = name
        self.tracks_layer: TrackGraph | None = None
        self.points_layer: TrackPoints | None = None
        self.seg_layer: TrackLabels | None = None

    def set_tracks(self, tracks, name):
        self.remove_napari_layers()
        self.tracks = tracks
        self.name = name
        # Create new layers
        if self.tracks is not None and self.tracks.segmentation is not None:
            self.seg_layer = TrackLabels(
                viewer=self.viewer,
                data=self.tracks.segmentation,
                name=self.name + "_seg",
                opacity=0.9,
                scale=self.tracks.scale,
                tracks_viewer=self.tracks_viewer,
            )
        else:
            self.seg_layer = None

        if self.tracks is not None and self.tracks.graph is not None:
            self.tracks_layer = TrackGraph(
                name=self.name + "_tracks",
                tracks_viewer=self.tracks_viewer,
            )

            self.points_layer = TrackPoints(
                name=self.name + "_points",
                tracks_viewer=self.tracks_viewer,
            )
        else:
            self.tracks_layer = None
            self.points_layer = None
        self.add_napari_layers()

    def remove_napari_layer(self, layer: napari.layers.Layer | None) -> None:
        """Remove a layer from the napari viewer, if present"""
        if layer and layer in self.viewer.layers:
            self.viewer.layers.remove(layer)

    def remove_napari_layers(self) -> None:
        """Remove all tracking layers from the viewer"""
        self.remove_napari_layer(self.tracks_layer)
        self.remove_napari_layer(self.seg_layer)
        self.remove_napari_layer(self.points_layer)

    def add_napari_layers(self) -> None:
        """Add new tracking layers to the viewer"""

        if self.tracks_layer is not None:
            self.viewer.add_layer(self.tracks_layer)
        if self.points_layer is not None:
            self.viewer.add_layer(self.points_layer)
        if self.seg_layer is not None:
            self.viewer.add_layer(self.seg_layer)

        # self.link_experimental_clipping_planes()

    def link_experimental_clipping_planes(self):
        """Link the clipping planes of all tracking layers"""

        track_layers = []
        if self.tracks_layer is not None:
            track_layers.append(self.tracks_layer)
        if self.seg_layer is not None:
            track_layers.append(self.seg_layer)
        if self.points_layer is not None:
            track_layers.append(self.points_layer)

        if all(layer.ndim >= 3 for layer in track_layers):
            link_layers(track_layers, ("experimental_clipping_planes",))

    def unlink_experimental_clipping_planes(self):
        """Unlink the clipping planes of all tracking layers"""

        track_layers = []
        if self.tracks_layer is not None:
            track_layers.append(self.tracks_layer)
        if self.seg_layer is not None:
            track_layers.append(self.seg_layer)
        if self.points_layer is not None:
            track_layers.append(self.points_layer)
        unlink_layers(track_layers, ("experimental_clipping_planes",))

    def _refresh(self) -> None:
        """Refresh the tracking layers with new tracks info"""
        if self.tracks_layer is not None:
            self.tracks_layer._refresh()
        if self.seg_layer is not None:
            self.seg_layer._refresh()
        if self.points_layer is not None:
            self.points_layer._refresh()

    def update_visible(self, visible_nodes: list[int] | str):
        if self.seg_layer is not None:
            self.seg_layer.update_label_colormap(visible_nodes)
        if self.points_layer is not None:
            self.points_layer.update_point_outline(visible_nodes)
        if self.tracks_layer is not None:
            # Convert node IDs to track IDs for the tracks layer
            if isinstance(visible_nodes, str):
                visible_tracks = visible_nodes  # "all"
            else:
                # visible_nodes is a small subset — use per-node lookup, not bulk batch
                visible_tracks = list(
                    {self.tracks.get_track_id(node) for node in visible_nodes}
                )
            self.tracks_layer.update_track_visibility(visible_tracks)

    def center_view(self, node):
        """Adjust the current_step and camera center of the viewer to jump to the node
        location, if the node is not already in the field of view"""

        if self.seg_layer is None or self.seg_layer.mode == "pan_zoom":
            location = self.tracks.get_position(node, incl_time=True)
            assert len(location) == self.viewer.dims.ndim, (
                f"Location {location} does not match viewer number of dims "
                f"{self.viewer.dims.ndim}"
            )

            # Set dims.point directly with world coordinates - napari will
            # automatically convert to the correct step indices
            self.viewer.dims.point = location

            # check whether the new coordinates are inside or outside the field of view,
            # then adjust the camera if needed
            example_layer = (
                self.points_layer
            )  # the points layer is always in world units,
            # because it directly reads the scaled coordinates. Therefore, no rescaling
            # is necessary to compute the camera center
            corner_coordinates = example_layer.corner_pixels

            # check which dimensions are shown, the first dimension is displayed on the
            # x axis, and the second on the y_axis
            dims_displayed = self.viewer.dims.displayed

            # Note: This centering does not work in 3D. What we should do instead is take
            # the view direction vector, start at the point, and move backward along the
            # vector a certain amount to put the point in view.
            # Note #2: Points already does centering when you add the first point, and it
            # works in 3D. We can look at that to see what logic they use.

            # self.viewer.dims.displayed_order
            x_dim = dims_displayed[-1]
            y_dim = dims_displayed[-2]

            # find corner pixels for the displayed axes
            _min_x = corner_coordinates[0][x_dim]
            _max_x = corner_coordinates[1][x_dim]
            _min_y = corner_coordinates[0][y_dim]
            _max_y = corner_coordinates[1][y_dim]

            # check whether the node location falls within the corner spatial range
            if not (
                (location[x_dim] > _min_x and location[x_dim] < _max_x)
                and (location[y_dim] > _min_y and location[y_dim] < _max_y)
            ):
                camera_center = self.viewer.camera.center

                # set the center y and x to the center of the node, by using the index
                # of the currently displayed dimensions
                self.viewer.camera.center = (
                    camera_center[0],
                    location[y_dim],
                    # camera center is calculated in scaled coordinates, and the optional
                    # labels layer is scaled by the layer.scale attribute
                    location[x_dim],
                )
