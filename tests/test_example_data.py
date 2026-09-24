"""Tests for the sample tracks shown as examples in the welcome widget."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.request import urlopen

import numpy as np
import pytest
from qtpy.QtWidgets import QPushButton

from motile_tracker import example_data
from motile_tracker.application_menus.main_app import MENU_WIDGETS
from motile_tracker.application_menus.menu_manager import MenuManager
from motile_tracker.application_menus.welcome_widget import WelcomeWidget
from motile_tracker.data_views.views_coordinator.tracks_list import TracksList
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.example_data import SAMPLE_TRACKS, sample_tracks_path
from motile_tracker.import_export.geff_io import write_geff_over

HELA = "Hela cells (2D)"
EMBRYO = "Mouse embryo (3D)"


@pytest.mark.parametrize("name", list(SAMPLE_TRACKS))
def test_sample_tracks_links(name):
    """The Google Drive folders with the sample tracks are still reachable
    (Drive answers 404 for removed or unshared folders)."""
    url = SAMPLE_TRACKS[name].url
    with urlopen(url, timeout=30) as response:
        assert response.status == 200


@pytest.fixture
def user_data_dir(tmp_path, monkeypatch) -> Path:
    """Point the appdir "user data dir" at a temporary directory."""
    monkeypatch.setattr(
        example_data,
        "AppDirs",
        lambda _: type("Dirs", (), {"user_data_dir": str(tmp_path)}),
    )
    return tmp_path


def test_sample_tracks_path_skips_download_if_present(user_data_dir, monkeypatch):
    name = HELA
    store = user_data_dir / SAMPLE_TRACKS[name].store_name
    store.mkdir()

    def fail(*args, **kwargs):
        raise AssertionError("should not download")

    monkeypatch.setattr(example_data, "download_drive_folder", fail)
    assert sample_tracks_path(name) == store


def test_sample_tracks_path_downloads_if_missing(user_data_dir, monkeypatch):
    name = EMBRYO
    downloads = []

    def fake_download_folder(url, output, **kwargs):
        downloads.append(url)
        Path(output).mkdir()
        (Path(output) / "zarr.json").touch()
        return [str(Path(output) / "zarr.json")]

    monkeypatch.setattr(example_data.gdown, "download_folder", fake_download_folder)
    path = sample_tracks_path(name)
    assert downloads == [SAMPLE_TRACKS[name].url]
    assert path == user_data_dir / SAMPLE_TRACKS[name].store_name
    assert (path / "zarr.json").exists()
    assert not path.with_name(path.name + ".download").exists()

    # second call uses the downloaded data
    sample_tracks_path(name)
    assert len(downloads) == 1


def test_failed_download_leaves_no_data(user_data_dir, monkeypatch):
    name = HELA
    monkeypatch.setattr(example_data.gdown, "download_folder", lambda **kwargs: None)
    with pytest.raises(RuntimeError):
        sample_tracks_path(name)
    assert list(user_data_dir.iterdir()) == []


def test_tracks_list_load_sample_tracks(
    qtbot, tmp_path, monkeypatch, solution_tracks_2d
):
    """Loading a sample adds it to the tracks list and announces where it came from."""
    geff_path = tmp_path / "sample.geff"
    write_geff_over(solution_tracks_2d, geff_path)
    module = "motile_tracker.data_views.views_coordinator.tracks_list"
    monkeypatch.setattr(f"{module}.sample_tracks_path", lambda name: geff_path)

    # a modal error dialog would block the test, so fail on it instead
    def fail(parent, title, text):
        raise AssertionError(text)

    monkeypatch.setattr(f"{module}.QMessageBox.critical", fail)

    tracks_list = TracksList()
    qtbot.addWidget(tracks_list)
    with qtbot.waitSignal(tracks_list.tracks_loaded) as blocker:
        tracks_list.load_sample_tracks(HELA)

    assert tracks_list.tracks_list.count() == 1
    row = tracks_list.tracks_list.itemWidget(tracks_list.tracks_list.item(0))
    assert row.name.text() == HELA
    assert row.tracks.graph.num_nodes() == solution_tracks_2d.graph.num_nodes()
    assert blocker.args[1] == geff_path


@pytest.fixture
def welcome_widget(qtbot, monkeypatch):
    """A WelcomeWidget on a fake viewer, whose raw data loaders and tracks list
    are mocks sharing one call record (to check the order of the calls)."""
    calls = MagicMock()
    viewer = SimpleNamespace(layers=[], add_image=calls.add_image)
    monkeypatch.setattr(
        TracksViewer,
        "get_instance",
        lambda v: (
            SimpleNamespace(tracks_list=calls.tracks_list) if v is viewer else None
        ),
    )
    for name, sample in SAMPLE_TRACKS.items():
        load_raw = getattr(calls, sample.raw_name)
        load_raw.return_value = (
            np.zeros((2, 4, 4)),
            {"name": sample.raw_name},
            "image",
        )
        monkeypatch.setitem(SAMPLE_TRACKS, name, sample._replace(load_raw=load_raw))

    widget = WelcomeWidget(viewer)
    qtbot.addWidget(widget)
    widget.calls = calls
    return widget


def _click_example(widget: WelcomeWidget, name: str) -> None:
    buttons = {
        b.text(): b
        for b in widget.findChildren(QPushButton)
        if b.text() in SAMPLE_TRACKS
    }
    assert set(buttons) == set(SAMPLE_TRACKS)
    buttons[name].click()


def test_welcome_widget_example_buttons(welcome_widget):
    """The example buttons add the raw data to the viewer, then load the sample
    tracks into the tracks list."""
    _click_example(welcome_widget, EMBRYO)
    calls = welcome_widget.calls
    assert [c[0] for c in calls.mock_calls] == [
        "01_membrane",
        "add_image",
        "tracks_list.load_sample_tracks",
    ]
    assert calls.add_image.call_args.kwargs == {"name": "01_membrane"}
    calls.tracks_list.load_sample_tracks.assert_called_once_with(EMBRYO)


def test_welcome_widget_reuses_raw_layer(welcome_widget):
    """The raw data is not loaded again if its layer is already in the viewer."""
    welcome_widget.viewer.layers.append("01_raw")
    _click_example(welcome_widget, HELA)
    calls = welcome_widget.calls
    assert getattr(calls, "01_raw").call_count == 0
    calls.add_image.assert_not_called()
    calls.tracks_list.load_sample_tracks.assert_called_once_with(HELA)


def test_example_after_closing_tracks_list(make_napari_viewer, qtbot, monkeypatch):
    """Closing the Tracks List tab keeps the shared TracksList (and its tracks)
    alive, so an example can still be loaded into it without showing it."""
    viewer = make_napari_viewer()
    manager = MenuManager(viewer)
    manager.initialize_menu({"Tracks List": MENU_WIDGETS["Tracks List"]})
    tracks_list = TracksViewer.get_instance(viewer).tracks_list
    tracks_list.add_tracks(MagicMock(), "existing", select=False)

    menu_widget = manager.menu_widgets["Tracks List"].widget()
    dock = viewer.window._wrapped_dock_widgets["Tracks List"]
    with qtbot.waitSignal(menu_widget.destroyed, timeout=5000):
        dock.destroyOnClose()  # what the tab's close button calls
    assert tracks_list.tracks_list.count() == 1  # not deleted

    welcome = WelcomeWidget(viewer)
    qtbot.addWidget(welcome)
    monkeypatch.setattr(welcome, "_add_raw_layer", lambda name: None)
    monkeypatch.setattr(tracks_list, "load_sample_tracks", MagicMock())
    _click_example(welcome, HELA)

    tracks_list.load_sample_tracks.assert_called_once_with(HELA)
    assert "Tracks List" not in manager.menu_widgets  # not shown again

    # reopening the menu shows the same list, tracks included
    manager.initialize_menu({"Tracks List": MENU_WIDGETS["Tracks List"]})
    assert manager.menu_widgets["Tracks List"].widget().tracks_list is tracks_list
    assert tracks_list.tracks_list.count() == 1
