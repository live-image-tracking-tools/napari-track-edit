import sys

from qtpy.QtWidgets import QFileDialog


def load_dialog_options(directories: bool = False) -> QFileDialog.Option:
    """Options for the file dialogs that pick something to load.

    On Linux the Qt-drawn dialog is used instead of the native one: inside the
    app, the native dialog (seen on Ubuntu 22.04) ignores the start directory
    and opens at "Recent", so the last load location could not be offered.

    Args:
        directories (bool): the dialog picks a directory, so only show those.
            Passed explicitly because giving options replaces the ShowDirsOnly
            that getExistingDirectory sets by default.
    """
    options = QFileDialog.Option(0)
    if directories:
        options |= QFileDialog.Option.ShowDirsOnly
    if sys.platform.startswith("linux"):
        options |= QFileDialog.Option.DontUseNativeDialog
    return options
