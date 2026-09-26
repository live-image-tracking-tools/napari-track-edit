"""Tests for the sample tracks shown as examples in the welcome widget."""

import re
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.request import Request, urlopen

import numpy as np
import pytest
from qtpy.QtCore import QUrl
from qtpy.QtWidgets import QMessageBox, QProgressDialog, QTextBrowser, QWidget

from motile_tracker import example_data
from motile_tracker.application_menus import welcome_widget as welcome_module
from motile_tracker.application_menus.main_app import MENU_WIDGETS
from motile_tracker.application_menus.menu_manager import MenuManager
from motile_tracker.application_menus.welcome_widget import (
    EXAMPLE_SCHEME,
    WelcomeWidget,
)
from motile_tracker.data_views.views_coordinator.tracks_list import TracksList
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.download_progress import MB, DownloadCancelled, download_progress
from motile_tracker.example_data import (
    CTC_URL_TEMPLATE,
    SAMPLE_TRACKS,
    ZENODO_LABELS_URL,
    ZENODO_RAW_URL,
    sample_tracks_path,
)
from motile_tracker.import_export.geff_io import write_geff_over

HELA = "Hela cells (2D)"
EMBRYO = "Mouse embryo (3D)"

# Everything the app downloads, so that a source going stale (moved, unshared,
# quota exceeded) fails here rather than under a user's click.
DOWNLOAD_SOURCES = {
    "sample images: Fluo-N2DL-HeLa (CTC)": CTC_URL_TEMPLATE.format(
        ds_name="Fluo-N2DL-HeLa"
    ),
    "sample images: Mouse_Embryo_Membrane raw (zenodo)": ZENODO_RAW_URL,
    "sample images: Mouse_Embryo_Membrane labels (zenodo)": ZENODO_LABELS_URL,
    **{f"sample tracks: {name}": s.url for name, s in SAMPLE_TRACKS.items()},
}


@pytest.mark.parametrize("name", list(DOWNLOAD_SOURCES))
def test_download_sources_are_reachable(name):
    """Everything the app downloads is still available. Fetches the first byte
    only. Google Drive and Zenodo answer with an html page rather than an error
    status when a file is unshared, removed, or over its quota."""
    request = Request(DOWNLOAD_SOURCES[name], headers={"Range": "bytes=0-0"})
    with urlopen(request, timeout=30) as response:
        assert response.status in (200, 206), f"{name}: HTTP {response.status}"
        content_type = response.headers.get("Content-Type", "")
        assert "text/html" not in content_type, (
            f"{name}: served an html page instead of the file ({content_type})"
        )
        assert response.read(1), f"{name}: empty response body"


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    """Fail instead of blocking when a test opens a modal dialog. There is
    nobody to click it away in CI, so the run would hang until the job times
    out. Tests that expect a dialog patch it themselves, which overrides this.
    """
    for name in ("question", "information", "warning", "critical"):

        def fail(*args, _name=name, **kwargs):
            text = next((a for a in args if isinstance(a, str)), "")
            pytest.fail(f"unexpected modal QMessageBox.{_name}: {text}")

        monkeypatch.setattr(QMessageBox, name, fail)


@pytest.fixture
def user_data_dir(tmp_path, monkeypatch) -> Path:
    """Point the platformdirs "user data dir" at a temporary directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(
        example_data,
        "PlatformDirs",
        lambda _: type("Dirs", (), {"user_data_dir": str(data_dir)}),
    )
    return data_dir


def _fake_urlretrieve(downloads: list[str], content: dict[str, bytes]):
    """An urlretrieve that writes a zip with the given files, recording the urls."""

    def urlretrieve(url, filename, reporthook=None):
        downloads.append(url)
        with zipfile.ZipFile(filename, "w") as zip_ref:
            for name, data in content.items():
                zip_ref.writestr(name, data)

    return urlretrieve


def test_sample_tracks_path_skips_download_if_present(user_data_dir, monkeypatch):
    store = user_data_dir / SAMPLE_TRACKS[HELA].store_name
    store.mkdir()
    downloads = []
    monkeypatch.setattr(example_data, "urlretrieve", _fake_urlretrieve(downloads, {}))
    assert sample_tracks_path(HELA) == store
    assert downloads == []


def test_sample_tracks_path_downloads_if_missing(user_data_dir, monkeypatch):
    store_name = SAMPLE_TRACKS[EMBRYO].store_name
    downloads = []
    content = {f"{store_name}/.zattrs": b"{}", f"{store_name}/.zgroup": b"{}"}
    monkeypatch.setattr(
        example_data, "urlretrieve", _fake_urlretrieve(downloads, content)
    )

    path = sample_tracks_path(EMBRYO)
    assert downloads == [SAMPLE_TRACKS[EMBRYO].url]
    assert path == user_data_dir / store_name
    assert (path / ".zattrs").exists()  # hidden files survive
    assert [p.name for p in user_data_dir.iterdir()] == [store_name]

    # second call uses the downloaded data
    sample_tracks_path(EMBRYO)
    assert len(downloads) == 1


def test_refused_download_leaves_no_data(user_data_dir, monkeypatch):
    """Google Drive serving an html page instead of the zip is an error."""

    def urlretrieve(url, filename, reporthook=None):
        Path(filename).write_text("<html>quota exceeded</html>")

    monkeypatch.setattr(example_data, "urlretrieve", urlretrieve)
    with pytest.raises(RuntimeError, match="refused"):
        sample_tracks_path(HELA)
    assert list(user_data_dir.iterdir()) == []


def test_zip_without_store_leaves_no_data(user_data_dir, monkeypatch):
    content = {"other.geff/.zattrs": b"{}"}
    monkeypatch.setattr(example_data, "urlretrieve", _fake_urlretrieve([], content))
    with pytest.raises(RuntimeError, match="does not contain"):
        sample_tracks_path(HELA)
    assert list(user_data_dir.iterdir()) == []


def test_tracks_list_load_sample_tracks(
    qtbot, tmp_path, monkeypatch, solution_tracks_2d
):
    """Loading a sample adds it to the tracks list and announces where it came from."""
    geff_path = tmp_path / "sample.geff"
    write_geff_over(solution_tracks_2d, geff_path)
    module = "motile_tracker.data_views.views_coordinator.tracks_list"
    monkeypatch.setattr(
        f"{module}.sample_tracks_path", lambda name, reporthook=None: geff_path
    )

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
        # the raw data counts as present, so no download prompt is shown
        monkeypatch.setattr(
            welcome_module, "raw_data_is_downloaded", lambda _name: True
        )
        monkeypatch.setitem(SAMPLE_TRACKS, name, sample._replace(load_raw=load_raw))

    widget = WelcomeWidget(viewer)
    qtbot.addWidget(widget)
    widget.calls = calls
    return widget


def _click_example(widget: WelcomeWidget, name: str) -> None:
    """Click the example link for `name` in the welcome widget."""
    browser = next(
        b for b in widget.findChildren(QTextBrowser) if EXAMPLE_SCHEME in b.toHtml()
    )
    links = {
        QUrl(a).path()
        for a in re.findall(rf'href="({EXAMPLE_SCHEME}:[^"]+)"', browser.toHtml())
    }
    assert links == set(SAMPLE_TRACKS)
    widget._on_link_clicked(QUrl(f"{EXAMPLE_SCHEME}:{name}"))


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
    # the raw data is not what this test is about, and asking to download it
    # would open a modal dialog
    monkeypatch.setattr(welcome_module, "raw_data_is_downloaded", lambda _name: True)
    monkeypatch.setattr(welcome, "_add_raw_layer", lambda name: True)
    monkeypatch.setattr(tracks_list, "load_sample_tracks", MagicMock())
    _click_example(welcome, HELA)

    tracks_list.load_sample_tracks.assert_called_once_with(HELA)
    assert "Tracks List" not in manager.menu_widgets  # not shown again

    # reopening the menu shows the same list, tracks included
    manager.initialize_menu({"Tracks List": MENU_WIDGETS["Tracks List"]})
    assert manager.menu_widgets["Tracks List"].widget().tracks_list is tracks_list
    assert tracks_list.tracks_list.count() == 1


def test_download_progress_reports_bytes(qtbot):
    """The report hook drives the bar while bytes come in, and switches to a
    busy indicator once the file is in and is being unpacked."""
    parent = QWidget()
    qtbot.addWidget(parent)
    with download_progress(parent, "test data") as reporthook:
        dialog = parent.findChild(QProgressDialog)
        reporthook(1, 10 * MB, 100 * MB)
        assert (dialog.minimum(), dialog.maximum()) == (0, 100 * MB)
        assert dialog.value() == 10 * MB
        assert "10 / 100 MB" in dialog.labelText()

        reporthook(10, 10 * MB, 100 * MB)  # all bytes received
        assert dialog.maximum() == 0  # busy indicator
        assert "Preparing" in dialog.labelText()


def test_download_progress_cancel(qtbot):
    """Pressing cancel interrupts the download through the report hook."""
    parent = QWidget()
    qtbot.addWidget(parent)
    with download_progress(parent, "test data") as reporthook:
        reporthook(1, 1024, 1024 * 1024)
        parent.findChild(QProgressDialog).cancel()
        with pytest.raises(DownloadCancelled):
            reporthook(2, 1024, 1024 * 1024)


@pytest.mark.parametrize(
    ("answer", "loaded"), [(QMessageBox.Yes, True), (QMessageBox.No, False)]
)
def test_raw_download_is_confirmed_first(welcome_widget, monkeypatch, answer, loaded):
    """Downloading the images of an example is a few hundred megabytes, so it is
    only started once the user agrees to it."""
    monkeypatch.setattr(welcome_module, "raw_data_is_downloaded", lambda _name: False)
    asked = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: asked.append(args) or answer,
    )

    _click_example(welcome_widget, HELA)

    assert len(asked) == 1
    assert SAMPLE_TRACKS[HELA].raw_size in asked[0][2]
    calls = welcome_widget.calls
    assert calls.add_image.called is loaded
    assert calls.tracks_list.load_sample_tracks.called is loaded
