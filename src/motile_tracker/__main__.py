import argparse
import sys

import napari
import logging

from motile_tracker.application_menus.main_app import StartupWidget


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

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s",
    )
    logging.getLogger("motile_tracker").setLevel(logging.DEBUG)
    sys.exit(main())
