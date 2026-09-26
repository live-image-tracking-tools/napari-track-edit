import napari
from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QLabel,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.application_menus.keybindings_widget import (
    open_keybindings_panel,
)
from motile_tracker.data_views.keybindings_config import shortcut_text
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.download_progress import DownloadCancelled, download_progress
from motile_tracker.example_data import SAMPLE_TRACKS, raw_data_is_downloaded

DOCS_URL = "https://liveimagetrackingtools.org/napari-track-edit"
KEYBINDINGS_LINK = "motile-tracker:keybindings"  # Not a real address, used to keep the formatting consistent
TUTORIAL_URL = "https://github.com/funkelab/motile_tracker/blob/main/assets/motile-tracker_tutorial.pdf"
DOCS_ICON = "\U0001f4d6"  # open book
KEYBINDINGS_ICON = "\u2328\ufe0f"  # keyboard
TUTORIAL_ICON = "\U0001f393"  # graduation cap

# Links use this scheme to load an example instead of navigating to a page.
EXAMPLE_SCHEME = "load-example"


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
        title = QLabel("Motile Tracker")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Top links
        example_links = "&nbsp;&nbsp;".join(
            f'<a href="{EXAMPLE_SCHEME}:{name}"><b>🔬 {name}</b></a>'
            for name in SAMPLE_TRACKS
        )
        links_html = f"""
        <p style="margin: 8px 0; line-height: 1.8;">
            <a href="{DOCS_URL}"><b>{DOCS_ICON} Documentation</b></a>&nbsp;&nbsp;
            <a href="{KEYBINDINGS_LINK}"><b>{KEYBINDINGS_ICON} Keybindings</b></a>&nbsp;&nbsp;
            <a href="{TUTORIAL_URL}"><b>{TUTORIAL_ICON} Tutorial</b></a>
        </p>
        <p style="margin: 8px 0; line-height: 1.8;">
            <b>Example data:</b>&nbsp;&nbsp;{example_links}
        </p>
        """
        self.links = QTextBrowser()
        self.links.setOpenLinks(False)  # handled in _on_link_clicked
        self.links.anchorClicked.connect(self._on_link_clicked)
        self.links.setHtml(links_html)
        self.links.setMaximumHeight(100)
        self.links.setStyleSheet(
            "QTextBrowser { border: none; background: transparent; margin: 0px; padding: 0px; }"
        )
        self.links.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.links.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.links)

        # Content
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        content.setStyleSheet("QTextBrowser { border: none; background: transparent; }")

        content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content.setMarkdown(f"""
### Quick Start

1. **Load Data**: Drag and drop your label or points data in the napari viewer.
2. **Configure Tracking**: Specify parameters in the Tracking panel and click 'Run Tracking'.
3. **Results**: Results are added to the Tracks List. View and navigate a tracking result in the napari layers and in the Lineage View.
4. **Edit Results**: Use the Editing & Selection panel to refine results.
5. **Visualization options**: Use the Visualization panel to adjust display mode and to show orthogonal views.
6. **Save & Load**: Save or export results in the Tracks List. To pick up where you left off, load the project from Motile Run.

### Tips

- Right-click on the 'eye' icon (middle) at the top of the docked widgets to set menu visibility.
- Toggle panels with the `{shortcut_text("hide_panels")}` key to maximize viewing space.
- View individual lineages by changing the display mode in Visualization tab and in the Lineage View (press [{shortcut_text("toggle_display_mode")}])
- If you have segmentation data, you can view additional features (e.g. area/volume) in the Lineage View (press [{shortcut_text("toggle_feature_mode")}])
- Assign objects to custom groups to keep track of different cell populations or conditions ('Groups' menu).
- Import data from external tracks from CSV or GEFF in the Tracks List menu.
        """)

        layout.addWidget(content)

        self.setLayout(layout)

    def _on_link_clicked(self, url: QUrl) -> None:
        """Open documentation links in a browser, load examples in the app."""

        if url.toString() == KEYBINDINGS_LINK:
            open_keybindings_panel(self)
        elif url.scheme() == EXAMPLE_SCHEME:
            self._load_example(url.path())
        else:
            QDesktopServices.openUrl(url)

    def _load_example(self, sample_name: str) -> None:
        """Load one of the sample tracks and its raw data, downloading them
        first if needed.

        The TracksViewer is looked up on click rather than on construction, so
        the widget does not depend on the order in which the menus are created.

        Args:
            sample_name (str): A key of SAMPLE_TRACKS
        """
        if not self._confirm_raw_download(sample_name):
            return
        tracks_list = TracksViewer.get_instance(self.viewer).tracks_list
        if not self._add_raw_layer(sample_name):
            return  # cancelled or failed, the tracks alone are not useful
        tracks_list.load_sample_tracks(sample_name)

    def _confirm_raw_download(self, sample_name: str) -> bool:
        """Ask before fetching the raw data for the first time, because it is a
        few hundred megabytes and can take minutes on a slow connection.

        Args:
            sample_name (str): A key of SAMPLE_TRACKS

        Returns:
            bool: True if the example should be loaded
        """
        sample = SAMPLE_TRACKS[sample_name]
        if sample.raw_name in self.viewer.layers or raw_data_is_downloaded(sample_name):
            return True
        answer = QMessageBox.question(
            self,
            "Download example data",
            f"The images for {sample_name} still have to be downloaded "
            f"({sample.raw_size}), which can take a few minutes.\n\n"
            "Download them now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return answer == QMessageBox.Yes

    def _add_raw_layer(self, sample_name: str) -> bool:
        """Add the raw data belonging to a sample to the viewer, downloading it
        first if needed. Skipped if a layer with that name is already present.
        Added before the tracks, so that the tracks layers are drawn on top.

        Args:
            sample_name (str): A key of SAMPLE_TRACKS

        Returns:
            bool: False if the user cancelled the download, or it failed
        """
        sample = SAMPLE_TRACKS[sample_name]
        if sample.raw_name in self.viewer.layers:
            return True
        try:
            with download_progress(self, f"images of {sample_name}") as reporthook:
                data, meta, _ = sample.load_raw(reporthook)
        except DownloadCancelled:
            return False
        except Exception as e:  # noqa: BLE001 - surfaced to the user in a dialog
            QMessageBox.warning(
                self, "Error", f"Failed to load raw data for {sample_name}: {e}"
            )
            return False
        self.viewer.add_image(data, **meta)
        return True
