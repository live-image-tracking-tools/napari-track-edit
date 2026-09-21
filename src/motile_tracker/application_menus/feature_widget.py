from __future__ import annotations

import napari
from funtracks.annotators._regionprops_annotator import (
    DEFAULT_POS_KEY,
    RegionpropsAnnotator,
)
from funtracks.features._feature import Feature
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class FeatureWidget(QWidget):
    """Widget to enable/disable RegionProps features."""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.tracks_updated.connect(self._update_checkboxes)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._toggling = False  # guard against rebuilding while handling a toggle

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.MarkdownText)

        self.box = QGroupBox("Select features")
        self.checkbox_layout = QVBoxLayout()
        self.box.setLayout(self.checkbox_layout)
        self.box.setVisible(False)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.box)
        self.layout.addStretch()
        self.setLayout(self.layout)

    def _update_checkboxes(self):
        """Update the list of available checkboxes."""

        if self._toggling:
            # no need to rebuild, the checkbox states are already correct
            return

        self._clear_layout()
        self._checkboxes.clear()

        tracks = self.tracks_viewer.tracks
        if tracks is None:
            self.box.setVisible(False)
            return

        for feature_key, feature in self._discover_features().items():
            checkbox = QCheckBox(feature["display_name"])

            checkbox.setChecked(feature_key in tracks.features)

            checkbox.toggled.connect(
                lambda checked, key=feature_key: self._on_toggled(key, checked)
            )

            self._checkboxes[feature_key] = checkbox
            self.checkbox_layout.addWidget(checkbox)

        self.box.setVisible(self.checkbox_layout.count() > 0)

    def _clear_layout(self) -> None:
        """Remove all checkboxes from the layout"""

        while self.checkbox_layout.count():
            item = self.checkbox_layout.takeAt(0)

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _discover_features(self) -> dict[str, Feature]:
        """Find all features available for the current tracks (excluding position)"""

        tracks = self.tracks_viewer.tracks

        if tracks.segmentation is not None:
            features = RegionpropsAnnotator.get_available_features(ndim=tracks.ndim)
            features.pop(DEFAULT_POS_KEY, None)
            self.label.setText(
                "*Activating the checkboxes will compute the selected feature. \n"
                "You can see these measurements in the Lineage View (choose Plot > Feature) \n"
                "and in the Table widget.*"
            )

        else:
            features = {}
            self.label.setText(
                "*Feature measurements are only supported if you are using a segmentation layer.*"
            )

        return features

    def _on_toggled(self, feature_key: str, checked: bool) -> None:
        """Enable/disable features on tracks

        Args:
            feature_key (str): the feature the enable/disable
            checked (bool): whether to enable (True) or disable (False)
        """

        tracks = self.tracks_viewer.tracks

        if checked:
            tracks.enable_features([feature_key])
        else:
            tracks.disable_features([feature_key])

        self._toggling = True
        try:
            self.tracks_viewer.update_track_df(initialization=False, refresh_view=False)
            self.tracks_viewer.tracks_updated.emit(False)
        finally:
            self._toggling = False
