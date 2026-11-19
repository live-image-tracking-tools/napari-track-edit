"""Tests for the history log of the tracks in the tracks list.

The log format, recorder and replay are funtracks' (funtracks.history); these tests
cover what NTE adds: where logs go, the annotator name, the log rollover on save,
the end of the logs on quit, and group create/delete going through actions.
"""

import json
from pathlib import Path

import pytest
from funtracks.cli import compare_tracks
from funtracks.history import replay
from funtracks.import_export import import_from_geff, write_to_geff
from funtracks.user_actions import UserDeleteEdge, UserDeleteNode
from qtpy.QtCore import Qt

from napari_track_edit.data_views.views_coordinator.tracks_list import TracksList
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer
from napari_track_edit.history import paths
from napari_track_edit.history.session import load_annotator
from napari_track_edit.import_export.sql_io import tracks_from_sql, write_tracks_to_sql


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    yield
    viewer.layers.clear()


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def types(path: Path) -> list[str]:
    return [line["type"] for line in read_lines(path)]


@pytest.fixture
def geff_path(solution_tracks_2d, tmp_path) -> Path:
    path = tmp_path / "tracks.geff"
    write_to_geff(solution_tracks_2d, path)
    return path


@pytest.fixture
def loaded(geff_path, viewer):
    """A tracks list holding tracks loaded from a geff, as the load button does."""
    tracks_list = TracksList()
    tracks = import_from_geff(geff_path)
    tracks_list._add_loaded((tracks, "tracks", geff_path))
    yield tracks_list, tracks
    tracks_list.close_history()


def row(tracks_list: TracksList, index: int = 0):
    return tracks_list.tracks_list.itemWidget(tracks_list.tracks_list.item(index))


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------


def test_log_next_to_loaded_geff_replays(loaded, geff_path):
    tracks_list, tracks = loaded
    log = row(tracks_list).history.log_path
    assert log.parent == geff_path.with_name("tracks.geff.history")
    assert not log.exists()  # created at the first edit

    UserDeleteNode(tracks, 4)
    UserDeleteEdge(tracks, (1, 2))
    tracks.undo()
    tracks.redo()
    tracks_list.close_history()

    lines = read_lines(log)
    assert [line["type"] for line in lines] == [
        "session_start",
        "action",
        "action",
        "undo",
        "redo",
        "session_end",
    ]
    start = lines[0]
    assert start["source"] == {"kind": "geff", "path": str(geff_path)}
    assert start["annotator"] == load_annotator()
    assert "napari-track-edit" in start["versions"]

    baseline = import_from_geff(geff_path)
    replay(baseline, log)
    assert compare_tracks(baseline, tracks) == []


def test_tracks_without_source_log_to_fallback(solution_tracks_2d, viewer):
    tracks_list = TracksList()
    tracks_list.add_tracks(solution_tracks_2d, "scratch")
    log = row(tracks_list).history.log_path
    assert log.parent == paths.fallback_dir()
    assert log.name.startswith("scratch_")

    UserDeleteNode(solution_tracks_2d, 4)
    tracks_list.close_history()
    assert read_lines(log)[0]["source"] == {"kind": "none", "path": None}


def test_unwritable_sidecar_falls_back_with_warning(geff_path, viewer, monkeypatch):
    from napari_track_edit.history import session

    monkeypatch.setattr(
        session, "is_writable", lambda d: d.name != "tracks.geff.history"
    )
    warnings = []
    monkeypatch.setattr(session, "show_warning", warnings.append)
    tracks_list = TracksList()
    tracks_list._add_loaded((import_from_geff(geff_path), "tracks", geff_path))
    assert row(tracks_list).history.log_path.parent == paths.fallback_dir()
    assert len(warnings) == 1
    assert "Cannot write the history log" in warnings[0]
    tracks_list.close_history()


def test_removing_tracks_ends_the_log(loaded):
    tracks_list, tracks = loaded
    log = row(tracks_list).history.log_path
    UserDeleteNode(tracks, 4)
    tracks_list.remove_tracks(tracks_list.tracks_list.item(0))
    assert types(log)[-1] == "session_end"


def test_viewer_close_ends_the_logs(viewer, solution_tracks_2d):
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.tracks_list.add_tracks(solution_tracks_2d, "t")
    log = row(tracks_viewer.tracks_list).history.log_path
    UserDeleteNode(solution_tracks_2d, 4)
    tracks_viewer.tracks_list.close_history()  # what the window teardown calls
    assert types(log)[-1] == "session_end"


# ---------------------------------------------------------------------------
# save rollover
# ---------------------------------------------------------------------------


def save(tracks_list: TracksList, directory: Path, name: str) -> Path:
    tracks_list.save_dir_line.setText(str(directory))
    tracks_list.save_name_line.setText(name)
    tracks_list.save_tracks(tracks_list.tracks_list.item(0))
    return directory / f"{name}.geff"


def test_save_starts_a_new_log_next_to_the_saved_geff(loaded, tmp_path):
    tracks_list, tracks = loaded
    old_log = row(tracks_list).history.log_path
    UserDeleteNode(tracks, 4)

    saved = save(tracks_list, tmp_path, "saved")
    new_log = row(tracks_list).history.log_path
    assert new_log.parent == saved.with_name("saved.geff.history")
    assert types(old_log)[-2:] == ["save", "session_end"]
    assert read_lines(old_log)[-2]["next_log"] == str(new_log)
    assert str(new_log) in tracks_list.history_label.text()

    UserDeleteEdge(tracks, (1, 2))
    tracks_list.close_history()
    start = read_lines(new_log)[0]
    assert start["previous_log"] == str(old_log)
    assert start["source"] == {"kind": "geff", "path": str(saved)}

    # The new log replays onto the saved geff
    baseline = import_from_geff(saved)
    replay(baseline, new_log)
    assert compare_tracks(baseline, tracks) == []


def test_save_without_edits_links_past_the_empty_session(loaded, tmp_path):
    tracks_list, tracks = loaded
    UserDeleteNode(tracks, 4)
    first_log = row(tracks_list).history.log_path

    save(tracks_list, tmp_path, "one")
    empty_log = row(tracks_list).history.log_path
    save(tracks_list, tmp_path, "two")  # no edits in between: no file
    assert not empty_log.exists()

    UserDeleteEdge(tracks, (1, 2))
    tracks_list.close_history()
    last_log = row(tracks_list).history.log_path
    assert read_lines(last_log)[0]["previous_log"] == str(first_log)


def test_database_tracks_keep_logging_next_to_the_database(graph_2d, tmp_path, viewer):
    from funtracks.data_model import Tracks

    db = tmp_path / "tracks.db"
    write_tracks_to_sql(Tracks(graph_2d, ndim=3, time_attr="t"), db)
    tracks = tracks_from_sql(db)
    tracks_list = TracksList()
    tracks_list._add_loaded((tracks, "tracks", db))
    log = row(tracks_list).history.log_path
    assert log.parent == tmp_path / "tracks.db.history"

    UserDeleteNode(tracks, 4)
    save(tracks_list, tmp_path, "snapshot")
    assert row(tracks_list).history.log_path == log
    UserDeleteEdge(tracks, (1, 2))
    tracks_list.close_history()

    lines = read_lines(log)
    assert [line["type"] for line in lines] == [
        "session_start",
        "action",
        "save",
        "action",
        "session_end",
    ]
    assert lines[0]["source"] == {"kind": "sql", "path": str(db)}


# ---------------------------------------------------------------------------
# annotator
# ---------------------------------------------------------------------------


def test_annotator_change_is_stored_and_logged(loaded):
    tracks_list, tracks = loaded
    log = row(tracks_list).history.log_path
    UserDeleteNode(tracks, 4)

    tracks_list.annotator_line.setText("pseudonym")
    tracks_list.annotator_line.editingFinished.emit()
    UserDeleteEdge(tracks, (1, 2))
    tracks_list.close_history()

    assert load_annotator() == "pseudonym"
    lines = read_lines(log)
    assert {"type": "annotator", "annotator": "pseudonym"}.items() <= lines[2].items()
    assert TracksList().annotator_line.text() == "pseudonym"


def test_annotator_before_first_edit_goes_into_the_header(loaded):
    tracks_list, tracks = loaded
    log = row(tracks_list).history.log_path
    tracks_list.annotator_line.setText("someone")
    tracks_list.annotator_line.editingFinished.emit()
    UserDeleteNode(tracks, 4)
    tracks_list.close_history()
    assert read_lines(log)[0]["annotator"] == "someone"


def test_empty_annotator_is_refused(loaded):
    tracks_list, _ = loaded
    before = load_annotator()
    tracks_list.annotator_line.setText("  ")
    tracks_list.annotator_line.editingFinished.emit()
    assert tracks_list.annotator_line.text() == before
    assert load_annotator() == before


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------


def group_names(widget) -> list[str]:
    return list(widget._row_names())


def test_group_create_and_delete_are_undoable(viewer, solution_tracks_2d, qtbot):
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.tracks_list.add_tracks(solution_tracks_2d, "t")
    log = row(tracks_viewer.tracks_list).history.log_path
    widget = tracks_viewer.get_collection_widget()
    tracks = tracks_viewer.tracks

    widget.group_name.setText("dividing")
    qtbot.mouseClick(widget.new_group_button, Qt.MouseButton.LeftButton)
    assert group_names(widget) == ["dividing"]
    widget._add_nodes([1, 2])

    item = widget.collection_list.item(0)
    qtbot.mouseClick(
        widget.collection_list.itemWidget(item).delete, Qt.MouseButton.LeftButton
    )
    assert group_names(widget) == []
    assert "dividing" not in tracks.features

    # Undoing the delete brings the group back with its members
    tracks.undo()
    assert group_names(widget) == ["dividing"]
    restored = widget.collection_list.itemWidget(widget.collection_list.item(0))
    assert restored.collection == {1, 2}

    tracks.redo()
    assert group_names(widget) == []

    tracks.undo()  # restore the group again
    tracks.undo()  # undo the membership change
    tracks.undo()  # undo the create
    assert group_names(widget) == []
    assert "dividing" not in tracks.features

    tracks_viewer.tracks_list.close_history()
    names = [line.get("name") for line in read_lines(log) if line["type"] == "action"]
    assert names == ["UserAddFeature", "UserUpdateNodesAttrs", "UserDeleteFeature"]


def test_loading_tracks_with_groups_writes_no_log_line(
    viewer, solution_tracks_2d, tmp_path
):
    from funtracks.user_actions import UserAddFeature

    UserAddFeature(
        solution_tracks_2d,
        "g",
        {
            "feature_type": "node",
            "value_type": "bool",
            "num_values": 1,
            "display_name": "g",
            "default_value": False,
        },
    )
    path = tmp_path / "with_group.geff"
    write_to_geff(solution_tracks_2d, path)

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.tracks_list._add_loaded((import_from_geff(path), "g", path))
    widget = tracks_viewer.get_collection_widget()
    assert group_names(widget) == ["g"]
    log = row(tracks_viewer.tracks_list).history.log_path
    tracks_viewer.tracks_list.close_history()
    assert not log.exists()


def test_unchanged_annotator_writes_no_line(loaded):
    tracks_list, tracks = loaded
    log = row(tracks_list).history.log_path
    UserDeleteNode(tracks, 4)
    tracks_list.annotator_line.editingFinished.emit()  # focus left, nothing typed
    tracks_list.close_history()
    assert "annotator" not in types(log)
