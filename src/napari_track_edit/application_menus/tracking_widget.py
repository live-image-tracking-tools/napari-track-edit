import napari
from qtpy.QtWidgets import QTabWidget

from napari_track_edit.application_menus.tracking_from_scratch_widget import (
    TrackingFromScratch,
)
from napari_track_edit.motile.menus.motile_widget import MotileWidget


class TrackingWidget(QTabWidget):
    """Tab widget holding the different ways of creating tracks: automatic tracking
    with motile (MotileWidget) and manual tracking from scratch (TrackingFromScratch).
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.motile_widget = MotileWidget(viewer)
        self.tracking_from_scratch = TrackingFromScratch(viewer)

        self.addTab(self.motile_widget, "Track with Motile")
        self.addTab(self.tracking_from_scratch, "Track from Scratch")
