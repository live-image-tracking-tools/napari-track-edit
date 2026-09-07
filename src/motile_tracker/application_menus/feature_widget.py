from __future__ import annotations

import napari
from funtracks.annotators._regionprops_annotator import (
    DEFAULT_INTENSITY_KEY,
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
    """Widget to enable/disable RegionProps features.

    For each image layer that matches the segmentation's shape, a checkbox is shown to
    activate measuring its mean intensity. The reference to the intensity images is stored
    on the tracks, and is updated when checkboxes are deactivated, or when the source layer
    is removed.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.tracks_updated.connect(self._update_checkboxes)
        self._checkboxes: dict[str, QCheckBox] = {}
        # Intensity checkboxes are keyed by layer object, not by name, so that they
        # survive renames.
        self._intensity_checkboxes: dict[napari.layers.Image, QCheckBox] = {}
        self._intensity_layers: list[napari.layers.Image] = []
        self._name_connected: set[napari.layers.Image] = set()
        self._tracks = None  # to notice when a different Tracks is loaded
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

        layers_events = self.viewer.layers.events
        layers_events.inserted.connect(self._on_layers_changed)
        layers_events.removed.connect(self._on_layers_changed)
        layers_events.reordered.connect(self._on_layers_changed)
        self._sync_layer_name_events()

    def _update_checkboxes(self):
        """Update the list of available checkboxes."""

        if self._toggling:
            # no need to rebuild, the checkbox states are already correct
            return

        self._clear_layout()
        self._checkboxes.clear()
        self._intensity_checkboxes.clear()

        tracks = self.tracks_viewer.tracks
        if tracks is not self._tracks:
            self._tracks = tracks
            self._intensity_layers = []
        if tracks is None:
            return

        for feature_key, feature in self._discover_features().items():
            checkbox = QCheckBox(feature["display_name"])

            checkbox.setChecked(feature_key in tracks.features)

            checkbox.toggled.connect(
                lambda checked, key=feature_key: self._on_toggled(key, checked)
            )

            self._checkboxes[feature_key] = checkbox
            self.checkbox_layout.addWidget(checkbox)

        # One mean intensity checkbox per image layer that matches the segmentation
        for layer in self._matching_image_layers():
            checkbox = QCheckBox(f"Mean intensity ({layer.name})")

            checkbox.setChecked(layer in self._intensity_layers)

            checkbox.toggled.connect(
                lambda checked, lyr=layer: self._on_intensity_toggled(lyr, checked)
            )

            self._intensity_checkboxes[layer] = checkbox
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
        """Find all features available for the current tracks.

        Excludes position (always computed) and intensity (driven by the per-layer
        checkboxes instead).
        """

        tracks = self.tracks_viewer.tracks

        if tracks.segmentation is not None:
            features = RegionpropsAnnotator.get_available_features(ndim=tracks.ndim)
            features.pop(DEFAULT_POS_KEY, None)
            features.pop(DEFAULT_INTENSITY_KEY, None)
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

        self._refresh_views()

    def _on_intensity_toggled(self, layer: napari.layers.Image, checked: bool) -> None:
        """Add or remove an image layer as an intensity channel, and remeasure.

        Args:
            layer (napari.layers.Image): the image layer to measure (or stop measuring)
            checked (bool): whether to add (True) or remove (False) the layer
        """

        if checked and layer not in self._intensity_layers:
            self._intensity_layers.append(layer)
        elif not checked and layer in self._intensity_layers:
            self._intensity_layers.remove(layer)

        self._apply_intensity_layers()
        self._refresh_views()

    def _apply_intensity_layers(self) -> None:
        """Push the checked image layers to the tracks and (re)compute intensity."""

        tracks = self.tracks_viewer.tracks
        if tracks is None or tracks.segmentation is None:
            return

        # Drop any layers that have since been removed from the viewer
        present = {id(layer) for layer in self.viewer.layers}
        self._intensity_layers = [
            layer for layer in self._intensity_layers if id(layer) in present
        ]

        if self._intensity_layers:
            tracks.set_intensity_images(
                [layer.data for layer in self._intensity_layers],
                channel_names=[layer.name for layer in self._intensity_layers],
            )
            if DEFAULT_INTENSITY_KEY not in tracks.features:
                tracks.enable_features([DEFAULT_INTENSITY_KEY])
        else:
            # Disable before clearing: computing intensity without an image warns
            if DEFAULT_INTENSITY_KEY in tracks.features:
                tracks.disable_features([DEFAULT_INTENSITY_KEY])
            tracks.set_intensity_images(None)

    def _refresh_views(self) -> None:
        """Rebuild the track dataframe and notify the other views of new features."""

        self._toggling = True
        try:
            self.tracks_viewer.update_track_df(initialization=False, refresh_view=False)
            self.tracks_viewer.tracks_updated.emit(False)
        finally:
            self._toggling = False

    def _on_layers_changed(self, event=None) -> None:
        """Keep the intensity checkboxes in sync with the napari layer list."""

        self._sync_layer_name_events()

        # Only a removed layer changes what is measured; an added one just gets a
        # checkbox.
        present = {id(layer) for layer in self.viewer.layers}
        if any(id(layer) not in present for layer in self._intensity_layers):
            self._apply_intensity_layers()
            self._refresh_views()

        self._update_checkboxes()

    def _on_layer_renamed(self, event) -> None:
        """A layer was renamed: refresh the labels, and the feature names if measured."""

        layer = getattr(event, "source", None)
        if layer in self._intensity_layers:
            # The channel names are the feature's column names, so push them through
            self._apply_intensity_layers()
            self._refresh_views()

        self._update_checkboxes()

    def _sync_layer_name_events(self) -> None:
        """Listen to name changes on the image layers currently in the viewer."""

        current = {
            layer
            for layer in self.viewer.layers
            if isinstance(layer, napari.layers.Image)
        }
        for layer in self._name_connected - current:
            layer.events.name.disconnect(self._on_layer_renamed)
        for layer in current - self._name_connected:
            layer.events.name.connect(self._on_layer_renamed)
        self._name_connected = current

    def _matching_image_layers(self) -> list[napari.layers.Image]:
        """Image layers with the same shape as the segmentation, in viewer order."""

        tracks = self.tracks_viewer.tracks
        if tracks is None or tracks.segmentation is None:
            return []

        seg_shape = tuple(tracks.segmentation.shape)
        return [
            layer
            for layer in self.viewer.layers
            if isinstance(layer, napari.layers.Image)
            and tuple(getattr(layer.data, "shape", ())) == seg_shape
        ]
