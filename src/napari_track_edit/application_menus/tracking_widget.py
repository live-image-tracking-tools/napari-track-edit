import napari
from qtpy.QtWidgets import QTabWidget, QWidget

from napari_track_edit.application_menus.tracking_from_scratch_widget import (
    TrackingFromScratch,
)

# Ordered (name, widget_cls) pairs added as tabs to every new TrackingWidget.
# "Track from Scratch" ships built in; downstream packages that bundle their own
# tracking widget (e.g. a standalone motile_tracker, which depends on
# napari-track-edit and so cannot be imported from here) can add to or replace
# these via register_tracking_tab() at import time.
_TRACKING_TABS: list[tuple[str, type[QWidget]]] = [
    ("Track from Scratch", TrackingFromScratch),
]


def register_tracking_tab(
    name: str, widget_cls: type[QWidget], index: int | None = None
) -> None:
    """Register a widget class to appear as a tab in every TrackingWidget.

    Meant to be called once at import time by a package that wants to contribute a
    way of creating tracks. The widget class must accept a single `viewer:
    napari.Viewer` argument, matching TrackingFromScratch.

    If a tab with this name is already registered, it is replaced in place rather
    than duplicated. `index` is ignored when replacing.

    Args:
        name (str): The tab's display name.
        widget_cls (type[QWidget]): Widget class to instantiate per TrackingWidget,
            called as `widget_cls(viewer)`.
        index (int | None): Position to insert a new tab at. Defaults to appending
            after all previously registered tabs. Ignored if `name` already exists.
    """
    for i, (existing_name, _) in enumerate(_TRACKING_TABS):
        if existing_name == name:
            _TRACKING_TABS[i] = (name, widget_cls)
            return
    entry = (name, widget_cls)
    if index is None:
        _TRACKING_TABS.append(entry)
    else:
        _TRACKING_TABS.insert(index, entry)


class TrackingWidget(QTabWidget):
    """Tab widget holding the different ways of creating tracks.

    "Track from Scratch" (manual tracking) is always present; other tabs are
    contributed by downstream packages via register_tracking_tab() and appear in
    registration order.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tabs: dict[str, QWidget] = {}
        for name, widget_cls in _TRACKING_TABS:
            widget = widget_cls(viewer)
            self.tabs[name] = widget
            self.addTab(widget, name)

        # extra vertical padding so the tab titles are not cut off at the bottom
        self.setStyleSheet("QTabBar::tab { padding: 5px 6px; }")
