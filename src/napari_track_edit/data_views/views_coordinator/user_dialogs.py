from functools import partial

from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from napari_track_edit.data_views.keybindings_config import shortcut_label


def confirm_force_operation(message: str) -> tuple[bool, bool]:
    """
    Ask the user if they want to force the operation by breaking conflicting edges.

    Returns:
        (force_now, set_always)
        - force_now: True if user selected 'Yes' or 'Yes, always'
        - set_always: True if user selected 'Yes, always'
    """

    msg = QMessageBox()
    msg.setWindowTitle("Force operation?")
    msg.setTextFormat(Qt.PlainText)

    message += "\n\nDo you want to force this operation by breaking conflicting edges?"
    msg.setText(message)
    msg.setIconPixmap(QIcon.fromTheme("dialog-question").pixmap(64, 64))

    yes_button = msg.addButton("Yes", QMessageBox.YesRole)
    always_button = msg.addButton("Yes, always", QMessageBox.AcceptRole)
    msg.addButton("No", QMessageBox.NoRole)

    msg.setDefaultButton(yes_button)

    msg.exec_()
    clicked = msg.clickedButton()

    if clicked == yes_button:
        return True, False
    elif clicked == always_button:
        return True, True
    else:
        return False, False


def ask_connect_mode() -> bool | None:
    """
    Ask whether the selected nodes should be connected with divisions or linearly.

    Returns:
        True to connect linearly, False to connect with divisions, and None if the
        user cancelled.
    """

    msg = QMessageBox()
    msg.setWindowTitle("Connect nodes")
    msg.setTextFormat(Qt.PlainText)
    msg.setText(
        "One or more of the selected nodes already has an outgoing edge.\n\n"
        "Connect with divisions to keep those edges, or connect linearly to break "
        "them and turn the selection into one linear track."
    )
    msg.setIconPixmap(QIcon.fromTheme("dialog-question").pixmap(64, 64))

    divisions_button = msg.addButton(
        shortcut_label("connect_nodes_with_divisions", "With divisions"),
        QMessageBox.YesRole,
    )
    linear_button = msg.addButton(
        shortcut_label("connect_nodes_linearly", "Linear"), QMessageBox.AcceptRole
    )
    msg.addButton("Cancel", QMessageBox.RejectRole)

    msg.setDefaultButton(divisions_button)

    msg.exec_()
    clicked = msg.clickedButton()

    if clicked is divisions_button:
        return False
    elif clicked is linear_button:
        return True
    else:
        return None


def _track_id_button_style(color) -> str:
    """Style a tracklet ID button with the color that tracklet has in the viewer."""

    r, g, b = (int(channel * 255) for channel in color[:3])
    return f"""
        QPushButton {{
            border: 3px solid rgb({r}, {g}, {b});
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: bold;
            background-color: rgba({r}, {g}, {b}, 40);
        }}
        QPushButton:hover {{
            background-color: rgba({r}, {g}, {b}, 100);
        }}
    """


class MergeTrackIDDialog(QDialog):
    """Dialog asking which tracklet ID a set of merged nodes should keep.

    Shows one button per tracklet ID, bordered in the color that tracklet has in
    the viewer, plus a cancel button. The chosen ID is available as
    :attr:`track_id` after the dialog closes, and is None if the user cancelled.
    """

    def __init__(self, track_ids: list[int], times: list[int], colormap, parent=None):
        """
        Args:
            track_ids: The tracklet IDs of the nodes that will be merged.
            times: The time points in which this set of tracklet IDs is merged.
            colormap: The viewer colormap, used to color each tracklet ID button.
            parent: The parent widget of the dialog. Defaults to None.
        """

        super().__init__(parent)
        self.setWindowTitle("Merge nodes")
        self.track_id: int | None = None

        if len(times) == 1:
            where = f"time point {times[0]}"
        else:
            where = "time points " + ", ".join(str(time) for time in times)

        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                f"The selected nodes in {where} will be merged into one node.\n"
                "Which tracklet ID should the merged node keep?"
            )
        )

        self.track_id_btns: dict[int, QPushButton] = {}
        track_id_layout = QHBoxLayout()
        for track_id in track_ids:
            button = QPushButton(str(track_id))
            button.setStyleSheet(_track_id_button_style(colormap.map(track_id)))
            button.clicked.connect(partial(self._select, track_id))
            track_id_layout.addWidget(button)
            self.track_id_btns[track_id] = button
        layout.addLayout(track_id_layout)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

        self.setLayout(layout)

    def _select(self, track_id: int) -> None:
        """Store the clicked tracklet ID and close the dialog."""

        self.track_id = track_id
        self.accept()


def select_merge_track_id(
    track_ids: list[int], times: list[int], colormap
) -> int | None:
    """
    Ask the user which of the given tracklet IDs the merged node should keep.

    Args:
        track_ids: The tracklet IDs of the nodes that will be merged.
        times: The time points in which this set of tracklet IDs is merged.
        colormap: The viewer colormap, used to color each tracklet ID button.

    Returns:
        The chosen tracklet ID, or None if the user cancelled.
    """

    dialog = MergeTrackIDDialog(track_ids, times, colormap)
    dialog.exec_()
    return dialog.track_id
