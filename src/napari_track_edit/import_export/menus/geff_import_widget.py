import os
from pathlib import Path

import zarr
from funtracks.utils import open_zarr_store
from psygnal import Signal
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from napari_track_edit.import_export.menus.geff_import_utils import (
    find_single_geff,
)


class ImportGeffWidget(QWidget):
    """QWidget for selecting a geff zarr directory to import."""

    update_buttons = Signal()

    def __init__(self):
        super().__init__()

        self.root = None
        self.store_path: Path | None = None  # Path to the zarr store on disk
        self.dir_name = None

        self.geff_path_line = QLineEdit(self)
        self.geff_path_line.setFocus()
        self.geff_path_line.setFocusPolicy(Qt.StrongFocus)
        self.geff_path_line.returnPressed.connect(self._on_line_editing_finished)
        self.geff_browse_button = QPushButton("Browse", self)
        self.geff_browse_button.setAutoDefault(0)
        self.geff_browse_button.clicked.connect(self._browse_geff)

        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.geff_path_line)
        browse_layout.addWidget(self.geff_browse_button)

        box = QGroupBox("Path to GEFF zarr directory")
        box_layout = QVBoxLayout()
        box_layout.addLayout(browse_layout)
        box.setLayout(box_layout)
        main_layout = QVBoxLayout()
        main_layout.addWidget(box)
        self.setLayout(main_layout)

    def _on_line_editing_finished(self) -> None:
        """Load the geff group when the user presses Enter in the path line"""

        folder_path = self.geff_path_line.text().strip()
        if not folder_path:
            self.root = None
            self.store_path = None
            self.update_buttons.emit()  # to remove any widgets and disable finish button
        else:
            # try to load, will raise an error if no zarr group can be found
            self._load_geff(Path(folder_path))

    def _browse_geff(self) -> None:
        """Open File dialog to select geff folder"""

        folder = QFileDialog.getExistingDirectory(self, "Select GEFF Zarr directory")
        if folder:
            folder_path = Path(folder)
            self.geff_path_line.setText(str(folder_path))
            self._load_geff(folder_path)

    def _load_geff(self, folder_path: Path) -> None:
        """Find the geff in the selected folder_path and send update signal.

        The folder may be a geff itself or hold exactly one, as a plain directory
        or a zarr container. Nothing is written to it.
        """

        self.root = None
        self.store_path = None
        if not os.path.exists(folder_path):
            QMessageBox.critical(self, "Error", f"Path does not exist: {folder_path}")
            self.update_buttons.emit()
            return

        try:
            geff_path = find_single_geff(Path(folder_path))
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
            self.update_buttons.emit()
            return

        # Opened with mode "r+" rather than through zarr.group, which creates a
        # group when there is none. Still writable because the import dialog may
        # add missing axes metadata to the geff.
        try:
            store = open_zarr_store(geff_path)
            self.root = zarr.open_group(store=store, mode="r+")
        except (KeyError, ValueError, OSError) as e:
            QMessageBox.critical(self, "Error", f"Could not open zarr store: {e}")
            self.update_buttons.emit()
            return

        self.store_path = geff_path
        self.dir_name = os.path.basename(folder_path)
        self.update_buttons.emit()
