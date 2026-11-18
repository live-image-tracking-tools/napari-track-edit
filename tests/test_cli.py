import logging
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize("mode", ["all", "tracking", "editing"])
def test_main_entrypoint(mode):
    """CLI entrypoint passes correct mode to StartupWidget."""

    viewer = MagicMock(name="viewer")

    with (
        patch("napari_track_edit.__main__.napari.Viewer", return_value=viewer),
        patch("napari_track_edit.__main__.napari.run"),
        patch("napari_track_edit.data_views.views.ortho_views.initialize_ortho_views"),
        patch("napari_track_edit.__main__.StartupWidget") as mock_widget,
        patch.object(sys, "argv", ["prog", "--mode", mode]),
    ):
        from napari_track_edit.__main__ import main

        main()

    mock_widget.assert_called_once()
    args, kwargs = mock_widget.call_args

    # First positional arg should be viewer
    assert args[0] is viewer

    # mode should match CLI flag
    assert kwargs["mode"] == mode


def test_main_configures_package_logging():
    """main() must set logging up itself.

    The installed `napari-track-edit` command imports this module and calls
    main(), so configuration behind an `if __name__ == "__main__"` block would
    never run for the normal way of starting the app.
    """
    package_logger = logging.getLogger("napari_track_edit")
    original_handlers = package_logger.handlers[:]
    original_level = package_logger.level
    package_logger.handlers = []
    package_logger.setLevel(logging.NOTSET)
    # pytest installs its own root handlers, so compare before/after rather than
    # asserting the root logger is bare.
    root_handlers_before = logging.getLogger().handlers[:]

    try:
        with (
            patch("napari_track_edit.__main__.napari.Viewer", return_value=MagicMock()),
            patch("napari_track_edit.__main__.napari.run"),
            patch(
                "napari_track_edit.data_views.views.ortho_views.initialize_ortho_views"
            ),
            patch("napari_track_edit.__main__.StartupWidget"),
            patch.object(sys, "argv", ["prog"]),
        ):
            from napari_track_edit.__main__ import main

            main()

        assert package_logger.handlers, "main() did not add a log handler"
        assert package_logger.level == logging.DEBUG
        # Our logs go through our own logger, so the root one is left alone.
        assert logging.getLogger().handlers == root_handlers_before
    finally:
        package_logger.handlers = original_handlers
        package_logger.setLevel(original_level)


def test_main_opens_path_after_startup(tmp_path):
    """A path argument is loaded once the event loop starts, not before."""

    viewer = MagicMock(name="viewer")

    with (
        patch("napari_track_edit.__main__.napari.Viewer", return_value=viewer),
        patch("napari_track_edit.__main__.napari.run"),
        patch("napari_track_edit.__main__.StartupWidget"),
        patch("napari_track_edit.__main__.QTimer") as mock_timer,
        patch("napari_track_edit.__main__.TracksViewer") as mock_tracks_viewer,
        patch.object(sys, "argv", ["prog", str(tmp_path)]),
    ):
        from napari_track_edit.__main__ import main

        main()

        mock_timer.singleShot.assert_called_once()
        _, callback = mock_timer.singleShot.call_args.args
        callback()

    tracks_viewer = mock_tracks_viewer.get_instance.return_value
    tracks_viewer.tracks_list.load_tracks_from_path.assert_called_once_with(
        tmp_path.resolve()
    )
    tracks_viewer.menu_manager.set_foreground_tabs.assert_called_once_with(
        ["Tracks List"]
    )


def test_main_without_path_loads_nothing():
    with (
        patch("napari_track_edit.__main__.napari.Viewer", return_value=MagicMock()),
        patch("napari_track_edit.__main__.napari.run"),
        patch("napari_track_edit.__main__.StartupWidget"),
        patch("napari_track_edit.__main__.QTimer") as mock_timer,
        patch.object(sys, "argv", ["prog"]),
    ):
        from napari_track_edit.__main__ import main

        main()

    mock_timer.singleShot.assert_not_called()


def test_main_rejects_missing_path(tmp_path):
    with (
        patch("napari_track_edit.__main__.napari.Viewer") as mock_viewer,
        patch.object(sys, "argv", ["prog", str(tmp_path / "missing.geff")]),
        pytest.raises(SystemExit),
    ):
        from napari_track_edit.__main__ import main

        main()

    mock_viewer.assert_not_called()
