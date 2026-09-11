import logging
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize("mode", ["all", "tracking", "editing"])
def test_main_entrypoint(mode):
    """CLI entrypoint passes correct mode to StartupWidget."""

    viewer = MagicMock(name="viewer")

    with (
        patch("motile_tracker.__main__.napari.Viewer", return_value=viewer),
        patch("motile_tracker.__main__.napari.run"),
        patch("motile_tracker.data_views.views.ortho_views.initialize_ortho_views"),
        patch("motile_tracker.__main__.StartupWidget") as mock_widget,
        patch.object(sys, "argv", ["prog", "--mode", mode]),
    ):
        from motile_tracker.__main__ import main

        main()

    mock_widget.assert_called_once()
    args, kwargs = mock_widget.call_args

    # First positional arg should be viewer
    assert args[0] is viewer

    # mode should match CLI flag
    assert kwargs["mode"] == mode


def test_main_configures_package_logging():
    """main() must set logging up itself.

    The installed `motile_tracker` command imports this module and calls main(),
    so configuration behind an `if __name__ == "__main__"` block would never run
    for the normal way of starting the app.
    """
    package_logger = logging.getLogger("motile_tracker")
    original_handlers = package_logger.handlers[:]
    original_level = package_logger.level
    package_logger.handlers = []
    package_logger.setLevel(logging.NOTSET)
    # pytest installs its own root handlers, so compare before/after rather than
    # asserting the root logger is bare.
    root_handlers_before = logging.getLogger().handlers[:]

    try:
        with (
            patch("motile_tracker.__main__.napari.Viewer", return_value=MagicMock()),
            patch("motile_tracker.__main__.napari.run"),
            patch("motile_tracker.data_views.views.ortho_views.initialize_ortho_views"),
            patch("motile_tracker.__main__.StartupWidget"),
            patch.object(sys, "argv", ["prog"]),
        ):
            from motile_tracker.__main__ import main

            main()

        assert package_logger.handlers, "main() did not add a log handler"
        assert package_logger.level == logging.DEBUG
        # Our logs go through our own logger, so the root one is left alone.
        assert logging.getLogger().handlers == root_handlers_before
    finally:
        package_logger.handlers = original_handlers
        package_logger.setLevel(original_level)
