import napari
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from motile_tracker.application_menus.tracking_from_scratch_widget import (
    TrackingFromScratch,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TrackListWidget(QWidget):
    """Creates or finds a TracksViewer and displays its TrackList widget, with the
    controls to create an empty tracking tree (tracking from scratch) above it.
    This is only used in case the user wants to open the trackslist from the plugins
    menu.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracking_from_scratch = TrackingFromScratch(viewer)

        layout = QVBoxLayout()
        layout.addWidget(self.tracking_from_scratch)
        layout.addWidget(tracks_viewer.tracks_list)

        self.setLayout(layout)
