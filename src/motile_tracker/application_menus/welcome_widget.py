import urllib.request
import zipfile
from pathlib import Path

import napari
from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

DOCS_URL = "https://funkelab.github.io/motile_tracker"
KEYBINDINGS_URL = f"{DOCS_URL}/key_bindings.html"
TUTORIAL_URL = "https://github.com/funkelab/motile_tracker/blob/main/assets/motile-tracker_tutorial.pdf"


def _drive_download_url(file_id: str) -> str:
    """Direct-download URL for a Google Drive file (skips the preview page)."""
    return (
        f"https://drive.usercontent.google.com/download?id={file_id}"
        "&export=download&confirm=t"
    )


# Zipped example geff datasets, as (link label, file name, download url)
EXAMPLE_GEFFS = (
    (
        "2D",
        "hela2D_crop_tracks.geff.zip",
        _drive_download_url("1wI1IHtxvbXB6Tg75zozxnFbeTITBefSW"),
    ),
    (
        "3D",
        "mouse3D_tracks.geff.zip",
        _drive_download_url("1zTiI4FRiSyOomaN-eV_HBTqQoawUCPWi"),
    ),
)
# Links use this scheme to trigger an in-app download instead of navigating.
DOWNLOAD_SCHEME = "geff-download"
LOAD_HINT = (
    "Unzip the file, then load the .geff from the Tracks List menu "
    '(select "Tracks (geff)" and press Load).'
)


class WelcomeWidget(QWidget):
    """Getting started widget with links and basic information to get started with the tool."""

    def __init__(self, _viewer: napari.Viewer):

        super().__init__()  # viewer is actually not used for this widget, but kept in to
        # match the expected signature for menu widgets.

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
        download_links = "&nbsp;&nbsp;".join(
            f'<a href="{DOWNLOAD_SCHEME}:{label}">'
            f"<b>📥 Download {label} example</b></a>"
            for label, _, _ in EXAMPLE_GEFFS
        )
        links_html = f"""
        <p style="margin: 8px 0; line-height: 1.8;">
            <a href="{DOCS_URL}"><b>📖 Documentation</b></a>&nbsp;&nbsp;
            <a href="{KEYBINDINGS_URL}"><b>🖱️ Keybindings</b></a>&nbsp;&nbsp;
            <a href="{TUTORIAL_URL}"><b>🎓 Tutorial</b></a>
        </p>
        <p style="margin: 8px 0; line-height: 1.8;">
            {download_links}
        </p>
        """
        links = QTextBrowser()
        links.setOpenLinks(False)  # handled in _on_link_clicked
        links.anchorClicked.connect(self._on_link_clicked)
        links.setHtml(links_html)
        links.setMaximumHeight(80)
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
        self.setLayout(layout)

    def _on_link_clicked(self, url: QUrl) -> None:
        """Open documentation links in a browser, download example data in-app."""
        if url.scheme() != DOWNLOAD_SCHEME:
            QDesktopServices.openUrl(url)
            return
        for label, filename, download_url in EXAMPLE_GEFFS:
            if label == url.path():
                self._download(filename, download_url)
                return

    def _download(self, filename: str, url: str) -> None:
        """Download a dataset to the user's Downloads folder."""
        dest = Path.home() / "Downloads" / filename
        if dest.exists():
            QMessageBox.information(
                self,
                "Already downloaded",
                f"{filename} is already in your Downloads folder:\n{dest}\n\n"
                f"{LOAD_HINT}",
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 - fixed https url
            if not zipfile.is_zipfile(dest):
                # Google Drive serves an html page instead of the file when the
                # download is blocked (quota exceeded, permissions changed, ...).
                dest.unlink(missing_ok=True)
                raise RuntimeError(
                    "Google Drive refused the download, try again later."
                )
        except Exception as e:  # noqa: BLE001 - surfaced to the user in a dialog
            QMessageBox.critical(self, "Download failed", str(e))
        else:
            QMessageBox.information(
                self,
                "Download complete",
                f"Saved to:\n{dest}\n\n{LOAD_HINT}",
            )
        finally:
            QApplication.restoreOverrideCursor()
