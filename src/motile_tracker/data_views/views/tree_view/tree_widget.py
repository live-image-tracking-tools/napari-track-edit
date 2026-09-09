# do not put the from __future__ import annotations as it breaks the injection

import contextlib

import napari
import numpy as np
import pandas as pd
from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible

from motile_tracker.data_views.keybindings_config import (
    GENERAL_KEY_ACTIONS,
    TREE_WIDGET_MODIFIER_ACTIONS,
    TREE_WIDGET_NAVIGATION_KEYS,
    TREE_WIDGET_SPECIFIC_ACTIONS,
)
from motile_tracker.data_views.views.tree_view.flip_axes_widget import FlipTreeWidget
from motile_tracker.data_views.views.tree_view.navigation_widget import NavigationWidget
from motile_tracker.data_views.views.tree_view.tree_plot_fpl import TreePlot
from motile_tracker.data_views.views.tree_view.tree_view_feature_widget import (
    TreeViewFeatureWidget,
)
from motile_tracker.data_views.views.tree_view.tree_view_mode_widget import (
    TreeViewModeWidget,
)
from motile_tracker.data_views.views.tree_view.tree_view_options_widget import (
    TreeViewOptionsWidget,
)
from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_lineage_tree,
    get_features_from_tracks,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TreeWidget(QWidget):
    """fastplotlib-based widget for lineage tree visualization and navigation"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.lineage_df = pd.DataFrame()  # the currently viewed subset of lineages
        self.graph = None
        self.mode = "all"  # options: "all", "lineage"
        self.plot_type = "tree"  # options: "tree", "feature"
        self.view_direction = "vertical"  # options: "horizontal", "vertical"

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.update_track_df(
            initialization=True, refresh_view=True
        )  # make sure tracks_viewer initializes/updates the track df
        self.tracks_viewer.tree_widget_present = True
        self.selected_nodes = self.tracks_viewer.selected_nodes
        self.tracks_viewer.node_selection_updated.connect(self._update_selected)
        self.tracks_viewer.tracks_updated.connect(self._update_track_data)

        # Construct the tree view (fastplotlib) canvas widget
        layout = QVBoxLayout()

        self.tree_widget: TreePlot = TreePlot()
        self.tree_widget.update_selection.connect(
            self.tracks_viewer.select_node_set_from_history
        )
        self.tree_widget.node_clicked.connect(self.selected_nodes.add)
        self.tree_widget.jump_to_node.connect(self.tracks_viewer.center_on_node)
        self.tree_widget.nodes_selected.connect(self.selected_nodes.add_list)
        self.tracks_viewer.center_node.connect(self.tree_widget.center_on_node)

        # Add radiobuttons for switching between different display modes
        self.mode_widget = TreeViewModeWidget()
        self.mode_widget.change_mode.connect(self._set_mode)

        # Add buttons to change which feature to display
        features_to_plot = get_features_from_tracks(
            self.tracks_viewer.tracks,
            features_to_ignore=["Time", "Tracklet ID", "Bounding box"],
        )
        self.plot_type_widget = TreeViewFeatureWidget(
            features_to_plot,
            get_features=lambda: get_features_from_tracks(
                self.tracks_viewer.tracks,
                features_to_ignore=["Time", "Tracklet ID", "Bounding box"],
            ),
        )
        self.plot_type_widget.change_plot_type.connect(self._set_plot_type)

        # Add navigation widget
        self.navigation_widget = NavigationWidget(
            self.tracks_viewer.track_df,
            self.lineage_df,
            self.view_direction,
            self.selected_nodes,
            self.plot_type,
        )
        # Add widget to flip the axes
        self.flip_widget = FlipTreeWidget()
        self.flip_widget.flip_tree.connect(self.flip_axes)

        # Add checkboxes for the tree view's own annotations
        self.options_widget = TreeViewOptionsWidget(
            show_track_ids=self.tree_widget.show_track_ids,
            show_hover_info=self.tree_widget.show_hover_info,
        )
        self.options_widget.show_track_ids_changed.connect(
            self.tree_widget.set_show_track_ids
        )
        self.options_widget.show_hover_info_changed.connect(
            self.tree_widget.set_show_hover_info
        )

        # Construct a toolbar and set main layout
        panel_layout = QHBoxLayout()
        panel_layout.addWidget(self.mode_widget)
        panel_layout.addWidget(self.plot_type_widget)
        panel_layout.addWidget(self.navigation_widget)
        panel_layout.addWidget(self.flip_widget)
        panel_layout.addWidget(self.options_widget)
        panel_layout.setSpacing(0)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        panel.setLayout(panel_layout)
        panel.setMaximumWidth(1060)  # 930 + room for the options checkboxes
        panel.setMaximumHeight(82)

        # Make a collapsible for TreeView widgets
        collapsible_widget = QCollapsible("Show/Hide Tree View Controls")
        collapsible_widget.layout().setContentsMargins(0, 0, 0, 0)
        collapsible_widget.layout().setSpacing(0)
        collapsible_widget.addWidget(panel)
        collapsible_widget.collapse(animate=False)

        tree_widget = QWidget()
        layout.addWidget(collapsible_widget)
        layout.addWidget(self.tree_widget)
        layout.setSpacing(0)
        tree_widget.setLayout(layout)

        self.setLayout(layout)

        # Install eventfilter to watch for the deferred delete event, and call cleanup()
        # to close the fastplotlib canvas before the Qt widgets are destroyed.
        qt_main_window = getattr(viewer.window, "_qt_window", None)
        if qt_main_window is not None:
            qt_main_window.installEventFilter(self)

        self._update_track_data(reset_view=True)

    def cleanup(self) -> None:
        """Tear down the tree view: stop reacting to TracksViewer signals, then close
        the wgpu canvas while its Qt widgets are still alive. Idempotent.

        Called by MenuManager when the widget is destroyed, and by the event hooks
        below when napari's main window goes away. Disconnecting comes first, so that
        nothing tries to redraw a figure that is already closed.
        """
        self.tracks_viewer.tree_widget_present = False
        for signal, slot in (
            (self.tracks_viewer.node_selection_updated, self._update_selected),
            (self.tracks_viewer.tracks_updated, self._update_track_data),
            (self.tracks_viewer.center_node, self.tree_widget.center_on_node),
        ):
            with contextlib.suppress(ValueError, KeyError, RuntimeError):
                signal.disconnect(slot)
        self.tree_widget.close_figure()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Trigger clean up when napari's main window is being destroyed"""
        if event.type() == QEvent.Type.DeferredDelete:
            with contextlib.suppress(AttributeError, RuntimeError):
                self.cleanup()
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt-style name)
        self.cleanup()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events.

        Priority order:
        1. Tree-widget-specific keybinds (highest priority) - call TreeWidget methods
        2. General keybinds (work in table widget too) - call tracks_viewer methods
        3. Modifier keybinds (mouse zoom constraints)
        4. Navigation (arrow keys)
        """
        # Handle tree-widget-specific keybinds first (higher priority)
        action_name = TREE_WIDGET_SPECIFIC_ACTIONS.get(event.key())
        if action_name:
            method = getattr(self, action_name, None)
            if method:
                method()
                event.accept()
                return

        # Try general keybinds (these also work in table widget)
        action_name = GENERAL_KEY_ACTIONS.get(event.key())
        if action_name:
            method = getattr(self.tracks_viewer, action_name, None)
            if method:
                method()
                event.accept()
                return

        # Handle mouse zoom constraints (X/Y axes)
        if event.key() in TREE_WIDGET_MODIFIER_ACTIONS:
            x_enabled, y_enabled = TREE_WIDGET_MODIFIER_ACTIONS[event.key()]
            self.set_mouse_enabled(x=x_enabled, y=y_enabled)
            event.accept()
            return

        # Handle navigation (Arrow keys)
        direction = TREE_WIDGET_NAVIGATION_KEYS.get(event.key())
        if direction:
            self.navigation_widget.move(direction)
            self.tree_widget.setFocus()
            event.accept()

    def delete_node(self):
        """Delete a node."""
        self.tracks_viewer.delete_node()

    def create_edge(self):
        """Create an edge."""
        self.tracks_viewer.create_edge()

    def delete_edge(self):
        """Delete an edge."""
        self.tracks_viewer.delete_edge()

    def swap_nodes(self):
        """Swap the nodes by swapping upstream edges"""
        self.tracks_viewer.swap_nodes()

    def undo(self):
        """Undo action."""
        self.tracks_viewer.undo()

    def redo(self):
        """Redo action."""
        self.tracks_viewer.redo()

    def deselect(self):
        """Deselect all nodes"""
        self.tracks_viewer.deselect()

    def restore_selection(self):
        """Restore previous selection"""
        self.tracks_viewer.restore_selection()

    def toggle_display_mode(self):
        """Toggle display mode."""
        self.mode_widget._toggle_display_mode()

    def toggle_feature_mode(self):
        """Toggle feature mode."""
        self.plot_type_widget._toggle_plot_type()

    def flip_axes(self):
        """Flip the axes of the plot"""

        if self.view_direction == "horizontal":
            self.view_direction = "vertical"
        else:
            self.view_direction = "horizontal"

        self.navigation_widget.view_direction = self.view_direction
        self.tree_widget._update_viewed_data(self.view_direction)
        # flipping transposes x<->y, so the previous camera rect no longer matches
        # the data — reframe to fit (matches the old pyqtgraph autoRange-on-flip).
        self.tree_widget.set_view(
            view_direction=self.view_direction,
            plot_type=self.tree_widget.plot_type,
            reset_view=True,
        )

    def set_mouse_enabled(self, x: bool, y: bool):
        """Enable or disable mouse zoom scrolling in X or Y direction."""
        self.tree_widget.setMouseEnabled(x=x, y=y)

    def keyReleaseEvent(self, ev):
        """Reset the mouse scrolling when releasing the X/Y key"""

        if ev.key() == Qt.Key_X or ev.key() == Qt.Key_Y:
            self.tree_widget.setMouseEnabled(x=True, y=True)

    def _update_selected(self):
        """Called whenever the selection list is updated. Only re-computes
        the full graph information when the new selection is not in the
        lineage df (and in lineage mode)
        """

        if self.mode == "lineage" and any(
            node not in np.unique(self.lineage_df["node_id"].values)
            for node in self.selected_nodes
        ):
            self._update_lineage_df()
            self.tree_widget.update(
                self.lineage_df,
                self.view_direction,
                self.plot_type,
                self.plot_type_widget.get_current_feature(),
                self.selected_nodes,
                # the plot now holds a different lineage, whose lanes (and, in feature
                # mode, whose value range) have nothing to do with the camera framing
                # left over from the previous one, so refit. TracksViewer's center_node
                # signal cannot cover this: it fires before this rebuild, against data
                # that is about to be replaced.
                reset_view=True,
            )
        else:
            self.tree_widget.set_selection(self.selected_nodes, self.plot_type)

    def _update_track_data(self, reset_view: bool | None = None) -> None:
        """Called when the TracksViewer emits the tracks_updated signal, indicating
        that a new set of tracks should be viewed.
        """

        if self.tracks_viewer.tracks is None:
            self.graph = None
        else:
            self.graph = self.tracks_viewer.tracks.graph

        # check whether we have regionprop measurements and therefore should activate the
        # feature button
        features_to_plot = get_features_from_tracks(
            self.tracks_viewer.tracks,
            features_to_ignore=["Time", "Tracklet ID", "Bounding box"],
        )
        self.plot_type_widget.update_feature_dropdown(features_to_plot)

        # if reset_view, we got new data and want to reset display and feature before
        # calling the plot update
        if reset_view:
            self.lineage_df = pd.DataFrame()
            self.mode = "all"
            self.mode_widget.show_all_radio.setChecked(True)
            self.view_direction = "vertical"
            self.plot_type = "tree"
            self.plot_type_widget.show_tree_radio.setChecked(True)
            allow_flip = True
        else:
            allow_flip = False

        # also update the navigation widget
        self.navigation_widget.track_df = self.tracks_viewer.track_df
        self.navigation_widget.lineage_df = self.lineage_df

        # check which view to set
        if self.mode == "lineage":
            self._update_lineage_df()
            self.tree_widget.update(
                self.lineage_df,
                self.view_direction,
                self.plot_type,
                self.plot_type_widget.get_current_feature(),
                self.selected_nodes,
                reset_view=reset_view,
                allow_flip=allow_flip,
            )

        else:
            self.tree_widget.update(
                self.tracks_viewer.track_df,
                self.view_direction,
                self.plot_type,
                self.plot_type_widget.get_current_feature(),
                self.selected_nodes,
                reset_view=reset_view,
                allow_flip=allow_flip,
            )

    def _set_mode(self, mode: str) -> None:
        """Set the display mode to all or lineage view. Currently, linage
        view is always horizontal and all view is always vertical.

        Args:
            mode (str): The mode to set the view to. Options are "all" or "lineage"
        """
        if mode not in ["all", "lineage"]:
            raise ValueError(f"Mode must be 'all' or 'lineage', got {mode}")

        self.mode = mode
        if mode == "all":
            if self.plot_type == "tree":
                self.view_direction = "vertical"
            else:
                self.view_direction = "horizontal"
            df = self.tracks_viewer.track_df
        elif mode == "lineage":
            self.view_direction = "horizontal"
            self._update_lineage_df()
            df = self.lineage_df
        self.navigation_widget.view_direction = self.view_direction
        self.tree_widget.update(
            df,
            self.view_direction,
            self.plot_type,
            self.plot_type_widget.get_current_feature(),
            self.selected_nodes,
            reset_view=True,
        )

    def _set_plot_type(self, plot_type: str) -> None:
        """Set the plot_type mode to 'tree' or 'feature', and adjust view direction. Also
        update the feature on the navigation_widget.

        Args:
            plot_type (str): The plot type to display. Options are "tree" or "feature"
        """
        if plot_type not in ["tree", "feature"]:
            raise ValueError(f"Plot type must be 'tree' or 'feature', got {plot_type}")

        self.plot_type = plot_type
        if plot_type == "tree" and self.mode == "all":
            self.view_direction = "vertical"
        else:
            self.view_direction = "horizontal"

        current_feature = self.plot_type_widget.get_current_feature()

        # Check if we need to rebuild dataframes for a newly computed feature
        if (
            plot_type == "feature"
            and current_feature is not None
            and current_feature not in self.tracks_viewer.track_df.columns
        ):
            self._update_track_data(reset_view=False)

        self.navigation_widget.feature = current_feature
        self.navigation_widget.view_direction = self.view_direction

        if self.mode == "all":
            df = self.tracks_viewer.track_df
        if self.mode == "lineage":
            df = self.lineage_df

        self.navigation_widget.plot_type = self.plot_type
        self.tree_widget.update(
            df,
            self.view_direction,
            self.plot_type,
            current_feature,
            self.selected_nodes,
            reset_view=True,
        )

    def _update_lineage_df(self) -> None:
        """Subset dataframe to include only nodes belonging to the current lineage"""

        if self.tracks_viewer.tracks is None:
            self.lineage_df = pd.DataFrame()  # nothing to plot, set empty dataframe
            return

        if len(self.selected_nodes) == 0 and not self.lineage_df.empty:
            # try to restore lineage df based on previous selection, even if those nodes
            # are now deleted. this is to prevent that deleting nodes will remove those
            # lineages from the lineage view, which is confusing.
            prev_visible_set = set(self.lineage_df["node_id"])
            prev_visible = [
                node for node in prev_visible_set if self.graph.has_node(node)
            ]
            visible = []
            for node_id in prev_visible:
                visible += extract_lineage_tree(self.graph, node_id)
                if set(prev_visible).issubset(visible):
                    break
        else:
            visible = []
            for node_id in self.selected_nodes:
                visible += extract_lineage_tree(self.graph, node_id)
        self.lineage_df = self.tracks_viewer.track_df[
            self.tracks_viewer.track_df["node_id"].isin(visible)
        ].reset_index()
        self.lineage_df["x_axis_pos"] = (
            self.lineage_df["x_axis_pos"].rank(method="dense").astype(int) - 1
        )
        self.navigation_widget.lineage_df = self.lineage_df
