from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QMessageBox


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

    divisions_button = msg.addButton("With divisions [C]", QMessageBox.YesRole)
    linear_button = msg.addButton("Linear [Shift+C]", QMessageBox.AcceptRole)
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
