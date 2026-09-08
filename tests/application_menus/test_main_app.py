"""Tests for main_app.py: StartupWidget, MainAppWidget, and single menu widget classes."""

from qtpy.QtWidgets import QWidget

from motile_tracker.application_menus.main_app import (
    MENU_WIDGETS,
    EditingGroupWidget,
    EditingSelection_LauncherWidget,
    GettingStarted_LauncherWidget,
    Groups_LauncherWidget,
    LineageView_LauncherWidget,
    MainAppWidget,
    StartupWidget,
    Table_LauncherWidget,
    Tracking_LauncherWidget,
    TrackingGroupWidget,
    TrackList_LauncherWidget,
    Visualization_LauncherWidget,
)


def test_startupwidget_initializes_all_tabs(make_napari_viewer):
    viewer = make_napari_viewer()
    widget = StartupWidget(viewer)
    assert isinstance(widget, QWidget)
    # Should initialize all menu widgets
    assert len(viewer.window.dock_widgets) == len(MENU_WIDGETS)


def test_main_widget(make_napari_viewer):
    viewer = make_napari_viewer()
    widget = MainAppWidget(viewer)
    assert isinstance(widget, StartupWidget)
    assert len(viewer.window.dock_widgets) == len(MENU_WIDGETS)


def test_single_menu_widgets(qtbot, make_napari_viewer):
    # Each single menu widget should only initialize one docked widget
    for WidgetClass in [
        GettingStarted_LauncherWidget,
        Tracking_LauncherWidget,
        TrackList_LauncherWidget,
        EditingSelection_LauncherWidget,
        Visualization_LauncherWidget,
        Groups_LauncherWidget,
        Table_LauncherWidget,
        LineageView_LauncherWidget,
    ]:
        n_docked_widgets = 0
        viewer = make_napari_viewer()
        widget = WidgetClass(viewer)
        n_docked_widgets += 1
        assert isinstance(widget, StartupWidget)
        assert len(viewer.window.dock_widgets) == n_docked_widgets


def test_tracking_and_editing_group_widgets(qtbot, make_napari_viewer):
    viewer = make_napari_viewer()
    tracking = TrackingGroupWidget(viewer)
    editing = EditingGroupWidget(viewer)
    assert isinstance(tracking, StartupWidget)
    assert isinstance(editing, StartupWidget)
    # Should initialize subset of widgets
    assert len(viewer.window.dock_widgets) == 7
