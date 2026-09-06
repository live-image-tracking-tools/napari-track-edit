from __future__ import annotations

from typing import TYPE_CHECKING

import napari
from fonticon_fa6 import FA6S
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon as qticon

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

if TYPE_CHECKING:
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class SelectionWidget(QWidget):
    """Widget with buttons to control selection of nodes on TracksViewer."""

    def __init__(self, tracks_viewer: TracksViewer):
        super().__init__()
        self.tracks_viewer = tracks_viewer

        select_widget = QGroupBox("Selection")
        selection_layout = QHBoxLayout()

        # Invert button
        self.invert_btn = QPushButton("Invert selection")
        self.invert_btn.clicked.connect(self._invert_selection)
        self.invert_btn.setToolTip("Select all nodes not in current selection.")

        # Buttons to jump to next or previous node in the selection
        left_arrow = qticon(FA6S.arrow_left, color="white")
        self.jump_to_previous_btn = QPushButton(icon=left_arrow)
        self.jump_to_previous_btn.setToolTip("Navigate to previous selected node.")
        self.jump_to_previous_btn.setEnabled(False)
        self.jump_to_previous_btn.clicked.connect(
            lambda: self._jump_to_node(forward=False)
        )

        right_arrow = qticon(FA6S.arrow_right, color="white")
        self.jump_to_next_btn = QPushButton(icon=right_arrow)
        self.jump_to_next_btn.setToolTip("Navigate to next selected node.")
        self.jump_to_next_btn.setEnabled(False)
        self.jump_to_next_btn.clicked.connect(lambda: self._jump_to_node(forward=True))

        arrow_layout = QHBoxLayout()
        arrow_layout.addWidget(self.jump_to_previous_btn)
        arrow_layout.addWidget(self.jump_to_next_btn)

        # Buttons to select next and previous node set from history
        self.select_next_set_btn = QPushButton("Next Selection [N]")
        self.select_next_set_btn.setToolTip(
            "Select the next set of nodes from the selection history."
        )
        self.select_next_set_btn.setEnabled(False)
        self.select_next_set_btn.clicked.connect(
            lambda: self.tracks_viewer.select_node_set_from_history(previous=False)
        )
        self.select_previous_set_btn = QPushButton("Previous Selection [P]")
        self.select_previous_set_btn.setToolTip(
            "Select the previous set of nodes from the selection history."
        )
        self.select_previous_set_btn.setEnabled(False)
        self.select_previous_set_btn.clicked.connect(
            lambda: self.tracks_viewer.select_node_set_from_history(previous=True)
        )

        # Button to deselect all nodes
        self.deselect_btn = QPushButton("Deselect [ESC]")
        self.deselect_btn.setToolTip("Deselect all nodes.")
        self.deselect_btn.clicked.connect(self.tracks_viewer.deselect)
        self.deselect_btn.setEnabled(False)

        # Button to restore previous selection
        self.reselect_btn = QPushButton("Restore selection [E]")
        self.reselect_btn.setToolTip("Restore the last selection.")
        self.reselect_btn.clicked.connect(self.tracks_viewer.restore_selection)
        self.reselect_btn.setEnabled(False)

        # Organize buttons in two vertical columns
        col1_layout = QVBoxLayout()
        col2_layout = QVBoxLayout()

        col1_layout.addWidget(self.invert_btn)
        col1_layout.addLayout(arrow_layout)
        col1_layout.addWidget(self.select_next_set_btn)
        col2_layout.addWidget(self.deselect_btn)
        col2_layout.addWidget(self.reselect_btn)
        col2_layout.addWidget(self.select_previous_set_btn)

        selection_layout.addLayout(col1_layout)
        selection_layout.addLayout(col2_layout)
        select_widget.setLayout(selection_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(select_widget)
        self.setLayout(main_layout)
        self.setMaximumHeight(180)

        # Connect to selection updates to enable/disable buttons accordingly
        self.tracks_viewer.node_selection_updated.connect(self.update_selection_buttons)

        # Set initial button states
        self.update_selection_buttons()

    def update_selection_buttons(self):
        """Update the button states based on the current node selection (history)"""

        if len(self.tracks_viewer.selected_nodes) > 0:
            self.deselect_btn.setEnabled(True)
            self.jump_to_next_btn.setEnabled(True)
            self.jump_to_previous_btn.setEnabled(True)
        else:
            self.deselect_btn.setEnabled(False)
            self.jump_to_next_btn.setEnabled(False)
            self.jump_to_previous_btn.setEnabled(False)

        self.reselect_btn.setEnabled(
            self.tracks_viewer.selected_nodes.has_valid_last_shown_set
        )
        self.select_next_set_btn.setEnabled(
            self.tracks_viewer.selected_nodes.has_next_set
        )
        self.select_previous_set_btn.setEnabled(
            self.tracks_viewer.selected_nodes.has_previous_set
        )

    def _jump_to_node(self, forward: bool) -> None:
        """Jump to the next/previous selected node in the list"""

        node = self.tracks_viewer.selected_nodes.next_node(forward)
        if node:
            self.tracks_viewer.center_on_node(node)

    def _invert_selection(self) -> None:
        """Invert the current selection"""

        all_nodes = set(self.tracks_viewer.tracks.nodes())
        inverted = list(all_nodes - set(self.tracks_viewer.selected_nodes.as_list))
        self.tracks_viewer.selected_nodes.add_list(inverted, append=False)


class EditingMenu(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.node_selection_updated.connect(self.update_buttons)

        box = QGroupBox("Editing")
        box_layout = QVBoxLayout()

        self.label = QLabel(f"Current Track ID: {self.tracks_viewer.selected_track}")
        self.tracks_viewer.update_track_id.connect(self.update_track_id_color)

        self.new_track_btn = QPushButton("Start new")
        self.new_track_btn.clicked.connect(self.tracks_viewer.request_new_track)
        track_layout = QHBoxLayout()
        track_layout.addWidget(self.label)
        track_layout.addWidget(self.new_track_btn)
        box_layout.addLayout(track_layout)

        node_box = QGroupBox("Edit Node(s)")
        node_box.setMaximumHeight(120)
        node_box_layout = QVBoxLayout()

        self.delete_node_btn = QPushButton("Delete [D]")
        self.delete_node_btn.clicked.connect(self.tracks_viewer.delete_node)
        self.delete_node_btn.setEnabled(False)
        self.swap_nodes_btn = QPushButton("Swap [S]")
        self.swap_nodes_btn.clicked.connect(self.tracks_viewer.swap_nodes)
        self.swap_nodes_btn.setEnabled(False)

        node_box_layout.addWidget(self.delete_node_btn)
        node_box_layout.addWidget(self.swap_nodes_btn)

        node_box.setLayout(node_box_layout)

        edge_box = QGroupBox("Edit Edge(s)")
        edge_box.setMaximumHeight(120)
        edge_box_layout = QVBoxLayout()

        self.connect_nodes_btn = QPushButton("Connect / Disconnect [C]")
        self.connect_nodes_btn.setToolTip(
            "Connect the selected nodes into one track, or break them apart again if "
            "they are already connected. If some of them already have an outgoing "
            "edge, you are asked whether to keep those edges as divisions ([C]) or "
            "to break them into one linear track ([Shift+C])"
        )
        self.connect_nodes_btn.clicked.connect(self.tracks_viewer.connect_nodes)
        self.connect_nodes_btn.setEnabled(False)

        edge_box_layout.addWidget(self.connect_nodes_btn)

        edge_box.setLayout(edge_box_layout)

        self.undo_btn = QPushButton("Undo (Z)")
        self.undo_btn.clicked.connect(self.tracks_viewer.undo)

        self.redo_btn = QPushButton("Redo (R)")
        self.redo_btn.clicked.connect(self.tracks_viewer.redo)

        box_layout.addWidget(node_box)
        box_layout.addWidget(edge_box)
        box_layout.addWidget(self.undo_btn)
        box_layout.addWidget(self.redo_btn)

        box.setLayout(box_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(box)
        self.setLayout(main_layout)
        self.setMaximumHeight(450)

    def update_track_id_color(self):
        """Display track ID value and color"""

        color = self.tracks_viewer.track_id_color
        r, g, b, a = [int(c * 255) if i < 3 else c for i, c in enumerate(color)]
        css_color = f"rgba({r}, {g}, {b}, {a})"
        self.label.setText(f"Current Track ID: {self.tracks_viewer.selected_track}")
        self.label.setStyleSheet(
            f"""
            color: white;
            border: 2px solid {css_color};
            padding: 5px;
            """
        )

    def update_buttons(self):
        """Set the buttons to enabled/disabled depending on the selected nodes"""

        n_selected = len(self.tracks_viewer.selected_nodes)
        if n_selected == 0:
            self.delete_node_btn.setEnabled(False)
            self.connect_nodes_btn.setEnabled(False)
            self.swap_nodes_btn.setEnabled(False)

        elif n_selected == 2:
            self.delete_node_btn.setEnabled(True)
            self.connect_nodes_btn.setEnabled(True)
            self.swap_nodes_btn.setEnabled(True)

        else:
            self.delete_node_btn.setEnabled(True)
            self.connect_nodes_btn.setEnabled(n_selected > 2)
            self.swap_nodes_btn.setEnabled(False)


class EditingSelectionWidget(QWidget):
    """Combined widget for editing and selection controls"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        editing_widget = EditingMenu(viewer)
        selection_widget = SelectionWidget(self.tracks_viewer)
        selection_editing_layout = QVBoxLayout()
        selection_editing_layout.addWidget(editing_widget)
        selection_editing_layout.addWidget(selection_widget)
        selection_editing_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(selection_editing_layout)
        self.setMaximumHeight(600)
