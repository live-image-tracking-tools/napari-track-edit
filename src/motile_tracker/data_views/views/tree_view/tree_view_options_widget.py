from psygnal import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)


class TreeViewOptionsWidget(QWidget):
    """Checkboxes for what the tree view annotates its nodes and axes with"""

    show_track_ids_changed = Signal(bool)
    show_hover_info_changed = Signal(bool)

    def __init__(self, show_track_ids: bool = False, show_hover_info: bool = True):
        super().__init__()

        display_box = QGroupBox("Show")
        display_layout = QHBoxLayout()

        self.track_ids_checkbox = QCheckBox("Track IDs")
        self.track_ids_checkbox.setChecked(show_track_ids)
        self.track_ids_checkbox.setToolTip(
            "Label the track axis with the track ID of each lane"
        )
        self.track_ids_checkbox.stateChanged.connect(
            lambda: self.show_track_ids_changed.emit(
                self.track_ids_checkbox.isChecked()
            )
        )
        display_layout.addWidget(self.track_ids_checkbox)

        self.hover_info_checkbox = QCheckBox("Hover info")
        self.hover_info_checkbox.setChecked(show_hover_info)
        self.hover_info_checkbox.setToolTip(
            "Show a tooltip with node, track and lineage ID when hovering over a node"
        )
        self.hover_info_checkbox.stateChanged.connect(
            lambda: self.show_hover_info_changed.emit(
                self.hover_info_checkbox.isChecked()
            )
        )
        display_layout.addWidget(self.hover_info_checkbox)

        display_box.setLayout(display_layout)
        display_box.setMaximumWidth(230)
        display_box.setMaximumHeight(60)

        layout = QVBoxLayout()
        layout.addWidget(display_box)
        self.setLayout(layout)
