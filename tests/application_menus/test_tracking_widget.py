"""Tests for TrackingWidget - the tab widget holding the ways of making tracks."""

from qtpy.QtWidgets import QGroupBox, QWidget

from napari_track_edit.application_menus.tracking_from_scratch_widget import (
    TrackingFromScratch,
)
from napari_track_edit.application_menus.tracking_widget import (
    TrackingWidget,
    register_tracking_tab,
)


def test_tabs(make_napari_viewer):
    """Track from Scratch is the built-in tab."""

    viewer = make_napari_viewer()
    widget = TrackingWidget(viewer)

    assert widget.count() == 1
    assert widget.widget(0) is widget.tabs["Track from Scratch"]
    assert isinstance(widget.tabs["Track from Scratch"], TrackingFromScratch)
    assert widget.tabText(0) == "Track from Scratch"


def test_register_tracking_tab_adds_tab(make_napari_viewer):
    """A registered tab appears in every subsequently created TrackingWidget."""

    class DummyWidget(QWidget):
        def __init__(self, viewer):
            super().__init__()
            self.viewer = viewer

    register_tracking_tab("Dummy", DummyWidget)
    try:
        viewer = make_napari_viewer()
        widget = TrackingWidget(viewer)

        assert widget.count() == 2
        assert widget.tabText(1) == "Dummy"
        assert isinstance(widget.tabs["Dummy"], DummyWidget)
    finally:
        from napari_track_edit.application_menus.tracking_widget import (
            _TRACKING_TABS,
        )

        _TRACKING_TABS[:] = [
            (name, cls) for name, cls in _TRACKING_TABS if name != "Dummy"
        ]


def test_from_scratch_tab_does_not_stretch(make_napari_viewer, qtbot):
    """The from-scratch controls stay at their natural height instead of being
    stretched over the whole tab, which is what a QVBoxLayout without a trailing
    stretch does to its only widget."""

    viewer = make_napari_viewer()
    widget = TrackingWidget(viewer)
    qtbot.addWidget(widget)
    widget.resize(300, 900)
    widget.show()
    qtbot.waitExposed(widget)

    tracking_from_scratch = widget.tabs["Track from Scratch"]
    box = tracking_from_scratch.findChild(QGroupBox)
    assert box is not None
    # a couple of pixels of slack for layout spacing/margins
    assert box.height() <= box.sizeHint().height() + 2
    assert box.height() < tracking_from_scratch.height() / 2
