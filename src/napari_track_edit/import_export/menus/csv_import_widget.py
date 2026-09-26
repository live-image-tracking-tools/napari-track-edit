import os
from pathlib import Path

import pandas as pd
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


class ImportCSVWidget(QWidget):
    """QWidget for loading a CSV file as pandas dataframe."""

    update_buttons = Signal()

    def __init__(self):
        super().__init__()

        self.df = None

        # QlineEdit for csv file path and browse button
        self.csv_path_line = QLineEdit(self)
        self.csv_path_line.setFocus()
        self.csv_path_line.setFocusPolicy(Qt.StrongFocus)
        self.csv_path_line.returnPressed.connect(self._on_line_editing_finished)
        self.csv_browse_button = QPushButton("Browse", self)
        self.csv_browse_button.setAutoDefault(0)
        self.csv_browse_button.clicked.connect(self._browse_csv)

        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.csv_path_line)
        browse_layout.addWidget(self.csv_browse_button)

        box = QGroupBox("Path to csv file")
        box_layout = QVBoxLayout()
        box_layout.addLayout(browse_layout)
        box.setLayout(box_layout)
        main_layout = QVBoxLayout()
        main_layout.addWidget(box)
        self.setLayout(main_layout)

    def _on_line_editing_finished(self) -> None:
        """Load the csv group when the user presses Enter in the path line"""

        file_path = self.csv_path_line.text().strip()
        if not file_path:
            self.update_buttons.emit()  # to remove any widgets and disable finish button
        else:
            # try to load, will raise an error if no zarr group can be found
            self._load_csv(Path(file_path))

    def _browse_csv(self) -> None:
        """Open File dialog to select CSV file"""

        csv_file, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if csv_file:
            self._load_csv(csv_file)
        else:
            QMessageBox.warning(self, "Input Required", "Please select a CSV file.")

    def _load_csv(self, csv_file: Path) -> None:
        """Load the csv file and display the CSVFieldMapWidget"""

        if csv_file == "":
            self.df = None

        elif not os.path.exists(csv_file):
            QMessageBox.critical(self, "Error", "The specified file was not found.")
            self.df = None

        # Ensure CSV path is valid
        else:
            try:
                self.df = pd.read_csv(csv_file)
                self.csv_path_line.setText(str(csv_file))

            except pd.errors.EmptyDataError:
                QMessageBox.critical(self, "Error", "The file is empty or has no data.")
                self.df = None

            except pd.errors.ParserError:
                self.df = None
                QMessageBox.critical(
                    self, "Error", "The file could not be parsed as a valid CSV."
                )

        self.update_buttons.emit()
