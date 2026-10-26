from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication

from napari_track_edit._nte_app import NTEApp


def _press_slash(qtbot, viewer) -> None:
    """Activate the viewer's window and press "/" on its canvas."""
    qt_window = viewer.window._qt_window
    qt_window.show()
    # Set the active window through Qt directly: activateWindow() depends on the OS
    # granting focus, which is unreliable in tests.
    QApplication.setActiveWindow(qt_window)
    qtbot.waitUntil(qt_window.isActiveWindow)
    qtbot.keyClick(viewer.window._qt_viewer.canvas.native, Qt.Key_Slash)


def test_hide_panels_shortcut_fires(make_napari_viewer, qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(NTEApp, "hide_panels", lambda self: calls.append(self))

    viewer = make_napari_viewer()
    app = NTEApp.get_instance(viewer)

    _press_slash(qtbot, viewer)
    assert calls == [app]


def test_hide_panels_shortcut_with_two_viewers(make_napari_viewer, qtbot, monkeypatch):
    """With two viewers open, "/" only toggles the panels of the active viewer."""
    calls = []
    monkeypatch.setattr(NTEApp, "hide_panels", lambda self: calls.append(self))

    viewer1 = make_napari_viewer()
    app1 = NTEApp.get_instance(viewer1)
    viewer2 = make_napari_viewer()
    app2 = NTEApp.get_instance(viewer2)

    _press_slash(qtbot, viewer1)
    assert calls == [app1]

    _press_slash(qtbot, viewer2)
    assert calls == [app1, app2]
