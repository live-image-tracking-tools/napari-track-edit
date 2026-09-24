from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

import napari
import pandas as pd
from funtracks.actions import AddNode, BasicAction, DeleteNode
from funtracks.data_model import Tracks
from funtracks.exceptions import InvalidActionError
from funtracks.user_actions import (
    UserConnectNodes,
    UserDeleteNodes,
    UserDisconnectNodes,
    UserMergeNodes,
    UserSetDivision,
    UserSwapPredecessors,
    is_connected_chain,
    get_track_id_options,
)
from psygnal import Signal
from qtpy.QtWidgets import QMessageBox

from motile_tracker.data_views.dims_utils import TracksDims
from motile_tracker.data_views.keybindings_config import (
    KEYMAP,
    bind_keymap,
)
from motile_tracker.data_views.node_type import NodeType
from motile_tracker.data_views.views.layers.tracks_layer_group import TracksLayerGroup
from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_lineage_tree,
    extract_sorted_tracks,
)
from motile_tracker.data_views.views_coordinator.groups import (
    CollectionWidget,
)
from motile_tracker.data_views.views_coordinator.node_selection_history import (
    NodeSelectionHistory,
)
from motile_tracker.data_views.views_coordinator.tracks_list import TracksList
from motile_tracker.data_views.views_coordinator.user_dialogs import (
    ask_connect_mode,
    confirm_force_operation,
    select_merge_track_id,
)

BASE_TEXT = (
    "Click : select node\n"
    "Shift + Click : add to selection\n"
    "Ctrl (/CMD) + Click : center node\n"
    "Alt (/Option) + Click : pick tracklet ID\n"
    "[Q] : toggle display\n"
    "\n"
    "Current display mode : "
)


class TracksViewer:
    """Purposes of the TracksViewer:

    - Emit signals that all widgets should use to update selection or update
      the currently displayed Tracks object
    - Storing the currently displayed tracks
    - Store shared rendering information like colormaps (or symbol maps)
    """

    tracks_updated = Signal(Optional[bool])  # noqa: UP007 UP045
    update_track_id = Signal()
    mode_updated = Signal()
    center_node = Signal(int)  # emitted when any component wants to center on a node
    node_selection_updated = Signal(bool)

    @classmethod
    def get_instance(cls, viewer=None):
        if not hasattr(cls, "_instance") or (
            viewer is not None and cls._instance.viewer is not viewer
        ):
            if viewer is None:
                raise ValueError("Make a viewer first please!")
            # The outgoing instance is about to become unreachable, but psygnal
            # connections keep it subscribed to its tracks object. Unsubscribe it,
            # or a tracks object shown in successive viewers ends up notifying
            # every TracksViewer ever built (see _disconnect_tracks).
            if hasattr(cls, "_instance"):
                cls._instance._disconnect_tracks()
            cls._instance = TracksViewer(viewer)
        return cls._instance

    def __init__(
        self,
        viewer: napari.Viewer,
    ):
        self.viewer = viewer
        self.viewer.mouse_double_click_callbacks.clear()  # no double click to zoom
        self.menu_manager = None  # will be set by MenuManager after initialization
        self.tree_widget_present = False
        self.table_widget_present = False

        def _clear_if_current():
            self._disconnect_tracks()
            if hasattr(TracksViewer, "_instance") and TracksViewer._instance is self:
                del TracksViewer._instance

        viewer.window._qt_window.destroyed.connect(_clear_if_current)
        self.colormap = napari.utils.colormaps.label_colormap(
            49,
            seed=0.5,
            background_value=0,
        )

        self.symbolmap: dict[NodeType, str] = {
            NodeType.END: "x",
            NodeType.CONTINUE: "disc",
            NodeType.SPLIT: "triangle_up",
        }
        self.mode = "all"
        self.tracks: Tracks | None = None
        self.visible: list | str = []
        self.tracking_layers = TracksLayerGroup(self.viewer, self.tracks, "", self)
        self.center_node.connect(self.tracking_layers.center_view)
        self.selected_nodes = NodeSelectionHistory()
        self.selected_nodes.selection_updated.connect(self.update_selection)

        self.track_df = pd.DataFrame()  # initialize empty dataframe
        self.axis_order: list[int] = []

        self.tracks_list = TracksList()
        self.tracks_list.view_tracks.connect(self.update_tracks)
        self.tracks_list.tracks_cleared.connect(self.clear_tracks)
        self.tracks_list.request_colormap.connect(self.set_colormap_to_trackslist)
        self.selected_track = None
        self.track_id_color = [0, 0, 0, 0]
        self.force = False
        # True while an interaction in the napari canvas (a click or a paint event) is
        # being processed, so that centering requests know where they came from (see
        # viewer_interaction and TracksLayerGroup.center_view)
        self.interacting_with_canvas = False

        self.collection_widget = None

        self.set_keybinds()

        self.viewer.dims.events.ndisplay.connect(self.update_selection)

    @property
    def tracks_dims(self) -> TracksDims:
        """How the tracks' axes sit compared to the viewer's world axes.

        Raises:
            RuntimeError: If no tracks are loaded.
        """

        if self.tracks is None:
            raise RuntimeError("No tracks are loaded, so they have no dimensions")
        return TracksDims(self.viewer.dims.ndim, self.tracks.ndim)

    def set_axis_labels(self) -> None:
        """Name the viewer's sliders after the axes the tracks use."""

        if self.tracks is None:
            return

        dims = self.tracks_dims
        labels = list(self.viewer.dims.axis_labels)
        # any 'extra' dims just keep the name they had already
        labels[dims.ndim_offset :] = ["t", *self.tracks.axis_names]
        self.viewer.dims.axis_labels = labels

    def get_collection_widget(self) -> CollectionWidget:
        """Return a reference to the groups widget"""
        if self.collection_widget is None or getattr(
            self.collection_widget, "_is_deleted", False
        ):
            self.collection_widget = CollectionWidget(self)
            if self.tracks is not None:
                self.collection_widget.retrieve_existing_groups()

            # track destruction
            self.collection_widget.destroyed.connect(
                lambda: self._on_collection_widget_destroyed()
            )

        return self.collection_widget

    def _on_collection_widget_destroyed(self):
        self.collection_widget = None

    def set_colormap_to_trackslist(self):
        """Set the current colormap on the TracksList, so that it can be exported."""
        self.tracks_list.colormap = self.colormap

    def set_keybinds(self):
        bind_keymap(self.viewer, KEYMAP, self)

    def request_new_track(self, event=None) -> None:
        """Request a new track id (with new segmentation label if a seg layer is present)"""

        if self.tracks is None:
            return
        if self.tracking_layers.seg_layer is not None:
            self.tracking_layers.seg_layer.new_label()
        else:
            self.set_new_track_id()

    def set_new_track_id(self) -> None:
        """Set a new track id (if needed), update the color, and emit signal. Only updates
        the track id if the tracks.max_track_id value is used already."""

        self.selected_track = self.tracks.max_track_id  # to check if available
        if (
            self.selected_track in self.tracks.track_id_to_node
            or self.selected_track == 0
        ):
            self.selected_track = self.tracks.get_next_track_id()
        self.set_track_id_color(self.selected_track)
        self.update_track_id.emit()

    def set_track_id_color(self, track_id: int) -> None:
        """Update self.track_id color with the rgba color or given track_id, or a list of
        0 if the provided  track_id is None"""

        self.track_id_color = (
            [0, 0, 0, 0] if track_id is None else self.colormap.map(track_id)
        )

    def update_track_df(
        self, initialization: bool | None = False, refresh_view: bool | None = False
    ) -> None:
        """Create or update the pandas dataframe used by the TreeWidget and TableWidget.

        The track_df should be updated when:

        - a tree or table widget is being initialized (initialization=True) and no
          tree or table widget exists yet
        - a normal update event happens (initialization = False) AND a tree widget
          and/or table widget exists on menu_manager

        Args:
            initialization (bool | None = False): whether or not this is called by a tree
                or table widget that is initializing.
            refresh_view (bool | None = False): whether or not we should not pass on the
                previous axis_order. Should be False if we want to use the previous axis
                order (current tracks got updated). Should be True if we have a new tracks
                object and should therefore recompute the axis_order.
        """

        if self.tracks is None:
            return

        if not initialization and (
            self.tree_widget_present is False and self.table_widget_present is False
        ):
            # no need to update if there are no tracks or there is no widget that needs
            # the dataframe
            return

        if initialization and (self.tree_widget_present or self.table_widget_present):
            # no need to call for update, since we already should have it for the existing
            # table or tree widget
            return

        # in the case menu_manager was never initialized, we cannot directly check if
        # widgets exist, so we always update the track_df if self.tracks is not None.

        if refresh_view:
            self.track_df, self.axis_order = extract_sorted_tracks(
                self.tracks, self.colormap
            )
        else:
            self.track_df, self.axis_order = extract_sorted_tracks(
                self.tracks,
                self.colormap,
                self.axis_order,
            )

    def _refresh(self, node: str | None = None, refresh_view: bool = False) -> None:
        """Call refresh function on napari layers and the submit signal that tracks are
        updated. Restore the selected_nodes, if possible
        """

        if self.collection_widget is not None:
            self.collection_widget._refresh()

        if len(self.selected_nodes) > 0 and any(
            not self.tracks.graph_solution.has_node(node)
            for node in self.selected_nodes
        ):
            self.selected_nodes.reset()

        self.tracking_layers._refresh()

        self.update_track_df(initialization=False, refresh_view=refresh_view)

        self.tracks_updated.emit(refresh_view)

        # if a new node was added, we would like to select this one now (call this after
        # emitting the signal, because if the node is a new node, we have to update the
        # table in the tree widget first, or it won't be present)
        if node is not None:
            self.selected_nodes.add(node)

        # restore selection and/or highlighting in all napari Views (napari Views do not
        # know about their selection ('all' vs 'lineage'), but TracksViewer does)
        self.update_selection(update_counts=True)

    def _disconnect_tracks(self) -> None:
        """Stop listening to the currently displayed tracks object.

        The connections below live on the Tracks object, not on this TracksViewer,
        so they outlive both the viewer and the singleton reference unless they are
        explicitly removed. Because one Tracks object can be handed to more than one
        viewer over a session, leaving them in place means an edit notifies every
        TracksViewer that ever displayed those tracks.
        """
        tracks = getattr(self, "tracks", None)
        if tracks is not None:
            tracks.refresh.disconnect(self._refresh)
            tracks.action_applied.disconnect(self._on_action_applied)

    def update_tracks(self, tracks: Tracks, name: str) -> None:
        """Stop viewing a previous set of tracks and replace it with a new one.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            tracks (funtracks.data_model.Tracks): The tracks to visualize in napari.
            name (str): The name of the tracks to display in the layer names
        """
        # clear rather than reset: the selection history belongs to the outgoing
        # tracks, and restoring one of its node ids against a different graph is
        # meaningless. This drops deleted_items with it.
        self.selected_nodes.clear()

        self._disconnect_tracks()

        self.tracks = tracks

        # listen to refresh signals from the tracks
        self.tracks.refresh.connect(self._refresh)
        # connect to action_applied signal to track deleted nodes
        self.tracks.action_applied.connect(self._on_action_applied)

        # deactivate the input labels layer
        for layer in self.viewer.layers:
            if isinstance(layer, (napari.layers.Labels | napari.layers.Points)):
                layer.visible = False

        # retrieve existing groups
        if self.collection_widget is not None:
            self.collection_widget.retrieve_existing_groups()

        self.set_display_mode("all")
        self.tracking_layers.set_tracks(tracks, name)
        self.set_axis_labels()  # the layers are in, so the viewer's dims have settled
        self.selected_nodes.reset()

        # ensure a valid track is selected from the start
        self.request_new_track()

        self.update_track_df(initialization=False, refresh_view=True)

        # emit the update signal
        self.tracks_updated.emit(True)

        # Update visualization widget
        self.mode_updated.emit()

    def clear_tracks(self) -> None:
        """Stop displaying any tracks at all: the mirror of update_tracks.

        Called when the last entry leaves the results list. Without it the napari
        layers, the tree plot and the table keep rendering a tracks object that the
        application no longer holds.

        Input layers that update_tracks hid stay hidden: the user may have hidden
        them themselves, and we do not record which ones were ours.
        """

        self._disconnect_tracks()
        self.tracks = None
        # update_track_df cannot produce this: it returns early without tracks, so
        # the dataframe of the tracks that just went away would survive
        self.track_df = pd.DataFrame()
        self.axis_order = []

        # remove the layers before clearing the selection: clearing emits
        # selection_updated, and the update_selection that follows would otherwise
        # recolour layers that are about to be thrown away
        self.tracking_layers.set_tracks(None, "")
        self.selected_nodes.clear()

        self.set_display_mode("all")
        if self.collection_widget is not None:
            self.collection_widget.retrieve_existing_groups()

        # reset_view=True is required: the TreeWidget only returns to "all" mode and
        # drops its lineage dataframe when this argument is truthy
        self.tracks_updated.emit(True)
        self.mode_updated.emit()

    def toggle_display_mode(self, event=None) -> None:
        """Toggle the display mode between available options.

        Skips 'group' mode when no groups exist, alternating only between
        'all' and 'lineage' in that case.
        """

        has_groups = (
            self.collection_widget is not None
            and self.collection_widget.collection_list.count() > 0
        )

        if self.mode == "lineage":
            self.set_display_mode("group" if has_groups else "all")
        elif self.mode == "group":
            self.set_display_mode("all")
        else:
            self.set_display_mode("lineage")
        self.mode_updated.emit()

    def set_display_mode(self, mode: str) -> None:
        """Update the display mode and call to update colormaps for points, labels, and tracks"""

        if mode == "lineage":
            self.mode = "lineage"
            self.viewer.text_overlay.text = BASE_TEXT + "Lineage"
        elif mode == "group":
            self.mode = "group"
            self.viewer.text_overlay.text = BASE_TEXT + "Group"
        else:
            self.mode = "all"
            self.viewer.text_overlay.text = BASE_TEXT + "All"

        self.viewer.text_overlay.visible = True
        self.viewer.text_overlay.font_size = 8
        self.filter_visible_nodes()
        self.tracking_layers.update_visible(self.visible)

    def filter_visible_nodes(self) -> list[int] | str:
        """Construct a list of node_ids that should be displayed according to the display
        mode: 'all', 'lineage', or 'group'). Note that whether a node is truly
        displayed also depends on whether it is in the current selection (not computed
        here). Additionally, if the mode is 'lineage' and the selection is cleared we
        keep the previous list of nodes visible to not have an entirely empty viewer.
        """

        if self.tracks is None or self.tracks.graph_solution is None:
            self.visible = []
            return
        if self.mode == "lineage":
            # if no nodes are selected, check which nodes were previously visible and
            # filter those
            if len(self.selected_nodes) == 0 and self.visible is not None:
                prev_visible = [
                    node
                    for node in self.visible
                    if self.tracks.graph_solution.has_node(node)
                ]
                self.visible = []
                for node_id in prev_visible:
                    self.visible += extract_lineage_tree(
                        self.tracks.graph_solution, node_id
                    )
                    if set(prev_visible).issubset(self.visible):
                        break
            else:
                self.visible = []
                for node in self.selected_nodes:
                    self.visible += extract_lineage_tree(
                        self.tracks.graph_solution, node
                    )
        elif self.mode == "group":
            if (
                self.collection_widget is not None
                and self.collection_widget.selected_collection is not None
            ):
                self.visible = list(
                    self.collection_widget.selected_collection.collection
                )
            else:
                self.visible = []
        else:
            self.visible = "all"

    @contextmanager
    def viewer_interaction(self):
        """Mark everything that happens inside this block as originating from the
        napari canvas, to suppress node centering when the seg or points layer is not in
        pan_zoom mode.
        """

        previous = self.interacting_with_canvas
        self.interacting_with_canvas = True
        try:
            yield
        finally:
            self.interacting_with_canvas = previous

    def center_on_node(self, node: int) -> None:
        """Request all views to center on the given node.

        Emits the center_node signal which is listened to by the tracking layers
        and tree view to synchronize centering.

        Args:
            node: The node ID to center on.
        """
        self.center_node.emit(node)

    def select_track_id_from_node(self, node: int) -> None:
        """Adopt the tracklet id of the given node as the current track id, without
        selecting or centering on that node.

        This is similar to the pipette behavior on the labels layer, but now available
        on all views, and not bound to the current time point. With a segmentation
        present, the pick goes through the labels layer's ``selected_label``, so
        ``_ensure_valid_label`` decides the label value that should be painted with
        that is consistent with the picked tracklet id.

        Args:
            node: The node ID whose tracklet id should become the current one.
        """

        node = int(node)
        if self.tracks is None or not self.tracks.graph_solution.has_node(node):
            return

        seg_layer = self.tracking_layers.seg_layer
        if seg_layer is not None:
            if seg_layer.selected_label == node:
                seg_layer._ensure_valid_label()
            else:
                seg_layer.selected_label = node
        else:
            # no segmentation to paint in: only the track id itself is meaningful
            self.selected_track = int(self.tracks.get_track_id(node))
            self.set_track_id_color(self.selected_track)
            self.update_track_id.emit()

    def _on_action_applied(self, action: BasicAction) -> None:
        """Handle action_applied signal from tracks.

        Updates the deleted_items set to track which nodes have been deleted,
        and clears nodes that were added back (via undo or re-addition).

        Args:
            action: The action that was applied (from funtracks)
        """

        if isinstance(action, DeleteNode):
            self.selected_nodes.deleted_items.add(action.node)
        elif isinstance(action, AddNode):
            self.selected_nodes.deleted_items.discard(action.node)

    def update_selection(
        self, set_view: bool = True, update_counts: bool = False
    ) -> None:
        """Sets the view and triggers visualization updates in other components"""

        if set_view and len(self.selected_nodes) == 1:
            self.center_on_node(self.selected_nodes[0])

        self.filter_visible_nodes()
        self.tracking_layers.update_visible(self.visible)

        if self.tracks is not None and len(self.selected_nodes) > 0:
            self.selected_track = self.tracks.get_track_id(self.selected_nodes[-1])

        self.set_track_id_color(self.selected_track)
        self.update_track_id.emit()
        self.node_selection_updated.emit(update_counts)

    def delete_node(self, event=None):
        """Calls the UserAction to delete currently selected nodes"""

        if self.tracks is None:
            return
        UserDeleteNodes(
            self.tracks, nodes=[int(n) for n in self.selected_nodes.as_list]
        )

    def swap_nodes(self, event=None):
        """Calls the UserAction to swap the predecessors of the two currently
        selected nodes
        """

        if len(self.selected_nodes) == 2:
            node1 = self.selected_nodes[0]
            node2 = self.selected_nodes[1]

            UserSwapPredecessors(self.tracks, nodes=(int(node1), int(node2)))

    def set_division(self, event=None):
        """Calls the UserAction to make or break a division between the three
        currently selected nodes
        """

        if self.tracks is None:
            return
        nodes = [int(node) for node in self.selected_nodes.as_list]
        try:
            UserSetDivision(self.tracks, tuple(nodes))
        except InvalidActionError as e:
            QMessageBox.warning(None, "Cannot set division", str(e))

    def merge_horizontally(self, event=None):
        """Merge every set of selected nodes that shares a time point into one node.

        The user picks which of the tracklet ids in a set the merged node should keep.
        Sets that offer the same tracklet ids are asked about only once. Cancelling any
        of the dialogs cancels the whole merge.
        """

        if self.tracks is None:
            return
        nodes = [int(node) for node in self.selected_nodes.as_list]
        try:
            options = get_track_id_options(self.tracks, nodes)
            track_id_per_time = self._ask_merge_track_ids(options, self.colormap)
            if track_id_per_time is None:
                return  # the user cancelled, so merge nothing at all
            UserMergeNodes(self.tracks, nodes, track_ids=track_id_per_time)
        except InvalidActionError as e:
            QMessageBox.warning(None, "Cannot merge nodes", str(e))

    @staticmethod
    def _ask_merge_track_ids(
        options: dict[int, list[int]], colormap
    ) -> dict[int, int] | None:
        """Ask the user which tracklet id to keep in each set of nodes to merge.

        Args:
            options: A mapping from time point to the tracklet ids to choose from.
            colormap: The colormap used to color the tracklet id options.

        Returns:
            A mapping from time point to the chosen tracklet id, or None if the user
            cancelled any of the dialogs.
        """

        # Time points offering the same tracklet ids can be answered in one dialog
        times_per_option: dict[tuple[int, ...], list[int]] = {}
        for time, track_ids in options.items():
            times_per_option.setdefault(tuple(track_ids), []).append(time)

        track_id_per_time: dict[int, int] = {}
        for track_ids, times in times_per_option.items():
            track_id = select_merge_track_id(list(track_ids), times, colormap)
            if track_id is None:
                return None
            for time in times:
                track_id_per_time[time] = track_id
        return track_id_per_time

    def connect_nodes(self, event=None, linear: bool | None = None):
        """Connect the currently selected nodes into a single track, or break them
        apart again if they are already connected.

        Which of the two happens depends on the selection: only when there is nothing
        left to connect - every consecutive pair in time order already has an edge -
        does this disconnect them. In every other case the nodes are connected as far
        as they can be, leaving the pairs that are connected already alone.

        Args:
            event: Unused, present so this can be used as a keybinding callback.
            linear: If True, existing outgoing edges of the selected nodes are broken
                so that the result is one linear track. If False, they are kept and
                divisions are created instead. If None (the default), the user is
                asked which of the two they want, but only when the choice makes a
                difference for this selection. Ignored when disconnecting.
        """

        if self.tracks is None:
            return
        if len(self.selected_nodes) < 2:
            return

        nodes = [int(node) for node in self.selected_nodes.as_list]

        if is_connected_chain(self.tracks, nodes):
            # nothing left to connect, so the button breaks the chain apart instead
            try:
                UserDisconnectNodes(self.tracks, nodes)
            except InvalidActionError as e:
                QMessageBox.warning(None, "Cannot disconnect nodes", str(e))
            return

        if linear is None:
            if UserConnectNodes.has_division_choice(self.tracks, nodes):
                linear = ask_connect_mode()
                if linear is None:  # cancelled
                    return
            else:
                linear = False

        try:
            UserConnectNodes(self.tracks, nodes, linear=linear, force=self.force)
        except InvalidActionError as e:
            if e.forceable:
                # Ask the user if the action should be forced
                force, always_force = confirm_force_operation(message=str(e))
                self.force = always_force
                if force:
                    UserConnectNodes(self.tracks, nodes, linear=linear, force=True)
            else:
                QMessageBox.warning(None, "Cannot connect nodes", str(e))

    def connect_nodes_with_divisions(self, event=None):
        """Connect the selected nodes, keeping existing outgoing edges as divisions."""

        self.connect_nodes(linear=False)

    def connect_nodes_linearly(self, event=None):
        """Connect the selected nodes into one linear track, breaking the existing
        outgoing edges of the nodes that get a new child."""

        self.connect_nodes(linear=True)

    def undo(self, event=None):
        if self.tracks is None:
            return
        self.tracks.undo()

    def redo(self, event=None):
        if self.tracks is None:
            return
        self.tracks.redo()

    def hide_panels(self, event=None):
        """Show/hide menu and tree view panels without destroying"""

        if self.menu_manager is not None:
            self.menu_manager.toggle_menu_panel_visibility()

    def deselect(self, event=None):
        self.selected_nodes.reset()

    def restore_selection(self, event=None):
        self.selected_nodes.restore()

    def select_node_set_from_history(self, previous: bool):
        """Move forwards or backwards through selection history."""
        self.selected_nodes.select_node_set_from_history(previous=previous)

    def select_next(self, event=None):
        """Select next node set from history"""
        self.select_node_set_from_history(previous=False)

    def select_previous(self, event=None):
        """Select previous node set from history"""
        self.select_node_set_from_history(previous=True)
