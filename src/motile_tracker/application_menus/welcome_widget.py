import napari
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

DOCS_URL = "https://funkelab.github.io/motile_tracker"
KEYBINDINGS_URL = f"{DOCS_URL}/key_bindings.html"
TUTORIAL_URL = "https://github.com/live-image-tracking-tools/napari-track-edit/blob/main/assets/napari-track-edit_tutorial.pdf"


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
        self.setLayout(layout)
