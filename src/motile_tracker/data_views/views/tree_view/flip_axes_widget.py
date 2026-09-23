from psygnal import Signal
from qtpy.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QWidget

from motile_tracker.data_views.keybindings_config import bind_shortcut_label


class FlipTreeWidget(QWidget):
    """Widget to flip the axis of the tree view"""

    flip_tree = Signal()

    def __init__(self):
        super().__init__()

        flip_layout = QVBoxLayout()
        display_box = QGroupBox()
        bind_shortcut_label(display_box, "flip_axes", "Plot axes")
        flip_button = QPushButton("Flip")
        flip_button.clicked.connect(self.flip)
        flip_layout.addWidget(flip_button)
        display_box.setLayout(flip_layout)

        layout = QVBoxLayout()
        layout.addWidget(display_box)
        self.setLayout(layout)
        display_box.setMaximumWidth(100)
        display_box.setMaximumHeight(82)

    def flip(self):
        """Send a signal to flip the axes of the plot"""

        self.flip_tree.emit()
