from __future__ import annotations

import random
import warnings
from typing import TYPE_CHECKING

import napari
import numpy as np
from funtracks.exceptions import InvalidActionError
from funtracks.user_actions import UserUpdateSegmentation
from napari.layers import Labels
from napari.utils import DirectLabelColormap
from napari.utils.action_manager import action_manager
from napari.utils.notifications import show_info

from motile_tracker.data_views.keybindings_config import (
    KEYMAP,
    bind_keymap,
)
from motile_tracker.data_views.views.layers.click_utils import (
    detect_click,
    detect_side_button,
    get_click_value,
)
from motile_tracker.data_views.views.layers.contour_labels import ContourLabels
from motile_tracker.data_views.views_coordinator.user_dialogs import (
    confirm_force_operation,
)

if TYPE_CHECKING:
    from napari.utils.events import Event

    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


def new_label(layer: TrackLabels):
    """A function to override the default napari labels new_label function.
    Must be registered (see end of this file)"""

    layer.events.selected_label.disconnect(layer._ensure_valid_label)
    _new_label(layer, new_track_id=True)
    layer.events.selected_label.connect(layer._ensure_valid_label)


def _new_label(layer: TrackLabels, new_track_id=True):
    """A function to get a new label for a given TrackLabels layer. Should properly
    go on the class, but needs to be registered to override the default napari function
    in the action manager. This helper is abstracted out because we want to do the same
    thing without making a new track id in the layer, and with the new track id in the
    overriden action.

    Args:
        layer (TrackLabels): A TrackLabels layer from which get a new label for drawing a
            new segmentation. Updates the selected_label attribute.
        new_track_id (bool, optional): If you should also generate a new track id and set
            it to the selected_track attribute. Defaults to True.
    """

    new_selected_label = max(layer.tracks_viewer.tracks.graph.node_ids(), default=0) + 1
    if new_track_id or layer.tracks_viewer.selected_track is None:
        layer.tracks_viewer.set_new_track_id()
    layer.selected_label = new_selected_label
    layer.colormap.color_dict[new_selected_label] = layer.tracks_viewer.track_id_color
    # to refresh, otherwise you paint with a transparent label until you
    # release the mouse
    with layer.events.selected_label.blocker():
        layer.colormap = DirectLabelColormap(color_dict=layer.colormap.color_dict)


class TrackLabels(ContourLabels):
    """Extended labels layer that holds the track information and emits
    and responds to dynamics visualization signals"""

    @property
    def _type_string(self) -> str:
        return "labels"  # to make sure that the layer is treated as labels layer for saving

    def __init__(
        self,
        viewer: napari.Viewer,
        data: np.array,
        name: str,
        opacity: float,
        scale: tuple,
        tracks_viewer: TracksViewer,
    ):
        self.tracks_viewer = tracks_viewer
        colormap = self._get_colormap()

        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            colormap=colormap,
            scale=scale,
        )

        self.viewer = viewer
        self.highlight_opacity = 1
        self.foreground_opacity = 0.6
        self.background_opacity = 0.3
        self.highlight_contour = False
        self.foreground_contour = False

        # Key bindings (should be specified both on the viewer (in tracks_viewer)
        bind_keymap(self, KEYMAP, self.tracks_viewer)

        # Listen to paint events and changing the selected label
        self.mouse_drag_callbacks.append(self.click)
        self.events.paint.connect(self._on_paint)
        self.tracks_viewer.node_selection_updated.connect(self.update_selected_label)
        self.events.mode.connect(self._check_mode)
        self.events.selected_label.connect(self._ensure_valid_label)

        # listen to changing the contours
        self.events.contour.connect(self.tracks_viewer.mode_updated.emit)

    # Connect click events to node selection
    def click(self, _, event):
        side_button = detect_side_button(event)
        if side_button is not None:
            self.process_click(event, side_button=side_button)
        elif self.mode == "pan_zoom" and event.type == "mouse_press":
            # disable selecting in lineage mode in 3D
            # differentiate between click and drag
            was_click = yield from detect_click(event)
            if was_click:
                value = get_click_value(self, event)
                self.process_click(event, value=value)

    def assign_new_label(self, event):
        """Function for orthoviews to connect to so the 'm' event can be processed here"""

        new_label(self)

    def process_click(
        self,
        event: Event,
        value: int | None = None,
        side_button: int | None = None,
        layer: ContourLabels | None = None,
    ):
        """Process the click event to update the selected nodes.

        Args:
            event (Event): The click event.
            value (int): The label value (node) at the clicked position.
            side_button (int | None): the integer for the mouse side buttons (4: back, 5: forward)
            layer (ContourLabels | None): The (ortho view) layer from which the click originated.
                If provided, it is used to check label visibility in that layer's colormap.
        """

        # Intercept mouse side button navigation (back/forward)
        if side_button is not None:
            self.tracks_viewer.select_node_set_from_history(previous=side_button == 4)
            return

        if value is not None and value != 0:
            # check visibility in the respective colormap. If a label is not visible, it
            # is not allowed to be selected from this view
            if layer is not None:
                is_visible = layer.colormap.color_dict.get(value)[3] > 0
            else:
                is_visible = self.colormap.color_dict.get(value)[3] > 0
            if is_visible:
                append = "Shift" in event.modifiers
                jump = "Control" in event.modifiers
                if jump:
                    self.tracks_viewer.center_on_node(value)
                else:
                    self.tracks_viewer.selected_nodes.add(int(value), append)
            else:
                warnings.warn(
                    f"Node {value} is not visible in this view and cannot be selected.",
                    stacklevel=2,
                )

    def _get_colormap(self) -> DirectLabelColormap:
        """Get a DirectLabelColormap that maps node ids to their track ids, and then
        uses the tracks_viewer.colormap to map from track_id to color.

        Returns:
            DirectLabelColormap: A map from node ids to colors based on track id
        """
        tracks = self.tracks_viewer.tracks
        if tracks is not None:
            nodes = tracks.graph.node_ids()
            track_ids = tracks.get_track_ids(nodes)
            # One vectorized colormap.map call for all nodes: colormap.map has a
            # large fixed per-call overhead (cache lookup, dtype, reshape), so a
            # single array call is ~290x faster than calling it per node (or even
            # once per unique track id). The result is an (N, 4) array with a
            # distinct row per node, so copy per node to get independent color
            # arrays: set_opacity later mutates each color's alpha in place.
            if len(track_ids) > 0:
                mapped = self.tracks_viewer.colormap.map(np.asarray(track_ids))
                colors = [color.copy() for color in mapped]
            else:
                colors = []
        else:
            nodes = []
            colors = []
        return DirectLabelColormap(
            color_dict={
                **dict(zip(nodes, colors, strict=True)),
                None: [0, 0, 0, 0],
            }
        )

    def _check_mode(self):
        """Check if the mode is valid and call the ensure_valid_label function"""
        # here disconnecting the event listener is still necessary because
        # self.mode = paint triggers the event internally and it is not blocked with
        # event.blocker()
        self.events.mode.disconnect(self._check_mode)
        if self.mode == "polygon":
            show_info("Please use the paint tool to update the label")
            self.mode = "paint"

        self.events.mode.connect(self._check_mode)

    def redo(self):
        """Overwrite the redo functionality of the labels layer and invoke redo action on
        the tracks_viewer.tracks first
        """

        self.tracks_viewer.redo()

    def undo(self):
        """Overwrite undo function and invoke undo action on the
        tracks_viewer.tracks first
        """

        self.tracks_viewer.undo()

    def _parse_paint_event(self, event_val):
        """_summary_

        Args:
            event_val (list[tuple]): A list of paint "atoms" generated by the labels
                layer. Each atom is a 3-tuple of arrays containing:
                - a numpy multi-index, pointing to the array elements that were
                changed (a tuple with len ndims)
                - the values corresponding to those elements before the change
                - the value after the change
        Returns:
            tuple(int, list[tuple]): The new value, and a list of node update actions
                defined by the time point and node update item
                Each "action" is a 2-tuple containing:
                - a numpy multi-index, pointing to the array elements that were
                changed (a tuple with len ndims)
                - the value before the change
        """

        new_value = event_val[-1][-1]
        ndim = len(event_val[-1][0])
        concatenated_indices = tuple(
            np.concatenate([ev[0][dim] for ev in event_val]) for dim in range(ndim)
        )
        concatenated_values = np.concatenate([ev[1] for ev in event_val])
        old_values = np.unique(concatenated_values)
        actions = []
        for old_value in old_values:
            mask = concatenated_values == old_value
            indices = tuple(concatenated_indices[dim][mask] for dim in range(ndim))
            time_points = np.unique(indices[0])
            for time_point in time_points:
                time_mask = indices[0] == time_point
                actions.append(
                    (
                        tuple(indices[dim][time_mask] for dim in range(ndim)),
                        int(old_value),
                    )
                )
        return new_value, actions

    def _revert_paint(self, _, source_layer: Labels | None = None):
        """Revert a paint event after it fails validation (no motile tracker Actions have
        been created). This keeps the view synced with the backend data.
        been created). If a source_layer is provided, the paint event will be reverted on
        this layer (this is necessary for orthoviews). This keeps the view synced with
        the backend data.
        """
        if source_layer is not None:
            source_layer.undo()  # revert on the orthoview
        else:
            super().undo()

    def _on_paint(self, event):
        """Listen to the paint event and check which track_ids have changed"""

        # make sure that 0 (in the case or erasing) or a valid label (in the case of
        # painting) is selected.
        if (
            self.mode == "erase"
            or (self.mode == "fill" and self.selected_label == 0)
            or (self.mode == "paint" and self.selected_label == 0)
        ):
            target_value = 0
        else:
            self._ensure_valid_label()
            target_value = self.selected_label

        with self.events.selected_label.blocker():
            try:
                _, updated_pixels = self._parse_paint_event(event.value)
                UserUpdateSegmentation(
                    tracks=self.tracks_viewer.tracks,
                    new_value=target_value,
                    updated_pixels=updated_pixels,
                    current_track_id=self.tracks_viewer.selected_track,
                    force=self.tracks_viewer.force,
                )  # paint with the updated self.selected_label, not with the value from the
                # event, to ensure it is a valid label.
            except InvalidActionError as e:
                if e.forceable:
                    # If the action is invalid, ask the user if they want to force it anyway
                    force, always_force = confirm_force_operation(message=str(e))
                    self.tracks_viewer.force = always_force
                    super().undo()
                    if not force:
                        self._refresh()  # to trigger refresh on orthoviews, if present
                    else:
                        # try again with force enabled
                        UserUpdateSegmentation(
                            tracks=self.tracks_viewer.tracks,
                            new_value=target_value,
                            updated_pixels=updated_pixels,
                            current_track_id=self.tracks_viewer.selected_track,
                            force=True,
                        )
                else:
                    warnings.warn(str(e), stacklevel=2)
                    super().undo()
                    self._refresh()

    def _refresh(self):
        """Refresh the data in the labels layer"""
        self.data = self.tracks_viewer.tracks.segmentation
        self.colormap = self._get_colormap()
        self.refresh()

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity for the highlighted, foreground, and background labels,
        and adds labels to the filled_labels if necessary.
        """

        highlighted = set(self.tracks_viewer.selected_nodes)
        foreground = self.colormap.color_dict.keys() if visible == "all" else visible
        self.background = (
            []
            if visible == "all"
            else self.colormap.color_dict.keys() - visible - highlighted
        )

        self.filled_labels = []
        if self.contour > 0 and visible != "all":
            if not self.highlight_contour:
                self.filled_labels.extend(highlighted)
            if not self.foreground_contour:
                self.filled_labels.extend(foreground)

        # special case: 3D rendering + partially filled contours -> set background opacity
        # to 0
        if self._slice.slice_input.ndisplay == 3 and self.contour > 0:
            self.set_opacity(self.background, 0)
        else:
            # set normal background opacity
            self.set_opacity(self.background, self.background_opacity)
        self.set_opacity(foreground, self.foreground_opacity)
        self.set_opacity(highlighted, self.highlight_opacity)
        self.refresh_colormap()

    def new_colormap(self):
        """Override existing function to generate new colormap on tracks_viewer and
        emit refresh signal to update colors in all layers/widgets"""

        self.tracks_viewer.colormap = napari.utils.colormaps.label_colormap(
            random.randint(49, 69),
            seed=random.uniform(0, 1),
            background_value=0,
        )
        self.tracks_viewer._refresh()

    def update_selected_label(self):
        """Update the selected label in the labels layer"""

        if len(self.tracks_viewer.selected_nodes) > 0:
            node = int(self.tracks_viewer.selected_nodes[0])
            self.selected_label = node
            self.tracks_viewer.selected_track = int(
                self.tracks_viewer.tracks.get_track_id(node)
            )

    def _ensure_valid_label(self, event: Event | None = None):
        """Make sure a valid label is selected, because it is not allowed to paint with
        a label that already exists at a different timepoint.

        Scenarios:

        1. If a node with the selected label value (node id) exists at a different time
           point, check if there is any node with the same track_id at the current time
           point.

           a. If there is a node with the same track id, select that one, so that it
              can be used to update an existing node.
           b. If there is no node with the same track id, create a new node id and
              paint with the track_id of the selected label. This can be used to add a
              new node with the same track id at a time point where it does not (yet)
              exist (anymore).

        2. If there is no existing node with this value in the graph, it is assumed that
           you want to add a node with the current track id. Retrieve the track_id from
           self.current_track_id and use it to find if there are any nodes of this track
           id at current time point.

        3. If no node with this label exists yet, it is valid and can be used to start a
           new track id. Therefore, create a new node id and map a new color. Add it to
           the dictionary.

        4. If a node with the label exists at the current time point, it is valid and
           can be used to update the existing node in a paint event. No action is needed.
        """

        # The background label is never a valid label to paint a node with (painting
        # with it erases), so it should never get a track id or a color. napari binds
        # "X" on Labels layers to swap_selected_and_background_labels, which sets
        # selected_label to the background value: without this guard, that would give
        # the background an opaque color and make the whole segmentation background
        # render in the track color (see issue #493).
        if self.selected_label == self.colormap.background_value:
            return

        update_colormap = False
        if self.tracks_viewer.tracks is not None:
            current_timepoint = self.viewer.dims.current_step[0]
            # if a node with the given label is already in the graph
            if self.tracks_viewer.tracks.graph.has_node(self.selected_label):
                # Update the track id
                self.tracks_viewer.selected_track = (
                    self.tracks_viewer.tracks.get_track_id(self.selected_label)
                )
                existing_time = self.tracks_viewer.tracks.get_time(self.selected_label)
                if existing_time == current_timepoint:
                    # we are changing the existing node. This is fine
                    pass
                else:
                    # if there is already a node in that track in this frame, edit that
                    # instead
                    edit = False
                    if (
                        self.tracks_viewer.selected_track
                        in self.tracks_viewer.tracks.track_id_to_node
                    ):
                        for node in self.tracks_viewer.tracks.track_id_to_node[
                            self.tracks_viewer.selected_track
                        ]:
                            if (
                                self.tracks_viewer.tracks.get_time(node)
                                == current_timepoint
                            ):
                                self.selected_label = int(node)
                                edit = True
                                break

                    if not edit:
                        # use a new label, but the same track id
                        _new_label(self, new_track_id=False)

            # the current node does not exist in the graph.
            # Use the current selected_track as the track id (will be a new track if a
            # new label was found with "m")
            # Check that the track id is not already in this frame.
            else:
                # if there is already a node in that track in this frame, edit that
                # instead
                if (
                    self.tracks_viewer.selected_track
                    in self.tracks_viewer.tracks.track_id_to_node
                ):
                    for node in self.tracks_viewer.tracks.track_id_to_node[
                        self.tracks_viewer.selected_track
                    ]:
                        if (
                            self.tracks_viewer.tracks.get_time(node)
                            == current_timepoint
                        ):
                            self.selected_label = int(node)
                            break

                elif self.tracks_viewer.selected_track is None:
                    self.tracks_viewer.selected_track = (
                        self.tracks_viewer.tracks.get_next_track_id()
                    )
                    update_colormap = True

        # update color and emit signal
        self.tracks_viewer.set_track_id_color(self.tracks_viewer.selected_track)
        if update_colormap:
            self.colormap.color_dict[self.selected_label] = (
                self.tracks_viewer.track_id_color
            )
            with self.events.selected_label.blocker():
                self.colormap = DirectLabelColormap(
                    color_dict=self.colormap.color_dict
                )  # refresh
        self.tracks_viewer.update_track_id.emit()

    @napari.layers.Labels.n_edit_dimensions.setter
    def n_edit_dimensions(self, n_edit_dimensions):
        # Overriding the setter to disable editing in time dimension
        if n_edit_dimensions > self.tracks_viewer.tracks.ndim - 1:
            n_edit_dimensions = self.tracks_viewer.tracks.ndim - 1
        self._n_edit_dimensions = n_edit_dimensions
        self.events.n_edit_dimensions()


# This is to override the default napari function to get a new label for the labels layer
action_manager.register_action(
    name="napari:new_label",
    command=new_label,
    keymapprovider=TrackLabels,
    description="",
)
TrackLabels.bind_key("m", overwrite=True)(new_label)
