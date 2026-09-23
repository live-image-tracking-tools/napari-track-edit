import napari
from qtpy.QtCore import Qt
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.application_menus.keybindings_widget import (
    open_keybindings_panel,
)
from motile_tracker.data_views.keybindings_config import shortcut_text

DOCS_URL = "https://liveimagetrackingtools.org/napari-track-edit"
TUTORIAL_URL = "https://github.com/funkelab/motile_tracker/blob/main/assets/motile-tracker_tutorial.pdf"
# Not a real address, used to keep the formatting consistent
KEYBINDINGS_LINK = "motile-tracker:keybindings"
DOCS_ICON = "\U0001f4d6"  # open book
KEYBINDINGS_ICON = "\u2328\ufe0f"  # keyboard
TUTORIAL_ICON = "\U0001f393"  # graduation cap


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

        # Top links.
        links_html = f"""
        <p style="margin: 8px 0; line-height: 1.8;">
            <a href="{DOCS_URL}"><b>{DOCS_ICON} Documentation</b></a>&nbsp;&nbsp;
            <a href="{KEYBINDINGS_LINK}"><b>{KEYBINDINGS_ICON} Keybindings</b></a>&nbsp;&nbsp;
            <a href="{TUTORIAL_URL}"><b>{TUTORIAL_ICON} Tutorial</b></a>
        </p>
        """
        self.links = QTextBrowser()
        self.links.setOpenLinks(False)
        self.links.anchorClicked.connect(self._open_link)
        self.links.setHtml(links_html)
        self.links.setMaximumHeight(50)
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

    def _open_link(self, url) -> None:
        """Open the keybindings panel for our own scheme, the browser otherwise."""
        if url.toString() == KEYBINDINGS_LINK:
            open_keybindings_panel(self)
        else:
            QDesktopServices.openUrl(url)
