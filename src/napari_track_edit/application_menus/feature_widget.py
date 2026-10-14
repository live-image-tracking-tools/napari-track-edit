from __future__ import annotations

import napari
import numpy as np
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
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon as qticon

from napari_track_edit.application_menus.intensity_region_preview import (
    IntensityRegionPreview,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


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

    Without a segmentation, mean intensity is the only feature: it is measured in a
    disk (2D) or sphere (3D) around each point, with a diameter in scaled (world) units
    set below the checkbox. Editing the diameter only updates a preview layer that
    outlines the region around every point; nothing is measured until the new diameter
    is confirmed.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.tracks_updated.connect(self._update_checkboxes)
        self._checkboxes: dict[str, QCheckBox] = {}
        self.intensity_checkbox: QCheckBox | None = None
        self.diameter_spinbox: QDoubleSpinBox | None = None
        self.diameter_confirm_btn: QPushButton | None = None
        self.preview_btn: QPushButton | None = None
        # The diameter shown in the preview, before it is confirmed
        self._pending_diameter: float | None = None
        self.preview = IntensityRegionPreview(viewer, self.tracks_viewer)
        self.preview.removed.connect(self._on_preview_removed)
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
        self.diameter_spinbox = None
        self.diameter_confirm_btn = None
        self.preview_btn = None

        tracks = self.tracks_viewer.tracks
        if tracks is not self._tracks:
            self._tracks = tracks
            self._forget_intensity_layers()
            self._pending_diameter = None
            self.preview.hide()
        else:
            # nodes may have been added, moved or deleted
            self.preview.refresh()
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

        if tracks.intensity_annotator is not None:
            self.checkbox_layout.addWidget(self._intensity_row())

        self.box.setVisible(self.checkbox_layout.count() > 0)

    def _intensity_row(self) -> QWidget:
        """The mean intensity checkbox, with a button to change the layers measured,
        and for point tracks the diameter to measure in."""

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

        top = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.intensity_checkbox)
        layout.addWidget(self.intensity_update_btn)
        layout.addStretch()
        top.setLayout(layout)

        if tracks.segmentation is not None:
            return top

        self.intensity_checkbox.setToolTip(
            "Measure the mean intensity in a disk (2D) or sphere (3D) around each "
            "point, in the image layers you select"
        )
        row = QWidget()
        row_layout = QVBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(top)
        row_layout.addWidget(self._diameter_row())
        row.setLayout(row_layout)
        return row

    def _diameter_row(self) -> QWidget:
        """The diameter of the disk/sphere to measure point intensity in, with a
        preview toggle and a button to confirm a new value."""

        tracks = self.tracks_viewer.tracks
        if self._pending_diameter is None:
            self._pending_diameter = tracks.intensity_diameter

        self.diameter_spinbox = QDoubleSpinBox()
        self.diameter_spinbox.setDecimals(2)
        self.diameter_spinbox.setRange(0.01, 10000)
        self.diameter_spinbox.setValue(self._pending_diameter)
        self.diameter_spinbox.setToolTip(
            "Diameter of the disk (2D) or sphere (3D) around each point to measure the "
            "mean intensity in, in scaled (world) units"
        )
        self.diameter_spinbox.valueChanged.connect(self._on_diameter_changed)

        self.preview_btn = QPushButton(icon=qticon(FA6S.eye, color="white"))
        self.preview_btn.setFixedSize(20, 20)
        self.preview_btn.setCheckable(True)
        self.preview_btn.setChecked(self.preview.is_shown)
        self.preview_btn.setToolTip("Show the region measured around each point")
        self.preview_btn.toggled.connect(self._on_preview_toggled)

        self.diameter_confirm_btn = QPushButton("Confirm")
        self.diameter_confirm_btn.setToolTip(
            "Use this diameter, remeasuring the intensity if it is switched on"
        )
        self.diameter_confirm_btn.clicked.connect(self._confirm_diameter)
        self._update_confirm_button()

        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Diameter:"))
        layout.addWidget(self.diameter_spinbox)
        layout.addWidget(self.preview_btn)
        layout.addWidget(self.diameter_confirm_btn)
        layout.addStretch()
        row.setLayout(layout)
        return row

    def _on_diameter_changed(self, diameter: float) -> None:
        """Preview the new diameter, without measuring anything yet."""

        self._pending_diameter = diameter
        self._update_confirm_button()
        if self.preview.is_shown:
            self.preview.show(diameter)
        else:
            self.preview_btn.setChecked(True)

    def _update_confirm_button(self) -> None:
        """Only offer to confirm a diameter that differs from the one in use."""

        tracks = self.tracks_viewer.tracks
        if self.diameter_confirm_btn is None or tracks is None:
            return
        self.diameter_confirm_btn.setEnabled(
            tracks.intensity_diameter is not None
            and not np.isclose(self._pending_diameter, tracks.intensity_diameter)
        )

    def _confirm_diameter(self) -> None:
        """Use the previewed diameter, remeasuring if intensity is switched on."""

        tracks = self.tracks_viewer.tracks
        if tracks is None or tracks.point_intensity_annotator is None:
            return
        tracks.set_intensity_diameter(self._pending_diameter)
        self._update_confirm_button()
        if self._measuring_intensity():
            self._refresh_views()

    def _on_preview_toggled(self, checked: bool) -> None:
        """Show or hide the preview of the measured region."""

        if checked:
            self.preview.show(self._pending_diameter)
        else:
            self.preview.hide()

    def _on_preview_removed(self) -> None:
        """The user deleted the preview layer: show the preview as off."""

        if self.preview_btn is not None:
            blocked = self.preview_btn.blockSignals(True)
            self.preview_btn.setChecked(False)
            self.preview_btn.blockSignals(blocked)

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
                "*Without a segmentation layer, only the mean intensity can be measured, "
                "in a disk (2D) or sphere (3D) of the given diameter around each point.*"
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

        eligible, requirement = self._matching_image_layers()
        if not eligible:
            QMessageBox.information(
                self,
                "No image layers to measure",
                f"No image layers {requirement}. \n\nIf you have multichannel data, "
                "please split the stack into the different channels and try again.",
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
        if tracks is None or tracks.intensity_annotator is None:
            return

        if layers:
            try:
                tracks.set_intensity_images(
                    [layer.data for layer in layers],
                    channel_names=[layer.name for layer in layers],
                )
            except ValueError as e:
                # e.g. point tracks measured in layers of different shapes
                QMessageBox.warning(self, "Cannot measure intensity", str(e))
                self._set_intensity_checked(self._measuring_intensity())
                return

        self._remember_intensity_layers(layers)

        if layers:
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

    def _matching_image_layers(self) -> tuple[list[napari.layers.Image], str]:
        """Image layers that intensity can be measured in, in viewer order.

        With a segmentation, these are the layers with the same shape. Without
        segmentation, any layer with the dimensions of the tracks can be used.

        Returns:
            The eligible layers, and a description of what makes a layer eligible.
        """

        tracks = self.tracks_viewer.tracks
        if tracks is None or tracks.intensity_annotator is None:
            return [], "can be measured"

        images = [
            layer
            for layer in self.viewer.layers
            if isinstance(layer, napari.layers.Image)
        ]

        if tracks.segmentation is not None:
            seg_shape = tuple(tracks.segmentation.shape)
            return [
                layer
                for layer in images
                if tuple(getattr(layer.data, "shape", ())) == seg_shape
            ], f"have the same shape as the segmentation: {seg_shape}"

        return [layer for layer in images if layer.ndim == tracks.ndim], (
            f"have the {tracks.ndim} dimensions of the tracks (t, [z], y, x)"
        )
