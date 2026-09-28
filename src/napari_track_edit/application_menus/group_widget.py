import napari
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


class GroupWidget(QWidget):
    """Creates or finds a TracksViewer and displays its Collection widget.
    This is only used in case the user wants to open the groups from the plugins
    menu.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        tracks_viewer = TracksViewer.get_instance(viewer)
        layout = QVBoxLayout()
        layout.addWidget(tracks_viewer.get_collection_widget())

        self.setLayout(layout)
