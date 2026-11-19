"""Tests for where history logs are written."""

from napari_track_edit.history import paths


def test_slug():
    assert paths.slug("Teun Huijben") == "teun_huijben"
    assert paths.slug("a/b\\c") == "a_b_c"
    assert paths.slug("???") == "unknown"


def test_sidecar_dir(tmp_path):
    assert paths.sidecar_dir(tmp_path / "x.geff") == tmp_path / "x.geff.history"
    assert paths.sidecar_dir(tmp_path / "x.csv") == tmp_path / "x.csv.history"


def test_new_log_paths_are_unique(tmp_path):
    first = paths.new_log_path(tmp_path, "ann")
    second = paths.new_log_path(tmp_path, "ann")
    assert first != second
    assert first.parent == tmp_path
    assert first.suffix == ".jsonl"


def test_is_writable_creates_nothing(tmp_path):
    directory = tmp_path / "a.geff.history"
    assert paths.is_writable(directory)
    assert not directory.exists()
