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

        self.tracks_list = TracksViewer.get_instance(viewer).tracks_list

        layout = QVBoxLayout()
        layout.addWidget(self.tracks_list)

        self.setLayout(layout)

    def cleanup(self) -> None:
        """Detach the tracks list before this widget is destroyed, because it is
        shared with other widgets and must outlive this one.
        """
        self.tracks_list.setParent(None)
