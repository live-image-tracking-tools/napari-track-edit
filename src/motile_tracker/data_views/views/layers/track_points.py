from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING

import napari
import numpy as np
from funtracks.data_model import Tracks
from funtracks.exceptions import InvalidActionError
from funtracks.user_actions import UserAddNode, UserDeleteNodes, UserUpdateNodesAttrs
from napari.layers.points._points_mouse_bindings import select
from napari.utils.notifications import show_info
from psygnal import Signal
from psygnal.containers import Selection

from motile_tracker.data_views.keybindings_config import (
    KEYMAP,
    bind_keymap,
)
from motile_tracker.data_views.node_type import NodeType
from motile_tracker.data_views.views.layers.click_utils import (
    detect_click,
    detect_side_button,
    get_click_value,
)
from motile_tracker.data_views.views_coordinator.user_dialogs import (
    confirm_force_operation,
)

if TYPE_CHECKING:
    from napari.utils.events import Event

    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

from motile_tracker.data_views.views.layers.out_of_slice_points import ZOnlyPoints


def custom_select(layer: napari.layers.Points, event: Event):
    """Block the current_size signal when selecting points to avoid changing the point
    size by accident."""

    with layer.events.current_size.blocker():
        yield from select(layer, event)


class TrackPoints(ZOnlyPoints):
    """Extended points layer that holds the track information and emits and
    responds to dynamics visualization signals
    """

    # overwrite the select function to block the current_size event signal
    _drag_modes = napari.layers.Points._drag_modes.copy()
    _drag_modes[napari.layers.Points._modeclass.SELECT] = custom_select
    data_updated = Signal()

    @property
    def _type_string(self) -> str:
        return "points"  # to make sure that the layer is treated as points layer for saving

    def __init__(
        self,
        name: str,
        tracks_viewer: TracksViewer,
    ):
        self.tracks_viewer = tracks_viewer
        self.nodes = tracks_viewer.tracks.graph.node_ids()
        self.node_index_dict = {node: idx for idx, node in enumerate(self.nodes)}

        if len(self.nodes) > 0:
            points = self.tracks_viewer.tracks.get_positions(self.nodes, incl_time=True)
        else:
            points = np.empty((0, self.tracks_viewer.tracks.ndim))

        track_ids = self.tracks_viewer.tracks.get_track_ids(self.nodes)
        colors = self._map_track_colors(track_ids)
        symbols = self.get_symbols(
            self.tracks_viewer.tracks, self.tracks_viewer.symbolmap
        )

        self.default_size = 5

        super().__init__(
            data=points,
            name=name,
            symbol=symbols,
            face_color=colors,
            size=self.default_size,
            properties={
                "node_id": self.nodes,
                "track_id": track_ids,
            },  # TODO: use features
            border_color=[1, 1, 1, 1],
            blending="translucent",
        )

        # Key bindings (should be specified both on the viewer (in tracks_viewer)
        bind_keymap(self, KEYMAP, self.tracks_viewer)

        # Connect to click events to select nodes
        @self.mouse_drag_callbacks.append
        def click(layer, event):
            side_button = detect_side_button(event)
            if side_button is not None:
                self.process_click(event, side_button=side_button)
            elif event.type == "mouse_press" and self.mode == "pan_zoom":
                was_click = yield from detect_click(event)
                if was_click:
                    # find the point matching the click location, if any. Warning: the
                    # search area depends on the point size. If points are large and
                    # overlapping, this may result in the wrong value being returned.
                    point_index = get_click_value(self, event)
                    self.process_click(event, value=point_index)

        # listen to updates of the data
        self.events.data.connect(self._update_data)

        # connect to changing the point size in the UI (see note)
        self.events.current_size.connect(
            lambda: self.set_point_size(size=self.current_size)
        )

        # listen to updates in the selected data (from the point selection tool)
        # to update the nodes in self.tracks_viewer.selected_nodes
        self.selected_data.events.items_changed.connect(self._update_selection)

    def add(self, coords: list[float]):
        """Block the current_size event before calling the 'add' function to avoid calling
        set_point_size (triggered by the current_size event) with a new point size."""

        with self.events.current_size.blocker():
            super().add(coords)

    @property
    def selected_data(self) -> Selection[int]:
        """Set of currently selected point indices."""

        return napari.layers.Points.selected_data.fget(self)

    @selected_data.setter
    def selected_data(self, selected_data) -> None:
        """Block the current_size event while changing the selection, so that the point
        size will not accumulate size increases when selecting points.
        """

        with self.events.current_size.blocker():
            napari.layers.Points.selected_data.fset(self, selected_data)

    def process_click(
        self,
        event: Event,
        value: int | None = None,
        side_button: int | None = None,
        layer: napari.layers.Points | None = None,
    ):
        """Select the clicked point(s)

        Args:
            event (Event): The mouse event
            value (int | None): The index of the clicked point, or None if no point
                was clicked
            side_button (int | None): the button index (4: back, 5: forward) if a mouse side button was used, or None if no side button was used.
            layer (napari.layers.Points | None): Optional, unused. The (ortho view) layer on which the click occurred, which is forwarded by default.
        """

        # Intercept mouse side button navigation (back/forward)
        if side_button is not None:
            self.tracks_viewer.select_node_set_from_history(previous=side_button == 4)
            return

        if value is None:
            self.tracks_viewer.selected_nodes.reset()
        else:
            node_id = self.nodes[value]
            append = "Shift" in event.modifiers
            jump = "Control" in event.modifiers
            if jump:
                self.tracks_viewer.center_on_node(node_id)
            else:
                self.tracks_viewer.selected_nodes.add(node_id, append)

    def set_point_size(self, size: int) -> None:
        """Sets a new default point size.

        NOTE: This function call is triggered by the current_size event, which is emitted
        when the user moves the 'point size' slider in the layer controls. However, this
        event is also emitted in the 'add' and 'select' functions, so we have to block the
        signals there to avoid increasing the point size by accident, since new or
        selected points are displayed at a 30% bigger size.
        """

        self.default_size = size
        self._refresh()

    def _refresh(self):
        """Refresh the data in the points layer"""

        self.events.data.disconnect(
            self._update_data
        )  # do not listen to new events until updates are complete
        self.nodes = self.tracks_viewer.tracks.graph.node_ids()

        self.node_index_dict = {node: idx for idx, node in enumerate(self.nodes)}

        track_ids = self.tracks_viewer.tracks.get_track_ids(self.nodes)
        self.data = self.tracks_viewer.tracks.get_positions(self.nodes, incl_time=True)
        self.data_updated.emit()  # emit update signal for the orthogonal views to connect to

        self.symbol = self.get_symbols(
            self.tracks_viewer.tracks, self.tracks_viewer.symbolmap
        )
        self.face_color = self._map_track_colors(track_ids)
        self.properties = {"node_id": self.nodes, "track_id": track_ids}
        self.size = self.default_size
        self.border_color = [1, 1, 1, 1]

        self.events.data.connect(
            self._update_data
        )  # reconnect listening to update events

    def _create_node_attrs(self, new_point: np.array) -> tuple[np.array, dict]:
        """Create attributes for a new node at given time point"""

        t = int(new_point[0])

        # Activate a new track_id if necessary
        if self.tracks_viewer.selected_track is None:
            self.tracks_viewer.set_new_track_id()

        # take the track_id of the selected track (funtracks will check that there is no
        # node with this track_id at this time point yet, and assign a new one otherwise.)
        track_id = self.tracks_viewer.selected_track

        features = self.tracks_viewer.tracks.features
        attributes = {
            features.position_key: new_point[1:],
            features.time_key: t,
            features.tracklet_key: track_id,
        }
        return attributes

    def _update_data(self, event: Event):
        """Calls the UserActions to update the data in the Tracks object and
        dispatch the update
        """

        if event.action == "added":
            # we only want to allow this update if there is no seg layer
            if self.tracks_viewer.tracking_layers.seg_layer is None:
                new_point = event.value[-1]
                attributes = self._create_node_attrs(new_point)
                try:
                    with self.tracks_viewer.center_node.blocked():
                        new_node_id = self.tracks_viewer.tracks._get_new_node_ids(1)[0]
                        UserAddNode(
                            self.tracks_viewer.tracks,
                            node=new_node_id,
                            attributes=attributes,
                            force=self.tracks_viewer.force,
                        )

                except InvalidActionError as e:
                    if e.forceable:
                        # If the action is invalid but forceable, ask the user if they want to do so
                        force, always_force = confirm_force_operation(message=str(e))
                        self.tracks_viewer.force = always_force
                        self._refresh()
                        if force:
                            new_node_id = self.tracks_viewer.tracks._get_new_node_ids(
                                1
                            )[0]
                            UserAddNode(
                                self.tracks_viewer.tracks,
                                node=new_node_id,
                                attributes=attributes,
                                force=True,
                            )
                    else:
                        warnings.warn(str(e), stacklevel=2)
                        self._refresh()
            else:
                show_info(
                    "Mixed point and segmentation nodes not allowed: add points by "
                    "drawing on segmentation layer"
                )
                self._refresh()

        elif event.action == "removed":
            UserDeleteNodes(
                self.tracks_viewer.tracks,
                nodes=self.tracks_viewer.selected_nodes.as_list,
            )

        elif event.action == "changed":
            # we only want to allow this update if there is no seg layer
            if self.tracks_viewer.tracking_layers.seg_layer is None:
                position_key = self.tracks_viewer.tracks.features.position_key
                nodes = [
                    int(self.properties["node_id"][ind]) for ind in self.selected_data
                ]
                attrs = {
                    position_key: [self.data[ind][1:] for ind in self.selected_data]
                }

                UserUpdateNodesAttrs(
                    self.tracks_viewer.tracks,
                    nodes=nodes,
                    attrs=attrs,
                )

            else:
                self._refresh()  # refresh to move points back where they belong

    def _update_selection(self):
        """Replaces the list of selected_nodes with the selection provided by the user"""

        if self.mode == "select":
            selected_points = self.selected_data
            self.tracks_viewer.selected_nodes.reset()
            for point in selected_points:
                node_id = self.nodes[point]
                self.tracks_viewer.selected_nodes.add(node_id, True)

    def _map_track_colors(self, track_ids: list[int]) -> np.ndarray:
        """Map track ids to an (N, 4) array of face colors in a single colormap call.

        colormap.map has a large fixed per-call overhead (cache lookup, dtype, reshape),
        so mapping the whole array at once is ~290x faster than calling it per node (or
        even once per unique track id): for ~37k nodes / 142 unique ids, ~1ms vs ~300ms.

        With no nodes (an empty tracks graph, e.g. when tracking from scratch) a single
        white color is returned instead of a (0, 4) array: napari's ColorManager treats
        the color argument as *the* current color when the layer holds no data, and
        feeding it an empty array raises in `transform_color`.
        """
        if len(track_ids) == 0:
            return np.ones((1, 4))
        return self.tracks_viewer.colormap.map(np.asarray(track_ids))

    def get_symbols(self, tracks: Tracks, symbolmap: dict[NodeType, str]) -> list[str]:
        statemap = {
            0: NodeType.END,
            1: NodeType.CONTINUE,
            2: NodeType.SPLIT,
        }
        symbols = [
            symbolmap[statemap[degree]]
            for degree in tracks.graph.out_degree(self.nodes)
        ]
        return symbols

    def update_point_outline(self, visible_nodes: list[int] | str) -> None:
        """Update the outline color of the selected points and visibility according to
        display mode

        Args:
            visible_nodes (list[int] | str): A list of node ids, or "all"
        """

        if isinstance(visible_nodes, str):
            self.shown[:] = True
        else:
            # For lineage or group mode, visible_nodes is a list of node IDs
            # In group mode, also include selected nodes so they remain visible
            if self.tracks_viewer.mode == "group":
                visible_nodes = (
                    list(visible_nodes) + self.tracks_viewer.selected_nodes.as_list
                )
            indices = np.where(np.isin(self.properties["node_id"], visible_nodes))[
                0
            ].tolist()
            self.shown[:] = False
            self.shown[indices] = True

        n_points = len(self.data)
        if n_points == 0:
            # nothing to style, and napari warns when assigning empty color arrays
            self.refresh()
            return

        # Set border color and size for the selected items. Both are built up first and
        # then assigned once, because every assignment emits an event that the orthogonal
        # views (if present) answer by re-slicing their copy of this layer.
        border_colors = np.tile([1.0, 1.0, 1.0, 1.0], (n_points, 1))
        sizes = np.full(n_points, self.default_size)
        selected_size = math.ceil(self.default_size + 0.3 * self.default_size)
        for node in self.tracks_viewer.selected_nodes:
            index = self.node_index_dict.get(node, None)
            if index is not None:
                border_colors[index] = (
                    0,
                    1,
                    1,
                    1,
                )
                sizes[index] = selected_size

        # size first: the orthogonal views read it when the border color event arrives
        self.size = sizes
        self.border_color = border_colors
        self.refresh()
