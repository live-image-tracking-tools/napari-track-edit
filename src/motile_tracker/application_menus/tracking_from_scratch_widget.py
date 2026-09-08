import napari
from funtracks.data_model import SolutionTracks
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from napari.layers import Image, Labels
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.application_menus.layer_dropdown import LayerDropdown
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TrackingFromScratch(QWidget):
    """Widget to create an empty tracking tree (with either point or label tracks), to
    track from scratch. The tree starts out without any nodes; nodes are added by
    manually annotating in the track layers."""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        exp = QLabel()
        exp.setWordWrap(True)
        exp.setTextFormat(Qt.MarkdownText)
        exp.setText(
            "*Create an empty tree with either point or label tracks. The array size is "
            "taken from the selected Image or Labels layer.*"
        )

        create_box = QGroupBox("Create empty tracks")
        create_layout = QVBoxLayout(create_box)
        create_layout.addWidget(exp)
        create_layout.addWidget(QLabel("Select an Image or Labels layer"))
        # follow_active=False: the dropdown should only change when the user explicitly
        # picks a layer from it, not when the active layer in the viewer changes.
        self.size_layer_dropdown = LayerDropdown(
            self.viewer, (Image, Labels), follow_active=False
        )
        self.size_layer_dropdown.layer_changed.connect(self._update_buttons)
        create_layout.addWidget(self.size_layer_dropdown)

        start_row = QHBoxLayout()
        self.start_points_btn = QPushButton("Track with Points")
        self.start_points_btn.clicked.connect(lambda: self._start_tracking("points"))
        self.start_labels_btn = QPushButton("Track with Labels")
        self.start_labels_btn.clicked.connect(lambda: self._start_tracking("labels"))
        start_row.addWidget(self.start_points_btn)
        start_row.addWidget(self.start_labels_btn)
        create_layout.addLayout(start_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(create_box)

        self._update_buttons()

    def _update_buttons(self, *args) -> None:
        """Enable the start buttons only when a size layer is selected."""

        has_size = self.size_layer_dropdown.selected_layer is not None
        self.start_points_btn.setEnabled(has_size)
        self.start_labels_btn.setEnabled(has_size)

    def _start_tracking(self, mode: str) -> None:
        """Create a new empty tree with empty TrackPoints/TrackGraph layers (and a
        TrackLabels layer for ``mode == 'labels'``). The array size is taken from the
        selected Image/Labels layer.

        Args:
            mode (str): "points" to track with points, "labels" to track with a
                segmentation.
        """

        layer = self.size_layer_dropdown.selected_layer
        if layer is None:
            return

        if mode == "labels":
            # an empty segmentation-backed graph: registering the 'mask' attribute and
            # the segmentation shape makes SolutionTracks expose an (empty) segmentation,
            # so a TrackLabels layer is created and grows as labels are added.
            graph = create_empty_graphview_graph(
                node_attributes=["pos", "area", "mask", "bbox"],
                position_attrs=["pos"],
                ndim=layer.data.ndim,
            )
            graph._update_metadata(segmentation_shape=layer.data.shape)
        else:
            graph = create_empty_graphview_graph(
                node_attributes=["pos"],
                position_attrs=["pos"],
                ndim=layer.data.ndim,
            )

        tracks = SolutionTracks(
            graph=graph,
            scale=layer.scale,
            ndim=layer.ndim,
            time_attr="t",
            pos_attr="pos",
        )
        self.tracks_viewer.tracks_list.add_tracks(tracks, f"{layer.name}_manual_tracks")
        self.tracks_viewer.set_new_track_id()
