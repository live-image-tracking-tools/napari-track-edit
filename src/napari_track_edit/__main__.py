import argparse
import logging
import sys

import napari

from napari_track_edit.application_menus.main_app import StartupWidget

LOG_FORMAT = "%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s"


def _configure_logging() -> None:
    """Send napari_track_edit's log records to the console.

    Configures our own package logger rather than the root logger, so napari,
    vispy and the rest of the dependency tree keep their own levels.

    Called from main(), not from an ``if __name__ == "__main__"`` block: the
    installed ``napari-track-edit`` command imports this module and calls
    main(), so such a block only runs for ``python -m napari_track_edit``.
    """
    logger = logging.getLogger("napari_track_edit")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def _activate_on_macos(viewer: napari.Viewer) -> None:
    """Force the napari window (and its menu bar) to take focus on macOS.

    When napari is launched as a subprocess of another app (e.g. VS Code's
    integrated terminal), the OS sometimes leaves the parent app's menu bar
    in place even though napari's window is frontmost. Explicitly raising
    and activating the window nudges macOS into handing over the menu bar.
    """
    if sys.platform != "darwin":
        return
    window = viewer.window._qt_window
    window.raise_()
    window.activateWindow()


def main():
    _configure_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["all", "tracking", "editing"],
        default="all",
    )

    args, _ = parser.parse_known_args()

    viewer = napari.Viewer()
    StartupWidget(viewer, mode=args.mode)
    _activate_on_macos(viewer)

    napari.run()


if __name__ == "__main__":
    sys.exit(main())
