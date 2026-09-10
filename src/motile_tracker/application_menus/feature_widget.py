from __future__ import annotations

import napari
from fonticon_fa6 import FA6S
from funtracks.annotators._regionprops_annotator import (
    DEFAULT_INTENSITY_KEY,
    DEFAULT_POS_KEY,
    RegionpropsAnnotator,
)
from funtracks.features._feature import Feature
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon as qticon

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class IntensityLayerDialog(QDialog):
    """Pick the image layers to measure mean intensity in.

    Args:
        layers: The eligible image layers, in viewer order.
        selected: The layers to tick. None ticks all of them, which is the default
            for a first-time choice.
        parent: The widget the dialog belongs to.
    """

    def __init__(
        self,
        layers: list[napari.layers.Image],
        selected: list[napari.layers.Image] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Select intensity layers")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Measure mean intensity in these image layers:"))

        self._checkboxes: list[tuple[napari.layers.Image, QCheckBox]] = []
        for layer in layers:
            checkbox = QCheckBox(layer.name)
            checkbox.setChecked(selected is None or layer in selected)
            layout.addWidget(checkbox)
            self._checkboxes.append((layer, checkbox))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    @property
    def selected_layers(self) -> list[napari.layers.Image]:
        """The ticked layers, in viewer order."""

        return [layer for layer, checkbox in self._checkboxes if checkbox.isChecked()]


class FeatureWidget(QWidget):
    """Widget to enable/disable RegionProps features.

    Mean intensity needs pixel values, so it has one checkbox for the feature plus a
    refresh button that opens a dialog to choose which image layers to measure. The
    chosen layers' data is handed to the tracks, which holds it (lazily) for as long as
    the feature is enabled, so the choice survives a rename. Renaming a measured layer
    renames its column, and removing one drops its measurement.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.tracks_updated.connect(self._update_checkboxes)
        self._checkboxes: dict[str, QCheckBox] = {}
        self.intensity_checkbox: QCheckBox | None = None
        # The layer objects, not their names, so that a rename cannot orphan them
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

        # Measured layers can disappear while the feature is on; new ones need no
        # watching, since the dialog reads the layer list each time it opens.
        self.viewer.layers.events.removed.connect(self._on_layer_removed)

    def _update_checkboxes(self):
        """Update the list of available checkboxes."""

        if self._toggling:
            # no need to rebuild, the checkbox states are already correct
            return

        self._clear_layout()
        self._checkboxes.clear()
        self.intensity_checkbox = None

        tracks = self.tracks_viewer.tracks
        if tracks is not self._tracks:
            self._tracks = tracks
            self._forget_intensity_layers()
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

        if tracks.segmentation is not None:
            self.checkbox_layout.addWidget(self._intensity_row())

        self.box.setVisible(self.checkbox_layout.count() > 0)

    def _intensity_row(self) -> QWidget:
        """The mean intensity checkbox, with a button to change the layers measured."""

        tracks = self.tracks_viewer.tracks

        self.intensity_checkbox = QCheckBox("Mean intensity")
        self.intensity_checkbox.setChecked(DEFAULT_INTENSITY_KEY in tracks.features)
        self.intensity_checkbox.setToolTip(
            "Measure the mean intensity of each detection in the image layers you select"
        )
        self.intensity_checkbox.toggled.connect(self._on_intensity_toggled)

        self.intensity_update_btn = QPushButton(
            icon=qticon(FA6S.arrows_rotate, color="white")
        )
        self.intensity_update_btn.setFixedSize(20, 20)
        self.intensity_update_btn.setToolTip("Change which image layers are measured")
        self.intensity_update_btn.clicked.connect(self._on_update_intensity_layers)

        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.intensity_checkbox)
        layout.addWidget(self.intensity_update_btn)
        layout.addStretch()
        row.setLayout(layout)
        return row

    def _clear_layout(self) -> None:
        """Remove all checkboxes from the layout"""

        while self.checkbox_layout.count():
            item = self.checkbox_layout.takeAt(0)

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _discover_features(self) -> dict[str, Feature]:
        """Find all features available for the current tracks.

        Excludes position (always computed) and intensity (which has its own row, since
        it also needs the layers to measure).
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

    def _on_intensity_toggled(self, checked: bool) -> None:
        """Turn mean intensity on (for the chosen layers) or off.

        The layers are asked for the first time the feature is switched on; after that
        the choice is reused, and changed with the update button.

        Args:
            checked (bool): whether to enable (True) or disable (False)
        """

        if not checked:
            self._disable_intensity()
            return

        layers = self._live_intensity_layers()
        if not layers:
            layers = self._ask_intensity_layers()
            if not layers:
                # cancelled, or nothing to measure: leave the feature off
                self._set_intensity_checked(False)
                return

        self._apply_intensity_layers(layers)

    def _disable_intensity(self) -> None:
        """Stop measuring, keeping the chosen layers for the next time it is switched
        back on."""

        tracks = self.tracks_viewer.tracks
        if tracks is None or DEFAULT_INTENSITY_KEY not in tracks.features:
            return
        tracks.disable_features([DEFAULT_INTENSITY_KEY])
        self._refresh_views()

    def _on_update_intensity_layers(self) -> None:
        """Reopen the layer choice and measure whatever comes back."""

        layers = self._ask_intensity_layers()
        if layers is None:
            return  # cancelled: leave the current measurement alone
        self._apply_intensity_layers(layers)

    def _ask_intensity_layers(self) -> list[napari.layers.Image] | None:
        """Ask which image layers to measure.

        Returns:
            The chosen layers (possibly none, meaning "stop measuring"), or None if
            the user cancelled or there is nothing eligible to measure.
        """

        eligible = self._matching_image_layers()
        if not eligible:
            QMessageBox.information(
                self,
                "No image layers to measure",
                "Mean intensity needs an image layer with the same shape as the "
                "segmentation.",
            )
            return None

        current = self._live_intensity_layers()
        dialog = IntensityLayerDialog(eligible, selected=current or None, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return None
        return dialog.selected_layers

    def _apply_intensity_layers(self, layers: list[napari.layers.Image]) -> None:
        """Measure mean intensity in the given layers, or stop measuring if there are
        none.

        Args:
            layers: the image layers to measure, in the order their columns appear.
        """

        tracks = self.tracks_viewer.tracks
        if tracks is None or tracks.segmentation is None:
            return

        self._remember_intensity_layers(layers)

        if layers:
            tracks.set_intensity_images(
                [layer.data for layer in layers],
                channel_names=[layer.name for layer in layers],
            )
            if DEFAULT_INTENSITY_KEY not in tracks.features:
                tracks.enable_features([DEFAULT_INTENSITY_KEY])
        else:
            # Disable before clearing: computing intensity without an image warns
            if DEFAULT_INTENSITY_KEY in tracks.features:
                tracks.disable_features([DEFAULT_INTENSITY_KEY])
            tracks.set_intensity_images(None)

        self._set_intensity_checked(bool(layers))
        self._refresh_views()

    def _set_intensity_checked(self, checked: bool) -> None:
        """Show the feature's state without re-entering the toggle handler."""

        if self.intensity_checkbox is None:
            return
        blocked = self.intensity_checkbox.blockSignals(True)
        self.intensity_checkbox.setChecked(checked)
        self.intensity_checkbox.blockSignals(blocked)

    def _refresh_views(self) -> None:
        """Rebuild the track dataframe and notify the other views of new features."""

        self._toggling = True
        try:
            self.tracks_viewer.update_track_df(initialization=False, refresh_view=False)
            self.tracks_viewer.tracks_updated.emit(False)
        finally:
            self._toggling = False

    def _live_intensity_layers(self) -> list[napari.layers.Image]:
        """The measured layers that are still in the viewer."""

        present = {id(layer) for layer in self.viewer.layers}
        return [layer for layer in self._intensity_layers if id(layer) in present]

    def _remember_intensity_layers(self, layers: list[napari.layers.Image]) -> None:
        """Track the measured layers, and listen for renames of exactly those."""

        self._intensity_layers = list(layers)

        wanted = set(layers)
        for layer in self._name_connected - wanted:
            layer.events.name.disconnect(self._on_layer_renamed)
        for layer in wanted - self._name_connected:
            layer.events.name.connect(self._on_layer_renamed)
        self._name_connected = wanted

    def _forget_intensity_layers(self) -> None:
        """Drop the measured layers, e.g. when a different Tracks is loaded."""

        self._remember_intensity_layers([])

    def _on_layer_removed(self, event=None) -> None:
        """A removed layer cannot be measured: drop it and remeasure the rest."""

        live = self._live_intensity_layers()
        if len(live) == len(self._intensity_layers):
            return
        if self._measuring_intensity():
            self._apply_intensity_layers(live)
        else:
            # Switched off: just forget it, there is nothing being measured to update
            self._remember_intensity_layers(live)

    def _on_layer_renamed(self, event=None) -> None:
        """A measured layer's name is its column name, so push the new one through."""

        if self._measuring_intensity():
            self._apply_intensity_layers(self._live_intensity_layers())

    def _measuring_intensity(self) -> bool:
        """Whether mean intensity is currently switched on."""

        tracks = self.tracks_viewer.tracks
        return tracks is not None and DEFAULT_INTENSITY_KEY in tracks.features

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
