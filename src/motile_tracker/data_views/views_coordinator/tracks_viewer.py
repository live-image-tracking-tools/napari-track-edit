from __future__ import annotations

from typing import Optional

import napari
import pandas as pd
from funtracks.actions import AddNode, BasicAction, DeleteNode
from funtracks.data_model import SolutionTracks
from funtracks.exceptions import InvalidActionError
from funtracks.user_actions import (
    UserAddEdge,
    UserDeleteEdge,
    UserDeleteNodes,
    UserSwapPredecessors,
)
from psygnal import Signal
from qtpy.QtWidgets import QMessageBox

from motile_tracker.data_views.keybindings_config import (
    KEYMAP,
    bind_keymap,
)
from motile_tracker.data_views.node_type import NodeType
from motile_tracker.data_views.views.layers.track_labels import new_label
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
    confirm_force_operation,
)

BASE_TEXT = "Click: select node\nShift+Click: append to selection\nCtrl/Cmd+Click: center node\n[Q]: toggle display\nCurrent display mode: "


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
        self.tracks: SolutionTracks | None = None
        self.visible: list | str = []
        self.tracking_layers = TracksLayerGroup(self.viewer, self.tracks, "", self)
        self.center_node.connect(self.tracking_layers.center_view)
        self.selected_nodes = NodeSelectionHistory()
        self.selected_nodes.selection_updated.connect(self.update_selection)

        self.track_df = pd.DataFrame()  # initialize empty dataframe
        self.axis_order: list[int] = []

        self.tracks_list = TracksList()
        self.tracks_list.view_tracks.connect(self.update_tracks)
        self.tracks_list.request_colormap.connect(self.set_colormap_to_trackslist)
        self.selected_track = None
        self.track_id_color = [0, 0, 0, 0]
        self.force = False

        self.collection_widget = None

        self.set_keybinds()

        self.viewer.dims.events.ndisplay.connect(self.update_selection)

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

    def request_new_track(self) -> None:
        """Request a new track id (with new segmentation label if a seg layer is present)"""

        if self.tracking_layers.seg_layer is not None:
            new_label(self.tracking_layers.seg_layer)
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
            not self.tracks.graph.has_node(node) for node in self.selected_nodes
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

    def update_tracks(self, tracks: SolutionTracks, name: str) -> None:
        """Stop viewing a previous set of tracks and replace it with a new one.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            tracks (funtracks.data_model.Tracks): The tracks to visualize in napari.
            name (str): The name of the tracks to display in the layer names
        """
        self.selected_nodes.reset()

        self._disconnect_tracks()

        self.tracks = tracks
        self.selected_nodes.deleted_items.clear()  # Reset deleted nodes when switching tracks

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
        self.selected_nodes.reset()

        # ensure a valid track is selected from the start
        self.request_new_track()

        self.update_track_df(initialization=False, refresh_view=True)

        # emit the update signal
        self.tracks_updated.emit(True)

        # Update visualization widget
        self.mode_updated.emit()

    def toggle_display_mode(self, event=None) -> None:
        """Toggle the display mode between available options.

        Skips 'group' mode when no groups exist, alternating only between
        'all' and 'lineage' in that case.
        """

        has_groups = self.collection_widget.collection_list.count() > 0

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

        if self.tracks is None or self.tracks.graph is None:
            self.visible = []
        if self.mode == "lineage":
            # if no nodes are selected, check which nodes were previously visible and
            # filter those
            if len(self.selected_nodes) == 0 and self.visible is not None:
                prev_visible = [
                    node for node in self.visible if self.tracks.graph.has_node(node)
                ]
                self.visible = []
                for node_id in prev_visible:
                    self.visible += extract_lineage_tree(self.tracks.graph, node_id)
                    if set(prev_visible).issubset(self.visible):
                        break
            else:
                self.visible = []
                for node in self.selected_nodes:
                    self.visible += extract_lineage_tree(self.tracks.graph, node)
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

    def center_on_node(self, node: int) -> None:
        """Request all views to center on the given node.

        Emits the center_node signal which is listened to by the tracking layers
        and tree view to synchronize centering.

        Args:
            node: The node ID to center on.
        """
        self.center_node.emit(node)

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

        if len(self.selected_nodes) > 0:
            self.selected_track = self.tracks.get_track_id(self.selected_nodes[-1])
        else:
            self.selected_track = None

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

    def delete_edge(self, event=None):
        """Calls the UserAction to delete an edge between the two currently
        selected nodes
        """

        if self.tracks is None:
            return
        if len(self.selected_nodes) == 2:
            node1 = self.selected_nodes[0]
            node2 = self.selected_nodes[1]

            time1 = self.tracks.get_time(node1)
            time2 = self.tracks.get_time(node2)

            if time1 > time2:
                node1, node2 = node2, node1

            node1, node2 = int(node1), int(node2)
            UserDeleteEdge(self.tracks, (node1, node2))

    def swap_nodes(self, event=None):
        """Calls the UserAction to swap the predecessors of the two currently
        selected nodes
        """

        if len(self.selected_nodes) == 2:
            node1 = self.selected_nodes[0]
            node2 = self.selected_nodes[1]

            UserSwapPredecessors(self.tracks, nodes=(int(node1), int(node2)))

    def create_edge(self, event=None):
        """Add an edge between the two currently selected nodes"""

        if self.tracks is None:
            return
        if len(self.selected_nodes) == 2:
            node1 = self.selected_nodes[0]
            node2 = self.selected_nodes[1]

            time1 = self.tracks.get_time(node1)
            time2 = self.tracks.get_time(node2)

            if time1 > time2:
                node1, node2 = node2, node1

            node1, node2 = int(node1), int(node2)

            if self.tracks.graph.out_degree(node1) >= 2:
                QMessageBox.warning(
                    None,
                    "Cannot add edge",
                    f"Node {node1} already has 2 children. Delete one of the "
                    "existing daughter edges before adding a new one.",
                )
                return

            try:
                UserAddEdge(self.tracks, (node1, node2), force=self.force)
            except InvalidActionError as e:
                if e.forceable:
                    # Ask the user if the action should be forced
                    force, always_force = confirm_force_operation(message=str(e))
                    self.force = always_force
                    if force:
                        UserAddEdge(self.tracks, (node1, node2), force=True)
                else:
                    # Re-raise the exception if it is not forceable
                    raise

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
