import napari
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TrackListWidget(QWidget):
    """Creates or finds a TracksViewer and displays its TrackList widget.
    This is only used in case the user wants to open the trackslist from the plugins
    menu. The controls to create an empty tracking tree (tracking from scratch) live in
    the Tracking menu.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        tracks_viewer = TracksViewer.get_instance(viewer)

        layout = QVBoxLayout()
        layout.addWidget(tracks_viewer.tracks_list)

        self.setLayout(layout)
