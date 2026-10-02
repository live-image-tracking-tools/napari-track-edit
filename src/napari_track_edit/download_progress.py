"""A progress dialog for the downloads of the example data.

The downloads run on the main thread, so the dialog is kept alive by processing
events from the `urlretrieve` report hook. This keeps `example_data` free of Qt,
which is also what lets it be used from a script or a notebook.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QProgressDialog, QWidget

MB = 1024 * 1024


class DownloadCancelled(Exception):
    """Raised inside the report hook when the user presses cancel."""


@contextmanager
def download_progress(
    parent: QWidget, label: str
) -> Iterator[Callable[[int, int, int], None]]:
    """Show a modal progress dialog, yielding a hook to report download progress.

    The hook has the signature `urlretrieve` expects, so it can be passed
    straight to it. Downloads of several files in a row are shown one after the
    other, because each of them starts counting blocks at zero again. Once a
    file is in, the bar switches to a busy indicator, since unpacking and
    converting the data reports no progress but does take a while.

    Args:
        parent (QWidget): Widget to center the dialog on
        label (str): What is being downloaded, shown above the bar

    Yields:
        Callable[[int, int, int], None]: `urlretrieve` report hook

    Raises:
        DownloadCancelled: From the hook, if the user pressed cancel
    """
    dialog = QProgressDialog(f"Downloading {label}...", "Cancel", 0, 0, parent)
    dialog.setWindowTitle("Example data")
    dialog.setWindowModality(Qt.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    def reporthook(block_num: int, block_size: int, total_size: int) -> None:
        if dialog.wasCanceled():
            raise DownloadCancelled(label)
        received = block_num * block_size
        if total_size > 0 and received < total_size:
            dialog.setRange(0, total_size)
            dialog.setValue(received)
            dialog.setLabelText(
                f"Downloading {label}... {received / MB:.0f} / {total_size / MB:.0f} MB"
            )
        else:  # done, or a server that does not report a size
            dialog.setRange(0, 0)  # busy indicator
            dialog.setLabelText(f"Preparing {label}...")
        QApplication.processEvents()

    dialog.show()
    QApplication.processEvents()
    try:
        yield reporthook
    finally:
        dialog.close()
