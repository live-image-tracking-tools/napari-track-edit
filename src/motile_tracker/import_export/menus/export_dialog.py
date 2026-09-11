from pathlib import Path

import napari
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

from motile_tracker.import_export.sql_io import (
    SQL_SUFFIX,
    is_same_database,
    is_sql_backed,
    rebind_tracks_to_graph,
    sql_database_path,
    write_tracks_to_sql,
)

SQL_EXPORT_TYPE = "SQL database"


class ExportTypeDialog(QDialog):
    def __init__(
        self,
        parent=None,
        label: str = "",
        has_segmentation: bool = False,
        offer_sql: bool = True,
        already_on_disk: Path | None = None,
    ):
        """
        Args:
            parent: The parent widget.
            label (str): Text shown above the format selector.
            has_segmentation (bool): Whether the tracks carry a segmentation, and
                so whether to offer exporting it as a standalone file.
            offer_sql (bool): Whether to offer the SQL database format. False for
                a group export, which writes a subset of nodes; a database is
                written whole (including candidates) so the two do not compose.
            already_on_disk (Path | None): The database the tracks already live
                in, if they are SQL-backed. Shown as a note, because for those
                tracks exporting is about sharing, not about not losing work.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Export Type")
        # Several of the explanatory labels below wrap; without a width to wrap
        # against the dialog opens narrow enough to squash them.
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        if label:
            layout.addWidget(QLabel(label))

        if already_on_disk is not None:
            on_disk_label = QLabel(
                f"<i>These tracks are stored in <b>{already_on_disk}</b> and are "
                f"kept up to date there automatically. Exporting is only needed "
                f"to hand the data to someone else.</i>"
            )
            on_disk_label.setWordWrap(True)
            layout.addWidget(on_disk_label)

        self.export_type_combo = QComboBox()
        self.export_type_combo.addItems(["GEFF", "CSV"])
        if offer_sql:
            self.export_type_combo.addItem(SQL_EXPORT_TYPE)
        layout.addWidget(self.export_type_combo)

        self._geff_seg_label = QLabel(
            "<i>The segmentation is part of the graph and is always saved with GEFF. "
            "No need to export it separately (unless you want to open it as a "
            "standalone file).</i>"
        )
        self._geff_seg_label.setWordWrap(True)
        self._geff_seg_label.setVisible(False)
        layout.addWidget(self._geff_seg_label)

        self._sql_label = QLabel(
            "<i>A SQLite database holding the whole graph, including the "
            "segmentation.</i>"
        )
        self._sql_label.setWordWrap(True)
        self._sql_label.setVisible(False)
        layout.addWidget(self._sql_label)

        # The default always leaves you working in a database, never in memory.
        # For in-memory tracks that means switching over to the one being
        # written (unticked). For tracks already in a database it means staying
        # in the one they are in (ticked), since exporting a copy is about
        # handing it over, not about moving your session into it.
        #
        # The text is broken over two lines by hand: a QCheckBox label does not
        # wrap, so on one line it gets cropped.
        staying = "the current database" if already_on_disk else "the in-memory graph"
        self.keep_in_memory_checkbox = QCheckBox(
            f"Continue editing {staying}\n"
            f"(otherwise switch to the newly saved database)"
        )
        self.keep_in_memory_checkbox.setChecked(already_on_disk is not None)
        self.keep_in_memory_checkbox.setVisible(False)
        layout.addWidget(self.keep_in_memory_checkbox)

        # Stated in the dialog rather than only in a tooltip: clearing undo is
        # the one thing about switching over that a user would not expect.
        self._rebind_label = QLabel(
            "<i>Switching over writes every later edit straight to the database, "
            "so nothing is lost if napari closes. Undo history is cleared.</i>"
        )
        self._rebind_label.setWordWrap(True)
        self._rebind_label.setVisible(False)
        layout.addWidget(self._rebind_label)

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
        is_sql = export_type == SQL_EXPORT_TYPE
        # A database always holds the segmentation, and holds it as part of the
        # graph, so there is nothing to tick and no format to choose.
        self.seg_checkbox.setVisible(self._has_segmentation and not is_sql)
        self._geff_seg_label.setVisible(self._has_segmentation and is_geff)
        self._sql_label.setVisible(is_sql)
        self.keep_in_memory_checkbox.setVisible(is_sql)
        self._rebind_label.setVisible(is_sql)
        if is_sql:
            self.seg_checkbox.setChecked(False)

    def _on_seg_toggled(self, checked: bool):
        for w in (self.seg_format_label, self.seg_format_combo, self.relabel_checkbox):
            w.setVisible(checked)

    @property
    def export_type(self) -> str:
        return self.export_type_combo.currentText()

    @property
    def rebind(self) -> bool:
        """Whether to switch the session over to the database being written.

        The checkbox asks the opposite question - whether to stay put - so that
        the default always leaves the user working in a database: in-memory
        tracks move to the new one (unticked), tracks already in a database stay
        in the one they are in (ticked).
        """
        return not self.keep_in_memory_checkbox.isChecked()

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
    """Handles exporting tracks to CSV, geff or a SQL database."""

    @staticmethod
    def show_export_dialog(
        parent,
        tracks: Tracks,
        name: str,
        colormap: napari.utils.Colormap,
        nodes_to_keep: set[int] | None = None,
    ):
        """Export tracks to CSV, geff or a SQL database, with the option to export
        a subset of nodes only.

        Args:
            tracks (Tracks): to be exported Tracks object.
            name (str): filename for exporting
            nodes_to_keep (set[int], optional): list of nodes to be exported. Ancestor
                nodes will automatically be included to make sure the graph has no
                missing parent nodes. Disables the SQL format, which writes the
                whole graph.

        Returns:
            Tracks | bool: The tracks to carry on with when the user exported a
                database and asked to keep editing in it, otherwise True on a
                successful export and False if nothing was written. Truthy either
                way, so callers that only check success keep working.
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
            parent,
            label,
            has_segmentation=tracks.segmentation is not None,
            offer_sql=nodes_to_keep is None,
            already_on_disk=sql_database_path(tracks)
            if is_sql_backed(tracks)
            else None,
        )

        if dialog.exec_() != QDialog.Accepted:
            return False

        export_type = dialog.export_type
        save_segmentation = dialog.save_segmentation
        seg_file_format = dialog.seg_file_format
        seg_label_attr = dialog.seg_label_attr

        if export_type == SQL_EXPORT_TYPE:
            return ExportDialog._export_to_sql(parent, tracks, name, dialog.rebind)

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

    @staticmethod
    def _export_to_sql(parent, tracks: Tracks, name: str, rebind: bool):
        """Write the tracks to a SQLite database, optionally switching to it.

        The destination is cleared before writing rather than being handed to
        tracksdata as an overwrite: exporting a database that is itself SQL-backed
        takes a fast SQL-level copy that requires an empty destination, and that
        is exactly the case where the graph may be too big to copy through Python.

        Returns:
            Tracks | bool: The rebound tracks if the user asked to keep editing in
                the database, True on a plain export, False if nothing was written.
        """
        file_dialog = QFileDialog(parent, "Save as SQL database")
        file_dialog.setFileMode(QFileDialog.AnyFile)
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter(f"SQLite database (*{SQL_SUFFIX})")
        file_dialog.setDefaultSuffix(SQL_SUFFIX.lstrip("."))
        file_dialog.selectFile(str(Path.home() / f"{name}_tracks{SQL_SUFFIX}"))

        if not file_dialog.exec_():
            return False

        file_path = Path(file_dialog.selectedFiles()[0])
        if is_same_database(file_path, tracks):
            QMessageBox.warning(
                parent,
                "Export Error",
                "These tracks are already stored in that database. Choose a "
                "different file to export a copy.",
            )
            return False

        try:
            graph = write_tracks_to_sql(tracks, file_path, overwrite=True)
        except (OSError, ValueError) as e:
            QMessageBox.warning(parent, "Export Error", str(e))
            return False

        if not rebind:
            return True
        return rebind_tracks_to_graph(tracks, graph)
