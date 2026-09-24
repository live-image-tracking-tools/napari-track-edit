import napari
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.example_data import SAMPLE_TRACKS

DOCS_URL = "https://funkelab.github.io/motile_tracker"
KEYBINDINGS_URL = f"{DOCS_URL}/key_bindings.html"
TUTORIAL_URL = "https://github.com/funkelab/motile_tracker/blob/main/assets/motile-tracker_tutorial.pdf"


class WelcomeWidget(QWidget):
    """Getting started widget with links and basic information to get started with the tool."""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.viewer = viewer

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Title
        title = QLabel("Napari Track Edit")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Top links
        links_html = f"""
        <p style="margin: 8px 0; line-height: 1.8;">
            <a href="{DOCS_URL}"><b>📖 Documentation</b></a>&nbsp;&nbsp;
            <a href="{KEYBINDINGS_URL}"><b>🖱️ Keybindings</b></a>&nbsp;&nbsp;
            <a href="{TUTORIAL_URL}"><b>🎓 Tutorial</b></a>
        </p>
        """
        links = QTextBrowser()
        links.setOpenExternalLinks(True)
        links.setHtml(links_html)
        links.setMaximumHeight(50)
        links.setStyleSheet(
            "QTextBrowser { border: none; background: transparent; margin: 0px; padding: 0px; }"
        )
        links.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        links.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(links)

        # Content
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        content.setStyleSheet("QTextBrowser { border: none; background: transparent; }")

        content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content.setMarkdown("""
### Quick Start

1. **Load Data**: Drag and drop your label or points data in the napari viewer.
2. **Configure Tracking**: Specify parameters in the Tracking panel and click 'Run Tracking'.
3. **Results**: Results are added to the Tracks List. View and navigate a tracking result in the napari layers and in the Lineage View.
4. **Edit Results**: Use the Editing & Selection panel to refine results.
5. **Visualization options**: Use the Visualization panel to adjust display mode and to show orthogonal views.
6. **Save & Load**: Save or export results in the Tracks List. To pick up where you left off, load the project from Motile Run.

### Tips

- Right-click on the 'eye' icon (middle) at the top of the docked widgets to set menu visibility.
- Toggle panels with the `/` key to maximize viewing space.
- View individual lineages by changing the display mode in Visualization tab and in the Lineage View (press [Q])
- If you have segmentation data, you can view additional features (e.g. area/volume) in the Lineage View (press [W])
- Assign objects to custom groups to keep track of different cell populations or conditions ('Groups' menu).
- Import data from external tracks from CSV or GEFF in the Tracks List menu.
        """)

        layout.addWidget(content)

        # example buttons, loading sample tracks into the tracks list
        layout.addWidget(QLabel("Show me an example!"))
        example_button_layout = QHBoxLayout()
        for sample_name in SAMPLE_TRACKS:
            example_button = QPushButton(sample_name)
            example_button.clicked.connect(
                lambda _, name=sample_name: self._load_example(name)
            )
            example_button_layout.addWidget(example_button)
        layout.addLayout(example_button_layout)

        self.setLayout(layout)

    def _load_example(self, sample_name: str) -> None:
        """Load one of the sample tracks into the tracks list, downloading it
        first if needed.

        The TracksViewer is looked up on click rather than on construction, so
        the widget does not depend on the order in which the menus are created.

        Args:
            sample_name (str): A key of SAMPLE_TRACKS
        """
        tracks_list = TracksViewer.get_instance(self.viewer).tracks_list
        self._add_raw_layer(sample_name)
        tracks_list.load_sample_tracks(sample_name)

    def _add_raw_layer(self, sample_name: str) -> None:
        """Add the raw data belonging to a sample to the viewer, downloading it
        first if needed. Skipped if a layer with that name is already present.
        Added before the tracks, so that the tracks layers are drawn on top.

        Args:
            sample_name (str): A key of SAMPLE_TRACKS
        """
        sample = SAMPLE_TRACKS[sample_name]
        if sample.raw_name in self.viewer.layers:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            data, meta, _ = sample.load_raw()
        except Exception as e:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self, "Error", f"Failed to load raw data for {sample_name}: {e}"
            )
            return
        QApplication.restoreOverrideCursor()
        self.viewer.add_image(data, **meta)
