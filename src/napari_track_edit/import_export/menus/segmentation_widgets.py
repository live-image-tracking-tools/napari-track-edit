import os
from pathlib import Path

import numpy as np
import zarr
from funtracks.import_export import has_embedded_segmentation
from funtracks.import_export.magic_imread import magic_imread
from psygnal import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from napari_track_edit.import_export.menus.geff_import_utils import (
    clear_layout,
    geff_group_path,
)


class ExternalSegmentationWidget(QWidget):
    """Widget for specifying the path to an external segmentation image file or folder."""

    seg_path_updated = Signal()

    def __init__(self):
        super().__init__()

        self.image_path_line = QLineEdit(self)
        self.image_path_line.editingFinished.connect(self._verify_path)
        self.image_browse_button = QPushButton("Browse")
        self.image_browse_button.setAutoDefault(0)
        self.image_browse_button.clicked.connect(self._browse_segmentation)
        self.valid = False

        image_widget = QWidget()
        image_layout = QVBoxLayout()
        image_sublayout = QHBoxLayout()
        self.seg_label = QLabel("Segmentation data path:")
        image_sublayout.addWidget(self.seg_label)
        image_sublayout.addWidget(self.image_path_line)
        image_sublayout.addWidget(self.image_browse_button)

        label = QLabel(
            "Image data can either be a single tif (3D+time or 2D+time) stack, a "
            "folder containing a time series of 2D or 3D tif images, or a zarr "
            "folder."
        )
        font = label.font()
        font.setItalic(True)
        label.setFont(font)
        label.setWordWrap(True)

        image_layout.addWidget(label)
        image_layout.addLayout(image_sublayout)
        image_widget.setLayout(image_layout)
        image_widget.setMaximumHeight(100)

        main_layout = QVBoxLayout()
        main_layout.addWidget(image_widget)
        self.setLayout(main_layout)

    def _browse_segmentation(self) -> None:
        """Open custom dialog to select either a file or a folder"""

        dialog = FileFolderDialog(self)

        def _on_finished(result: int) -> None:
            if result == dialog.Accepted:
                selected_path = dialog.get_selected_path()
                if selected_path:
                    self.image_path_line.setText(selected_path)
                    self._verify_path()
            self.seg_path_updated.emit()

        dialog.finished.connect(_on_finished)
        dialog.open()

    def _verify_path(self) -> None:
        """Check that the path exists and is of type .zarr or tiff, change style sheet if
        invalid"""

        path = self.image_path_line.text()
        is_tiff = path.endswith((".tif", ".tiff"))
        is_zarr = ".zarr" in path
        is_dir_with_tiff_images = os.path.isdir(path) and any(
            f.endswith((".tif", ".tiff")) for f in os.listdir(path)
        )
        path_exists = os.path.exists(path)

        self.valid = path_exists and (is_tiff or is_zarr or is_dir_with_tiff_images)
        if not self.valid:
            self.seg_label.setStyleSheet("color: red;")
        else:
            self.seg_label.setStyleSheet("")

        self.seg_path_updated.emit()

    def get_segmentation_path(self) -> Path | None:
        """Return the path to the segmentation data."""

        path = self.image_path_line.text()
        if os.path.exists(self.image_path_line.text()):
            return Path(path)
        return None


class FileFolderDialog(QDialog):
    """Dialog to select a file or folder for segmentation data."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Choose an image file or a folder containing a time series")
        self.path_line_edit = QLineEdit(self)

        self.file_button = QPushButton("Select file", self)
        self.file_button.clicked.connect(self._select_file)
        self.file_button.setAutoDefault(False)
        self.file_button.setDefault(False)

        self.folder_button = QPushButton("Select folder", self)
        self.folder_button.clicked.connect(self._select_folder)
        self.folder_button.setAutoDefault(False)
        self.folder_button.setDefault(False)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.file_button)
        button_layout.addWidget(self.folder_button)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.path_line_edit)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.ok_button)

    def _select_file(self):
        """Open File dialog to select a file and set it to the line edit."""

        file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Segmentation File",
            "",
            "Segmentation Files (*.tiff *.zarr *.tif)",
        )
        if file:
            self.path_line_edit.setText(file)

    def _select_folder(self):
        """Open Folder dialog to select a folder and set it to the line edit."""

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.path_line_edit.setText(folder)

    def get_selected_path(self) -> Path | None:
        """Return the path entered in the line edit."""

        path = self.path_line_edit.text()
        if path != "" and os.path.exists(path):
            return path
        return None


class CSVSegmentationWidget(QWidget):
    """QWidget to select segmentation data when importing from CSV"""

    seg_updated = Signal(bool)

    def __init__(self):
        super().__init__()

        # Button group for mutual exclusivity
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        # Add "None" option
        none_radio_layout = QHBoxLayout()
        self.none_radio = QRadioButton("None")
        none_radio_layout.addWidget(self.none_radio)
        self.button_group.addButton(self.none_radio)
        self.none_radio.setChecked(True)
        self.button_group.buttonToggled.connect(
            lambda: self.seg_updated.emit(self.none_radio.isChecked())
        )

        # External segmentation as a radio button
        external_segmentation_radio_layout = QVBoxLayout()
        self.external_segmentation_radio = QRadioButton("Add segmentation")
        external_segmentation_radio_layout.addWidget(self.external_segmentation_radio)
        self.button_group.addButton(self.external_segmentation_radio)
        self.external_segmentation_radio.toggled.connect(self._toggle_segmentation)
        self.segmentation_widget = ExternalSegmentationWidget()
        self.segmentation_widget.setVisible(False)
        self.segmentation_widget.seg_path_updated.connect(
            lambda: self.seg_updated.emit(self.none_radio.isChecked())
        )

        # Assemble group box layout
        box_layout = QVBoxLayout()
        box_layout.addLayout(none_radio_layout)
        box_layout.addLayout(external_segmentation_radio_layout)
        box_layout.addWidget(self.segmentation_widget)

        main_layout = QVBoxLayout()
        box = QGroupBox("Segmentation data")
        box.setLayout(box_layout)
        main_layout.addWidget(box)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Minimum)
        self.setLayout(main_layout)

        self.setToolTip(
            "<html><body><p style='white-space:pre-wrap; width: 300px;'>"
            "If your tracking data is associated with segmentation data, select it here."
        )

    def _toggle_segmentation(self, checked: bool) -> None:
        """Toggle visibility of the segmentation widget based on the radio button
        state."""

        self.segmentation_widget.setVisible(checked)
        self.adjustSize()

    def include_seg(self) -> bool:
        """Return True if any segmentation radio button is checked, else False."""

        return self.external_segmentation_radio.isChecked()

    def get_segmentation_path(self) -> Path | None:
        """Return the path to selected segmentation data"""

        if self.external_segmentation_radio.isChecked():
            return self.segmentation_widget.get_segmentation_path()
        return None

    def load_segmentation(self) -> np.ndarray | None:
        """Return the associated segmentation image array if a valid path is given."""

        path = self.get_segmentation_path()
        if path is not None and os.path.exists(path) and self.segmentation_widget.valid:
            segmentation = magic_imread(path, use_dask=False)
            return segmentation
        else:
            QMessageBox.critical(
                self,
                "Invalid file type",
                "Please provide a tiff or zarr file for the segmentation image stack",
            )
            return None


def _geff_has_mask_props(root: zarr.Group) -> bool:
    """Return True if 'mask' and 'bbox' exist as actual node prop arrays in the zarr store."""
    try:
        props = root["nodes"]["props"]
        return "mask" in props and "bbox" in props
    except KeyError:
        return False


class GeffSegmentationWidget(QWidget):
    """QWidget to select segmentation data when importing from geff."""

    seg_updated = Signal(bool)

    def __init__(self, root: zarr.Group | None = None):
        super().__init__()

        self.root = root

        # Button group for mutual exclusivity
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.related_object_radio_buttons = {}

        # Add "None" option
        none_radio_layout = QHBoxLayout()
        self.none_radio = QRadioButton("None")
        none_radio_layout.addWidget(self.none_radio)
        self.button_group.addButton(self.none_radio)
        self.none_radio.setChecked(True)
        self.button_group.buttonToggled.connect(
            lambda: self.seg_updated.emit(self.none_radio.isChecked())
        )

        # Empty layout to which related objects can be added
        self.related_objects_layout = QVBoxLayout()

        # External segmentation as a radio button
        external_segmentation_radio_layout = QVBoxLayout()
        self.external_segmentation_radio = QRadioButton("Use external segmentation")
        external_segmentation_radio_layout.addWidget(self.external_segmentation_radio)
        self.button_group.addButton(self.external_segmentation_radio)
        self.external_segmentation_radio.toggled.connect(self._toggle_segmentation)
        self.segmentation_widget = ExternalSegmentationWidget()
        self.segmentation_widget.setVisible(False)
        self.segmentation_widget.seg_path_updated.connect(
            lambda: self.seg_updated.emit(self.none_radio.isChecked())
        )

        # Info label shown when masks/bboxes are embedded in the graph
        self._embedded_info_label = QLabel(
            "Embedded segmentation detected (masks/bboxes). "
            "The segmentation will be reconstructed automatically."
        )
        self._embedded_info_label.setWordWrap(True)
        font = self._embedded_info_label.font()
        font.setItalic(True)
        self._embedded_info_label.setFont(font)
        self._embedded_info_label.setVisible(False)

        # Warning label shown when masks/bboxes are present but the shape metadata
        # is missing (GEFF exported by an older version of funtracks or external tool)
        self._old_geff_warning_label = QLabel(
            "⚠ This GEFF contains mask/bbox data but no shape metadata. "
            "The segmentation cannot be reconstructed automatically. "
            "Re-export with an updated version of funtracks, or provide an "
            "external segmentation file below."
        )
        self._old_geff_warning_label.setWordWrap(True)
        self._old_geff_warning_label.setStyleSheet("color: orange;")
        self._old_geff_warning_label.setVisible(False)

        # Assemble group box layout
        box_layout = QVBoxLayout()
        box_layout.addWidget(self._embedded_info_label)
        box_layout.addWidget(self._old_geff_warning_label)
        box_layout.addLayout(none_radio_layout)
        box_layout.addLayout(self.related_objects_layout)
        box_layout.addLayout(external_segmentation_radio_layout)
        box_layout.addWidget(self.segmentation_widget)

        main_layout = QVBoxLayout()
        box = QGroupBox("Segmentation data")
        box.setLayout(box_layout)
        main_layout.addWidget(box)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Minimum)
        self.setLayout(main_layout)

        self.setToolTip(
            "<html><body><p style='white-space:pre-wrap; width: 300px;'>"
            "Optionally select a segmentation image, or use associated data if provided"
            " in the GEFF directory."
        )
        self.setVisible(False)

    def update_root(self, root: zarr.Group | None) -> None:
        """Update the root group and populate related objects if available.
        Args:
            root (zarr.Group | None): The root group of the geff zarr store.
        """
        self.setVisible(False)
        self.root = root
        clear_layout(self.related_objects_layout)
        self.related_object_radio_buttons = {}
        if self.root is not None:
            has_embedded_seg = has_embedded_segmentation(geff_group_path(self.root))
            if has_embedded_seg:
                # Embedded segmentation: hide radio options, show info label.
                # segmentation_path=None will be passed to import_from_geff and
                # funtracks will reconstruct the segmentation as a GraphArrayView.
                self.none_radio.setVisible(False)
                self.external_segmentation_radio.setVisible(False)
                self.segmentation_widget.setVisible(False)
                self._embedded_info_label.setVisible(True)
                self._old_geff_warning_label.setVisible(False)
                self.none_radio.setChecked(True)
            elif _geff_has_mask_props(self.root):
                # Old GEFF: masks present but shape metadata missing.
                # Show a warning and the normal options so the user can provide
                # an external segmentation or skip it.
                self.none_radio.setVisible(True)
                self.external_segmentation_radio.setVisible(True)
                self._embedded_info_label.setVisible(False)
                self._old_geff_warning_label.setVisible(True)
            else:
                self.none_radio.setVisible(True)
                self.external_segmentation_radio.setVisible(True)
                self._embedded_info_label.setVisible(False)
                self._old_geff_warning_label.setVisible(False)

            if not has_embedded_seg:
                metadata = dict(self.root.attrs)
                related_objects = metadata.get("geff", {}).get("related_objects", None)
                if related_objects:
                    for obj in related_objects:
                        if obj.get("type") == "labels":
                            radio = QRadioButton(
                                f"Related data: {obj.get('path', None)}"
                            )
                            radio.setChecked(True)
                            self.button_group.addButton(radio)
                            self.related_object_radio_buttons[obj.get("path", None)] = (
                                radio
                            )
                            self.related_objects_layout.addWidget(radio)
            self.setVisible(True)

    def _toggle_segmentation(self, checked: bool) -> None:
        """Toggle visibility of the segmentation widget based on the radio button
        state."""
        self.segmentation_widget.setVisible(checked)
        self.adjustSize()

    def include_seg(self) -> bool:
        """Return True if any segmentation radio button is checked, else False."""

        # Check external segmentation radio
        if self.external_segmentation_radio.isChecked():
            return True
        # Check related object radios
        for radio in self.related_object_radio_buttons.values():
            if radio.isChecked():
                return True
        return False

    def get_segmentation_path(self) -> Path | None:
        """Return the path to selected related object or external segmentation"""

        for path, radio in self.related_object_radio_buttons.items():
            if radio.isChecked():
                seg_path = (geff_group_path(self.root) / path).resolve()
                return seg_path
        if self.external_segmentation_radio.isChecked():
            return self.segmentation_widget.get_segmentation_path()
        return None
