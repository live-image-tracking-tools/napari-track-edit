import contextlib

import napari
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QWidget,
)

from napari_track_edit.application_menus.editing_selection_menu import (
    EditingSelectionWidget,
)
from napari_track_edit.application_menus.feature_widget import FeatureWidget
from napari_track_edit.application_menus.group_widget import GroupWidget
from napari_track_edit.application_menus.menu_manager import MenuManager
from napari_track_edit.application_menus.track_list_widget import TrackListWidget
from napari_track_edit.application_menus.tracking_widget import TrackingWidget
from napari_track_edit.application_menus.visualization_widget import (
    VisualizationWidget,
)
from napari_track_edit.application_menus.welcome_widget import WelcomeWidget
from napari_track_edit.data_views.views.table.custom_table_widget import (
    ColoredTableWidget,
)
from napari_track_edit.data_views.views.tree_view.tree_widget import TreeWidget
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer

MENU_WIDGETS = {
    "Getting Started": {"widget": WelcomeWidget, "location": "right"},
    "Tracking": {"widget": TrackingWidget, "location": "right"},
    "Tracks List": {"widget": TrackListWidget, "location": "right"},
    "Editing && Selection": {"widget": EditingSelectionWidget, "location": "right"},
    "Visualization": {"widget": VisualizationWidget, "location": "right"},
    "Features": {"widget": FeatureWidget, "location": "right"},
    "Groups": {"widget": GroupWidget, "location": "right"},
    "Table": {"widget": ColoredTableWidget, "location": "right"},
    "Lineage View": {"widget": TreeWidget, "location": "bottom"},
}


class StartupWidget(QWidget):
    """Initialize multiple widgets at once, by group"""

    def __init__(self, napari_viewer: napari.Viewer, mode: str = "all"):
        """Initializes groups of widgets at once, docks them to viewer.window, then remove
        itself.
            Args:
                napari_viewer (napari.Viewer): napari viewer to get/initialize
                TracksViewer from and to dock widgets to.
                mode (str, one of ('all', 'tracking', 'editing'): which widget group to
                initialize and mount. Defaults to 'all'.
        """
        super().__init__()
        self.viewer = napari_viewer
        tracks_viewer = TracksViewer.get_instance(napari_viewer)
        if tracks_viewer.menu_manager is not None:
            self.menu_manager = tracks_viewer.menu_manager
        else:
            self.menu_manager = MenuManager(napari_viewer)

        widgets = MENU_WIDGETS
        active_tab = "Getting Started"
        if mode == "tracking":
            subset = ["Tracking", "Tracks List", "Visualization", "Lineage View"]
            widgets = {k: MENU_WIDGETS[k] for k in subset}
            active_tab = "Tracking"
        elif mode == "editing":
            subset = [
                "Tracks List",
                "Editing && Selection",
                "Visualization",
                "Features",
                "Groups",
                "Lineage View",
            ]
            widgets = {k: MENU_WIDGETS[k] for k in subset}
            active_tab = "Tracks List"
        elif mode in MENU_WIDGETS:
            widgets = {mode: MENU_WIDGETS[mode]}
            active_tab = mode

        for name, config in widgets.items():
            self.menu_manager.initialize_menu({name: config})

        # make sure the 'Getting started' tab is the active foreground tab.
        QTimer.singleShot(0, lambda: self._finalize_ui(active_tab))

        # Now safely remove the widget, since everything we need is docked
        QTimer.singleShot(0, self._remove_self)

    def _finalize_ui(self, active_tab: str) -> None:
        """Set the active foreground tab, and move tabbar to the top.
        Args:
            active_tab (str): name of the tab to be set to the foreground (active).
        """
        self.menu_manager.set_tabbar_location(location="North")
        self.menu_manager.set_foreground_tabs([active_tab])

    def _remove_self(self) -> None:
        """Remove the widget from the napari viewer.window.dock_widgets"""
        with contextlib.suppress(LookupError):
            self.viewer.window.remove_dock_widget(self)


# Grouped Widgets
class MainAppWidget(StartupWidget):
    def __init__(self, napari_viewer: napari.Viewer):
        super().__init__(napari_viewer, mode="all")


class TrackingGroupWidget(StartupWidget):
    def __init__(self, napari_viewer: napari.Viewer):
        super().__init__(napari_viewer, mode="tracking")


class EditingGroupWidget(StartupWidget):
    def __init__(self, napari_viewer: napari.Viewer):
        super().__init__(napari_viewer, mode="editing")


# One widget class per menu item
def _make_single_menu_widget_class(widget_name):
    class _SingleMenuWidget(StartupWidget):
        def __init__(self, napari_viewer: napari.Viewer):
            super().__init__(napari_viewer, mode=widget_name)

    _SingleMenuWidget.__name__ = widget_name.replace(" ", "") + "Widget"
    _SingleMenuWidget.__qualname__ = _SingleMenuWidget.__name__
    return _SingleMenuWidget


# Export one class per single widget menu item
GettingStarted_LauncherWidget = _make_single_menu_widget_class("Getting Started")
Tracking_LauncherWidget = _make_single_menu_widget_class("Tracking")
TrackList_LauncherWidget = _make_single_menu_widget_class("Tracks List")
EditingSelection_LauncherWidget = _make_single_menu_widget_class("Editing && Selection")
Visualization_LauncherWidget = _make_single_menu_widget_class("Visualization")
Feature_LauncherWidget = _make_single_menu_widget_class("Features")
Groups_LauncherWidget = _make_single_menu_widget_class("Groups")
Table_LauncherWidget = _make_single_menu_widget_class("Table")
LineageView_LauncherWidget = _make_single_menu_widget_class("Lineage View")
