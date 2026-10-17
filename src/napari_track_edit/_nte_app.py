from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

import napari
from napari_orthogonal_views.ortho_view_manager import OrthoViewManager
from qtpy.QtCore import Qt
from qtpy.QtGui import QShortcut
from qtpy.QtWidgets import QWidget

from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer

if TYPE_CHECKING:
    from napari_track_edit.application_menus.menu_manager import MenuManager
    from napari_track_edit.data_views.views_coordinator.tracks_list import TracksList


class MenuWidgetConfig(TypedDict):
    """A menu widget's class and which side of the viewer it docks to."""

    widget: type[QWidget]
    location: Literal["left", "right", "top", "bottom"]


class NTEAppConfig:
    """How this app instance is currently set up: which widgets are open,
    whether orthogonal views and the canvas text overlay are on.

    Currently just reads/writes the live objects that already track each of
    these (MenuManager, OrthoViewManager, the napari Viewer's text overlay) -
    nothing here is persisted to disk yet. The point of grouping them here
    rather than leaving them scattered is to give future persistence (saving
    this on close, restoring it on the next launch) a single place to read
    from and write to.
    """

    def __init__(self, app: NTEApp):
        self._app = app

    @property
    def open_widgets(self) -> set[str]:
        """Names of the menu widgets currently initialized (open at least once,
        whether or not they are presently visible)."""
        return set(self._app.menu_manager.initialized_menu_widgets)

    @property
    def orthoviews_enabled(self) -> bool:
        manager = self._app.ortho_view_manager
        return manager is not None and manager.is_shown()

    @orthoviews_enabled.setter
    def orthoviews_enabled(self, value: bool) -> None:
        manager = self._app.ortho_view_manager
        if manager is None:
            if not value:
                return
            # Created on demand, independent of which menu widgets happen to be
            # open: this only needs the viewer's Qt window to exist (not any
            # layers), so nothing requires waiting for VisualizationWidget.
            from napari_track_edit.data_views.views.ortho_views import (
                initialize_ortho_views,
            )

            manager = initialize_ortho_views(self._app.viewer)

        if value:
            manager.show()
        else:
            manager.hide()

    @property
    def text_overlay_visible(self) -> bool:
        return self._app.viewer.text_overlay.visible

    @text_overlay_visible.setter
    def text_overlay_visible(self, value: bool) -> None:
        self._app.viewer.text_overlay.visible = value


class NTEApp:
    """The running napari-track-edit application state for one napari Viewer."""

    @classmethod
    def get_instance(cls, viewer: napari.Viewer | None = None) -> NTEApp:
        if not hasattr(cls, "_instance") or (
            viewer is not None and cls._instance.viewer is not viewer
        ):
            if viewer is None:
                raise ValueError("Make a viewer first please!")
            cls._instance = NTEApp(viewer)
        return cls._instance

    def __init__(self, viewer: napari.Viewer):
        self.viewer = viewer
        self._menu_manager: MenuManager | None = None
        self.config = NTEAppConfig(self)
        self._shortcuts: list[QShortcut] = []
        self._bind_app_keymap()

    def _bind_app_keymap(self) -> None:
        """Bind every "app"-targeted KEYBINDINGS action as a Qt.ApplicationShortcut,
        so it fires no matter what has focus - unlike "tracks_viewer"/"tree_widget"
        actions, which only fire on the specific layer/widget they are bound to.
        """
        from napari_track_edit.data_views.keybindings_config import KEYBINDINGS

        qt_window = self.viewer.window._qt_window
        for action, config in KEYBINDINGS.items():
            if "app" not in config["targets"]:
                continue
            handler = getattr(self, action, None)
            if handler is None:
                continue
            for key in config["napari_keys"]:
                shortcut = QShortcut(key, qt_window)
                shortcut.setContext(Qt.ApplicationShortcut)
                shortcut.activated.connect(handler)
                self._shortcuts.append(shortcut)

    @property
    def tracks_viewer(self) -> TracksViewer:
        return TracksViewer.get_instance(self.viewer)

    @property
    def tracks_list(self) -> TracksList:
        """The TracksList holding every Tracks object loaded into this viewer,
        independent of which one (if any) is currently displayed.
        """
        return self.tracks_viewer.tracks_list

    @property
    def menu_manager(self) -> MenuManager:
        """The MenuManager for this viewer, created on first access."""
        if self._menu_manager is None:
            from napari_track_edit.application_menus.menu_manager import MenuManager

            self._menu_manager = MenuManager(self.viewer)
        return self._menu_manager

    @property
    def ortho_view_manager(self) -> OrthoViewManager | None:
        """The OrthoViewManager already set up for this viewer, or None if
        orthogonal views have not been turned on yet.

        Unlike `initialize_ortho_views`, this never creates one: that function
        both creates the manager *and* (re-)registers every layer hook/sync
        filter, so it should only be called once, the first time the user asks
        for orthogonal views - callers that only want to check or use an
        existing manager should use this property instead.
        """
        from napari_orthogonal_views.ortho_view_manager import _VIEWER_MANAGERS

        return _VIEWER_MANAGERS.get(self.viewer)

    def hide_panels(self) -> None:
        """Show/hide menu and tree view panels without destroying them."""
        self.menu_manager.toggle_menu_panel_visibility()
