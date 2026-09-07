from pathlib import Path

import numpy as np
from funtracks.data_model import Tracks
from funtracks.import_export import export_to_csv, export_to_geff
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from motile_tracker.data_views.colormap import TrackColormap


class ExportTypeDialog(QDialog):
    def __init__(self, parent=None, label: str = "", has_segmentation: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Select Export Type")

        layout = QVBoxLayout(self)

        if label:
            layout.addWidget(QLabel(label))

        self.export_type_combo = QComboBox()
        self.export_type_combo.addItems(["GEFF", "CSV"])
        layout.addWidget(self.export_type_combo)

        self._geff_seg_label = QLabel(
            "<i>The segmentation is part of the graph and is always saved with GEFF. "
            "No need to export it separately (unless you want to open it as a "
            "standalone file).</i>"
        )
        self._geff_seg_label.setWordWrap(True)
        self._geff_seg_label.setVisible(False)
        layout.addWidget(self._geff_seg_label)

        self.seg_checkbox = QCheckBox("Export segmentation")
        self.seg_checkbox.setVisible(has_segmentation)
        layout.addWidget(self.seg_checkbox)

        self.seg_format_label = QLabel("Segmentation format:")
        self.seg_format_combo = QComboBox()
        self.seg_format_combo.addItems(["zarr", "tiff"])
        self.relabel_checkbox = QCheckBox("Relabel segmentation by Track ID")
        self.relabel_checkbox.setChecked(True)

        for w in (self.seg_format_label, self.seg_format_combo, self.relabel_checkbox):
            w.setVisible(False)
            layout.addWidget(w)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self._has_segmentation = has_segmentation
        self.seg_checkbox.toggled.connect(self._on_seg_toggled)
        self.export_type_combo.currentTextChanged.connect(self._on_export_type_changed)
        self._on_export_type_changed(self.export_type_combo.currentText())

    def _on_export_type_changed(self, export_type: str) -> None:
        is_geff = export_type == "GEFF"
        self.seg_checkbox.setVisible(self._has_segmentation)
        self._geff_seg_label.setVisible(self._has_segmentation and is_geff)

    def _on_seg_toggled(self, checked: bool):
        for w in (self.seg_format_label, self.seg_format_combo, self.relabel_checkbox):
            w.setVisible(checked)

    @property
    def export_type(self) -> str:
        return self.export_type_combo.currentText()

    @property
    def save_segmentation(self) -> bool:
        return self.seg_checkbox.isChecked()

    @property
    def seg_file_format(self) -> str:
        return self.seg_format_combo.currentText()

    @property
    def seg_label_attr(self) -> str | None:
        return "tracklet" if self.relabel_checkbox.isChecked() else None


class ExportDialog:
    """Handles exporting tracks to CSV or geff."""

    @staticmethod
    def show_export_dialog(
        parent,
        tracks: Tracks,
        name: str,
        colormap: TrackColormap,
        nodes_to_keep: set[int] | None = None,
    ):
        """Export tracks to CSV or geff, with the option to export a subset of nodes only.

        Args:
            tracks (Tracks): to be exported Tracks object.
            name (str): filename for exporting
            nodes_to_keep (set[int], optional): list of nodes to be exported. Ancestor
                nodes will automatically be included to make sure the graph has no
                missing parent nodes.
        """
        if nodes_to_keep is None:
            label = "Choose tracks export format:"
        else:
            label = (
                f"<p style='white-space: normal;'>"
                f"<i>Export all nodes in group </i>"
                f"<span style='color: green;'><b>{name}.</b></span><br>"
                f"<i>Note that ancestors will also be included to maintain a valid "
                f"graph.</i>"
                f"</p>"
                f"<p>Choose tracks export format:</p>"
            )

        dialog = ExportTypeDialog(
            parent, label, has_segmentation=tracks.segmentation is not None
        )

        if dialog.exec_() != QDialog.Accepted:
            return False

        export_type = dialog.export_type
        save_segmentation = dialog.save_segmentation
        seg_file_format = dialog.seg_file_format
        seg_label_attr = dialog.seg_label_attr

        if export_type == "CSV":
            csv_dialog = QFileDialog(parent, "Save to CSV")
            csv_dialog.setFileMode(QFileDialog.AnyFile)
            csv_dialog.setAcceptMode(QFileDialog.AcceptSave)
            csv_dialog.setNameFilter("CSV files (*.csv)")
            csv_dialog.setDefaultSuffix("csv")
            csv_dialog.selectFile(str(Path.home() / f"{name}_tracks.csv"))

            if not csv_dialog.exec_():
                return False

            file_path = Path(csv_dialog.selectedFiles()[0])
            seg_path = None

            if save_segmentation:
                if seg_file_format == "tiff":
                    seg_dialog = QFileDialog(parent, "Save segmentation as TIFF")
                    seg_dialog.setFileMode(QFileDialog.AnyFile)
                    seg_dialog.setAcceptMode(QFileDialog.AcceptSave)
                    seg_dialog.setNameFilter("TIF files (*.tif)")
                    seg_dialog.setDefaultSuffix("tif")
                    seg_dialog.selectFile(str(file_path.with_suffix(".tif")))
                else:
                    seg_dialog = QFileDialog(parent, "Save segmentation as Zarr")
                    seg_dialog.setFileMode(QFileDialog.AnyFile)
                    seg_dialog.setAcceptMode(QFileDialog.AcceptSave)
                    seg_dialog.setNameFilter("Zarr folder (*.zarr)")
                    seg_dialog.setDefaultSuffix("zarr")
                    seg_dialog.selectFile(
                        str(file_path.with_name(file_path.stem + "_seg.zarr"))
                    )

                if not seg_dialog.exec_():
                    return False
                seg_path = Path(seg_dialog.selectedFiles()[0])

            nodes = tracks.graph.node_ids()
            track_ids = tracks.get_track_ids(nodes)
            # Single vectorized colormap.map call (per-call overhead makes
            # per-node mapping O(nodes) slow); these colors are export-only and
            # not mutated in place, so no per-node copy is needed.
            colors = colormap.map(np.asarray(track_ids)) if len(track_ids) > 0 else []
            color_dict = {
                **dict(zip(nodes, colors, strict=True)),
                None: [0, 0, 0, 0],
            }

            export_to_csv(
                tracks=tracks,
                outfile=file_path,
                color_dict=color_dict,
                node_ids=nodes_to_keep,
                use_display_names=True,
                export_seg=save_segmentation,
                seg_path=seg_path,
                seg_relabel=seg_label_attr,
                seg_file_format=seg_file_format,
            )
            return True

        elif export_type == "GEFF":
            file_dialog = QFileDialog(parent, "Save as GEFF file")
            file_dialog.setFileMode(QFileDialog.AnyFile)
            file_dialog.setAcceptMode(QFileDialog.AcceptSave)
            file_dialog.setNameFilter("Zarr folder (*.zarr)")
            file_dialog.setDefaultSuffix("zarr")
            file_dialog.selectFile(str(Path.home() / f"{name}_geff.zarr"))

            if not file_dialog.exec_():
                return False

            file_path = Path(file_dialog.selectedFiles()[0])
            try:
                export_to_geff(
                    tracks,
                    file_path,
                    overwrite=True,
                    node_ids=nodes_to_keep,
                    save_segmentation=save_segmentation,
                    seg_relabel=seg_label_attr,
                    seg_file_format=seg_file_format,
                )
                return True
            except ValueError as e:
                QMessageBox.warning(parent, "Export Error", str(e))
        return False
