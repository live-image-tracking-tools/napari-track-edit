"""Tests for WelcomeWidget: initialization and content."""

from qtpy.QtWidgets import QLabel, QTextBrowser

from napari_track_edit.application_menus.welcome_widget import WelcomeWidget


def test_welcome_widget_initializes(qtbot):
    class DummyViewer:
        pass

    widget = WelcomeWidget(DummyViewer())
    assert widget is not None
    # Should have a layout
    assert widget.layout() is not None
    # Should contain a QLabel with 'Napari Track Edit', and one showing the logo
    labels = widget.findChildren(QLabel)
    assert any("Napari Track Edit" in label.text() for label in labels)
    assert any(
        label.pixmap() is not None and not label.pixmap().isNull() for label in labels
    )
    # Should contain at least one QTextBrowser
    found_browser = False
    for i in range(widget.layout().count()):
        item = widget.layout().itemAt(i).widget()
        if isinstance(item, QTextBrowser):
            found_browser = True
    assert found_browser
