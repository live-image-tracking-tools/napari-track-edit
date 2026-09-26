"""Tests for MenuManager: initialization, tab management, and widget visibility."""

from unittest.mock import MagicMock

from qtpy.QtWidgets import QDockWidget, QScrollArea, QTabBar, QWidget

from napari_track_edit.application_menus.main_app import MENU_WIDGETS, StartupWidget
from napari_track_edit.application_menus.menu_manager import MenuManager


class DummyWidget(QWidget):
    def __init__(self, viewer):
        super().__init__()


def test_basic_menu_operations(make_napari_viewer):
    """Test initialize_menu, find_dock_widget, toggle, and tabbar location."""
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)

    menu = {"TestWidget": {"widget": DummyWidget, "location": "right"}}
    manager.initialize_menu(menu)

    # initialize_menu adds widget wrapped in QScrollArea
    assert "TestWidget" in viewer.window.dock_widgets
    assert isinstance(viewer.window.dock_widgets["TestWidget"], QScrollArea)

    # _find_dock_widget_by_name finds the widget
    found = manager._find_dock_widget_by_name("TestWidget")
    assert found is not None

    # toggle_menu_panel_visibility doesn't raise
    manager.toggle_menu_panel_visibility()
    manager.toggle_menu_panel_visibility()

    # set_tabbar_location and set_foreground_tabs don't raise
    manager.set_tabbar_location("North")
    manager.set_foreground_tabs(["TestWidget"])


def test_recreate_hidden_widget_and_hide_restore_cycle(make_napari_viewer):
    """Test widget reuse when hidden and full hide/restore cycle."""
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)

    menu = {"TestWidget": {"widget": DummyWidget, "location": "right"}}
    manager.initialize_menu(menu)

    dock = manager._find_dock_widget_by_name("TestWidget")
    assert dock is not None

    # Simulate hidden state for recreate path
    dock.isVisible = MagicMock(return_value=False)
    fake_parent = MagicMock()
    dock.parent = MagicMock(return_value=fake_parent)

    manager.initialize_menu(menu)
    assert "TestWidget" in manager.visible_menus
    fake_parent.show.assert_called_once()

    # Now test full hide/restore cycle with a fresh widget
    menu2 = {"A": {"widget": DummyWidget, "location": "right"}}
    manager.initialize_menu(menu2)
    dock2 = manager._find_dock_widget_by_name("A")
    dock2.isVisible = MagicMock(return_value=True)
    parent2 = MagicMock()
    dock2.parent = MagicMock(return_value=parent2)

    manager.toggle_menu_panel_visibility()
    parent2.close.assert_called_once()
    assert manager.hidden is True

    manager.toggle_menu_panel_visibility()
    parent2.show.assert_called_once()
    assert manager.hidden is False


def test_error_fallback_and_visible_tabs(make_napari_viewer):
    """Test RuntimeError fallback and _get_visible_tabs filtering."""
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)

    # RuntimeError during isVisible causes safe fallback
    bad_widget = MagicMock()
    bad_widget.isVisible.side_effect = RuntimeError("deleted")
    viewer.window.__dict__["dock_widgets"] = {"BrokenWidget": bad_widget}
    result = manager._find_dock_widget_by_name("BrokenWidget")
    assert result is None

    # Restore dock_widgets for visible tabs test
    menu = {"Visible": {"widget": DummyWidget, "location": "right"}}
    manager.initialize_menu(menu)
    dock = manager._find_dock_widget_by_name("Visible")
    dock.isVisible = MagicMock(return_value=True)

    manager.initialized_menu_widgets.add("Hidden")

    def fake_find(name):
        if name == "Visible":
            return dock
        return None

    manager._find_dock_widget_by_name = fake_find

    visible = manager._get_visible_tabs()
    assert "Visible" in visible
    assert "Hidden" not in visible


def test_foreground_tabs_and_tabbar_fallback(make_napari_viewer):
    """Test set_foreground_tabs raises correct widget and tabbar fallback."""
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)

    StartupWidget(viewer)

    qt_window = viewer.window._qt_window
    dock_widgets = qt_window.findChildren(QDockWidget)
    assert len(dock_widgets) > 0

    # set_foreground_tabs raises the correct widget
    target = dock_widgets[3]
    target_title = target.windowTitle()
    target.raise_ = MagicMock()
    manager.set_foreground_tabs([target_title])

    for dw in dock_widgets:
        if dw is target:
            dw.raise_.assert_called_once()
        else:
            assert not getattr(dw.raise_, "called", False)

    # Invalid tabbar location falls back safely (defaults to North) without raising,
    # whether or not napari has materialized any real QTabBar yet.
    tabbars = qt_window.findChildren(QTabBar)
    for tb in tabbars:
        tb.setStyleSheet = MagicMock()
        tb.setElideMode = MagicMock()

    manager.set_tabbar_location("INVALID")

    for tb in tabbars:
        tb.setStyleSheet.assert_called()
        tb.setElideMode.assert_called()


class CleanupWidget(QWidget):
    """DummyWidget that records that MenuManager gave it a chance to clean up."""

    count = 0
    cleaned_up: list[str] = []  # names of the widgets whose cleanup() ran

    def __init__(self, viewer):
        super().__init__()
        CleanupWidget.count += 1
        self.name = f"widget-{CleanupWidget.count}"

    def cleanup(self):
        # kept on the class: the widget itself is deleted right after this
        CleanupWidget.cleaned_up.append(self.name)


def test_dock_close_destroys_widget(make_napari_viewer, qtbot):
    """The 'x' on a tab must destroy the widget, not just orphan it.

    napari's remove_dock_widget deletes the QDockWidget but only detaches the widget
    it contained (setParent(None)), so without MenuManager destroying it the widget
    lives on and keeps reacting to TracksViewer signals.
    """
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)
    CleanupWidget.cleaned_up.clear()

    menu = {"TestWidget": {"widget": CleanupWidget, "location": "right"}}
    manager.initialize_menu(menu)
    widget = manager.menu_widgets["TestWidget"].widget()
    name = widget.name

    dock = viewer.window._wrapped_dock_widgets["TestWidget"]
    # `destroyed` is emitted once the widget is really gone, which takes a couple of
    # deferred deletions: waiting for the signal instead of a fixed delay keeps this
    # independent of how promptly a platform gets round to them.
    with qtbot.waitSignal(widget.destroyed, timeout=5000):
        dock.destroyOnClose()  # what the tab's close button calls

    assert CleanupWidget.cleaned_up == [name]
    assert "TestWidget" not in manager.menu_widgets
    assert "TestWidget" not in manager.initialized_menu_widgets
    assert "TestWidget" not in manager.visible_menus


def test_closing_the_viewer_does_not_raise(make_napari_viewer, qtbot):
    """Docks destroyed with their window must not trip the destroyed handler.

    Their children are gone by then, so there is nothing left to clean up - it just
    has to stay quiet, since an exception raised from a Qt signal aborts the process.
    """
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)
    manager.initialize_menu(
        {
            "WidgetA": {"widget": CleanupWidget, "location": "right"},
            "WidgetB": {"widget": CleanupWidget, "location": "right"},
        }
    )
    docks_destroyed = []
    for name in ("WidgetA", "WidgetB"):
        viewer.window._wrapped_dock_widgets[name].destroyed.connect(
            lambda *_: docks_destroyed.append(1)
        )

    viewer.close()
    qtbot.waitUntil(lambda: len(docks_destroyed) == 2, timeout=5000)


def test_real_menu_widgets_stop_following_tracks_viewer(make_napari_viewer, qtbot):
    """Destroying the docks unhooks the tree and table from the TracksViewer."""
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)
    manager.initialize_menu(
        {
            "Lineage View": MENU_WIDGETS["Lineage View"],
            "Table": MENU_WIDGETS["Table"],
        }
    )

    tree_widget = manager.menu_widgets["Lineage View"].widget()
    table_widget = manager.menu_widgets["Table"].widget()
    tracks_viewer = tree_widget.tracks_viewer
    assert tracks_viewer.tree_widget_present
    assert tracks_viewer.table_widget_present
    connected = len(tracks_viewer.tracks_updated)

    for name, widget in (("Lineage View", tree_widget), ("Table", table_widget)):
        with qtbot.waitSignal(widget.destroyed, timeout=5000):
            viewer.window._wrapped_dock_widgets[name].destroyOnClose()

    assert not tracks_viewer.tree_widget_present
    assert not tracks_viewer.table_widget_present
    assert len(tracks_viewer.tracks_updated) == connected - 2
    tracks_viewer.tracks_updated.emit(True)  # must not reach the destroyed widgets

    # re-opening gives fresh, working widgets
    manager.initialize_menu({"Lineage View": MENU_WIDGETS["Lineage View"]})
    assert manager.menu_widgets["Lineage View"].widget() is not tree_widget
    assert tracks_viewer.tree_widget_present
