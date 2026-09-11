from pathlib import Path
from unittest.mock import MagicMock, patch

import napari
import numpy as np
import pytest
from funtracks.data_model import Tracks
from qtpy.QtWidgets import QLabel

from motile_tracker.import_export.menus.export_dialog import (
    SQL_EXPORT_TYPE,
    ExportDialog,
    ExportTypeDialog,
)
from motile_tracker.import_export.sql_io import (
    is_sql_backed,
    sql_database_path,
    tracks_from_sql,
    write_tracks_to_sql,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_parent(qtbot):
    from qtpy.QtWidgets import QWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    return parent


@pytest.fixture
def colormap():
    """A napari colormap mock that vectorizes like the real one: map() is called
    once with the whole track-id array and returns an (N, 4) RGBA array."""
    cmap = MagicMock(spec=napari.utils.Colormap)
    cmap.map.side_effect = lambda tids: np.tile(
        [0.0, 0.0, 0.0, 1.0], (len(np.atleast_1d(tids)), 1)
    )
    return cmap


@pytest.fixture
def accept_type_dialog(monkeypatch):
    """Patch ExportTypeDialog.exec_ to auto-accept, and return a handle to
    configure the dialog state *after* construction (via a callback).

    Usage::

        def configure(dialog):
            dialog.export_type_combo.setCurrentText("CSV")
            dialog.seg_checkbox.setChecked(True)

        accept_type_dialog(configure)
    """
    captured = {}

    def _accept(configure_fn=None):
        orig_init = ExportTypeDialog.__init__

        def patched_init(self, *args, **kwargs):
            orig_init(self, *args, **kwargs)
            if configure_fn is not None:
                configure_fn(self)
            captured["dialog"] = self

        monkeypatch.setattr(ExportTypeDialog, "__init__", patched_init)
        monkeypatch.setattr(
            ExportTypeDialog,
            "exec_",
            lambda self: 1,  # QDialog.Accepted
        )
        return captured

    return _accept


@pytest.fixture
def reject_type_dialog(monkeypatch):
    """Patch ExportTypeDialog.exec_ to auto-reject (cancel)."""

    def _reject():
        monkeypatch.setattr(
            ExportTypeDialog,
            "exec_",
            lambda self: 0,  # QDialog.Rejected
        )

    return _reject


@pytest.fixture
def mock_file_dialog():
    """Return a context-manager patch that makes QFileDialog return *path*."""

    def _make(*paths):
        if len(paths) == 1:
            fd = MagicMock()
            fd.exec_.return_value = True
            fd.selectedFiles.return_value = [str(paths[0])]
            return patch(
                "motile_tracker.import_export.menus.export_dialog.QFileDialog",
                return_value=fd,
            )
        else:
            fds = []
            for p in paths:
                fd = MagicMock()
                fd.exec_.return_value = True
                fd.selectedFiles.return_value = [str(p)]
                fds.append(fd)
            return patch(
                "motile_tracker.import_export.menus.export_dialog.QFileDialog",
                side_effect=fds,
            )

    return _make


# ---------------------------------------------------------------------------
# ExportTypeDialog unit tests (real widget, no mocks)
# ---------------------------------------------------------------------------


def test_checkbox_hidden_without_segmentation(qtbot):
    dialog = ExportTypeDialog(has_segmentation=False)
    qtbot.addWidget(dialog)
    assert not dialog.seg_checkbox.isVisibleTo(dialog)


def test_checkbox_visible_with_segmentation(qtbot):
    """Checkbox is visible for both GEFF and CSV when segmentation is present."""
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    assert dialog.seg_checkbox.isVisibleTo(dialog)
    assert dialog._geff_seg_label.isVisibleTo(dialog)
    dialog.export_type_combo.setCurrentText("CSV")
    assert dialog.seg_checkbox.isVisibleTo(dialog)
    assert not dialog._geff_seg_label.isVisibleTo(dialog)


def test_seg_options_hidden_by_default(qtbot):
    """Format combo and relabel checkbox are hidden until seg_checkbox is ticked."""
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    assert not dialog.seg_format_combo.isVisibleTo(dialog)
    assert not dialog.relabel_checkbox.isVisibleTo(dialog)


def test_seg_options_shown_when_seg_checked(qtbot):
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    dialog.seg_checkbox.setChecked(True)
    assert dialog.seg_format_combo.isVisibleTo(dialog)
    assert dialog.relabel_checkbox.isVisibleTo(dialog)


def test_relabel_checked_by_default(qtbot):
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    assert dialog.relabel_checkbox.isChecked()
    assert dialog.seg_label_attr == "tracklet"


def test_relabel_unchecked_gives_none_label_attr(qtbot):
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    dialog.relabel_checkbox.setChecked(False)
    assert dialog.seg_label_attr is None


def test_seg_format_defaults_to_zarr(qtbot):
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    assert dialog.seg_file_format == "zarr"


# ---------------------------------------------------------------------------
# ExportDialog integration tests
# Real ExportTypeDialog, real SolutionTracks, real export functions.
# Only QFileDialog (OS picker) is mocked.
# ---------------------------------------------------------------------------


def test_export_dialog_cancel(
    solution_tracks_2d_without_segmentation,
    fake_parent,
    colormap,
    reject_type_dialog,
):
    """Returns False when user cancels the type dialog."""
    reject_type_dialog()
    result = ExportDialog.show_export_dialog(
        fake_parent,
        solution_tracks_2d_without_segmentation,
        name="TestGroup",
        colormap=colormap,
    )
    assert result is False


def test_export_dialog_passes_has_segmentation(
    solution_tracks_2d,
    solution_tracks_2d_without_segmentation,
    fake_parent,
    colormap,
    monkeypatch,
):
    """ExportTypeDialog receives the correct has_segmentation flag."""
    captured_kwargs = []
    orig_init = ExportTypeDialog.__init__

    def spy_init(self, *args, **kwargs):
        captured_kwargs.append(kwargs)
        orig_init(self, *args, **kwargs)

    monkeypatch.setattr(ExportTypeDialog, "__init__", spy_init)
    monkeypatch.setattr(ExportTypeDialog, "exec_", lambda self: 0)

    ExportDialog.show_export_dialog(
        fake_parent,
        solution_tracks_2d_without_segmentation,
        name="x",
        colormap=colormap,
    )
    assert captured_kwargs[-1].get("has_segmentation") is False

    ExportDialog.show_export_dialog(
        fake_parent,
        solution_tracks_2d,
        name="x",
        colormap=colormap,
    )
    assert captured_kwargs[-1].get("has_segmentation") is True


def test_export_csv_no_seg(
    solution_tracks_2d_without_segmentation,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """CSV export without segmentation writes a real CSV file."""
    csv_file = tmp_path / "tracks.csv"

    def configure(dialog):
        dialog.export_type_combo.setCurrentText("CSV")

    accept_type_dialog(configure)

    with mock_file_dialog(csv_file):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d_without_segmentation,
            name="G",
            nodes_to_keep={1, 2, 3},
            colormap=colormap,
        )

    assert result is True
    assert csv_file.exists()
    content = csv_file.read_text()
    # ancestors of {1,2,3} include node 1 (parent of 2 and 3)
    assert "1" in content


def test_export_csv_with_seg_zarr(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """CSV export with segmentation as zarr writes both files."""
    csv_file = tmp_path / "tracks.csv"
    zarr_dir = tmp_path / "seg.zarr"

    def configure(dialog):
        dialog.export_type_combo.setCurrentText("CSV")
        dialog.seg_checkbox.setChecked(True)
        dialog.seg_format_combo.setCurrentText("zarr")

    accept_type_dialog(configure)

    with mock_file_dialog(csv_file, zarr_dir):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d,
            name="G",
            colormap=colormap,
        )

    assert result is True
    assert csv_file.exists()
    assert zarr_dir.exists()


def test_export_csv_with_seg_tiff_no_relabel(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """CSV export with segmentation as tiff, relabeling disabled."""
    csv_file = tmp_path / "tracks.csv"
    tif_file = tmp_path / "tracks.tif"

    def configure(dialog):
        dialog.export_type_combo.setCurrentText("CSV")
        dialog.seg_checkbox.setChecked(True)
        dialog.seg_format_combo.setCurrentText("tiff")
        dialog.relabel_checkbox.setChecked(False)

    accept_type_dialog(configure)

    with mock_file_dialog(csv_file, tif_file):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d,
            name="G",
            colormap=colormap,
        )

    assert result is True
    assert csv_file.exists()
    assert tif_file.exists()


def test_export_geff_no_seg(
    solution_tracks_2d_without_segmentation,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """GEFF export without segmentation writes a real zarr directory."""
    geff_dir = tmp_path / "tracks.zarr"

    accept_type_dialog()  # defaults: GEFF, no seg

    with mock_file_dialog(geff_dir):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d_without_segmentation,
            name="G",
            nodes_to_keep={1, 2},
            colormap=colormap,
        )

    assert result is True
    assert (geff_dir / "tracks.geff").exists()


def test_export_geff_with_seg_zarr(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """GEFF export with segmentation as zarr."""
    geff_dir = tmp_path / "tracks.zarr"

    def configure(dialog):
        dialog.seg_checkbox.setChecked(True)

    accept_type_dialog(configure)

    with mock_file_dialog(geff_dir):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d,
            name="G",
            colormap=colormap,
        )

    assert result is True
    assert (geff_dir / "tracks.geff").exists()
    assert (geff_dir / "segmentation").exists()


def test_export_geff_with_seg_tiff_no_relabel(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """GEFF export with segmentation as tiff, relabeling disabled."""
    geff_dir = tmp_path / "tracks.zarr"

    def configure(dialog):
        dialog.seg_checkbox.setChecked(True)
        dialog.seg_format_combo.setCurrentText("tiff")
        dialog.relabel_checkbox.setChecked(False)

    accept_type_dialog(configure)

    with mock_file_dialog(geff_dir):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d,
            name="G",
            colormap=colormap,
        )

    assert result is True
    assert (geff_dir / "tracks.geff").exists()


def test_export_geff_error(
    solution_tracks_2d_without_segmentation,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """Shows QMessageBox when export_to_geff raises ValueError."""
    geff_dir = tmp_path / "error.zarr"

    accept_type_dialog()

    with (
        mock_file_dialog(geff_dir),
        patch(
            "motile_tracker.import_export.menus.export_dialog.export_to_geff",
            side_effect=ValueError("Export failed"),
        ),
        patch(
            "motile_tracker.import_export.menus.export_dialog.QMessageBox.warning"
        ) as mock_warning,
    ):
        result = ExportDialog.show_export_dialog(
            fake_parent,
            solution_tracks_2d_without_segmentation,
            name="G",
            colormap=colormap,
        )

    assert result is False
    mock_warning.assert_called_once()


# ---------------------------------------------------------------------------
# SQL database export
# ---------------------------------------------------------------------------


def _select_sql(dialog):
    dialog.export_type_combo.setCurrentText(SQL_EXPORT_TYPE)


def _select_sql_and_rebind(dialog):
    # Switching over is the default, so selecting the format is all it takes.
    _select_sql(dialog)


def _select_sql_and_stay(dialog):
    _select_sql(dialog)
    dialog.keep_in_memory_checkbox.setChecked(True)


def test_sql_offered_by_default(qtbot):
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    assert dialog.export_type_combo.findText(SQL_EXPORT_TYPE) != -1


def test_sql_hidden_for_group_export(qtbot):
    """A group export writes a subset; a database is written whole."""
    dialog = ExportTypeDialog(has_segmentation=True, offer_sql=False)
    qtbot.addWidget(dialog)
    assert dialog.export_type_combo.findText(SQL_EXPORT_TYPE) == -1


def test_rebind_option_only_shown_for_sql(qtbot):
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    assert not dialog.keep_in_memory_checkbox.isVisibleTo(dialog)

    _select_sql(dialog)
    assert dialog.keep_in_memory_checkbox.isVisibleTo(dialog)
    assert dialog._rebind_label.isVisibleTo(dialog)


def test_in_memory_tracks_switch_over_by_default(qtbot):
    """Exporting from memory leaves you working in the new database."""
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    _select_sql(dialog)

    assert not dialog.keep_in_memory_checkbox.isChecked()
    assert dialog.rebind is True

    dialog.keep_in_memory_checkbox.setChecked(True)
    assert dialog.rebind is False


def test_database_backed_tracks_stay_put_by_default(qtbot):
    """Exporting a copy of a database must not move the session into the copy.

    The default never leaves you in memory, but for tracks already on disk that
    means staying where they are, not following the copy being handed over.
    """
    dialog = ExportTypeDialog(
        has_segmentation=True, already_on_disk=Path("/data/tracks.db")
    )
    qtbot.addWidget(dialog)
    _select_sql(dialog)

    assert dialog.keep_in_memory_checkbox.isChecked()
    assert dialog.rebind is False

    dialog.keep_in_memory_checkbox.setChecked(False)
    assert dialog.rebind is True


def test_sql_hides_segmentation_options(qtbot):
    """A database always holds the segmentation, as part of the graph."""
    dialog = ExportTypeDialog(has_segmentation=True)
    qtbot.addWidget(dialog)
    dialog.seg_checkbox.setChecked(True)

    _select_sql(dialog)

    assert not dialog.seg_checkbox.isVisibleTo(dialog)
    assert not dialog.save_segmentation


def test_export_to_sql_writes_a_readable_database(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    db_path = tmp_path / "tracks.db"
    accept_type_dialog(_select_sql_and_stay)

    with mock_file_dialog(db_path):
        result = ExportDialog.show_export_dialog(
            fake_parent, solution_tracks_2d, name="G", colormap=colormap
        )

    assert result is True
    assert db_path.exists()
    reopened = tracks_from_sql(db_path)
    assert reopened.graph_full.num_nodes() == (
        solution_tracks_2d.graph_full.num_nodes()
    )


def test_export_to_sql_without_rebind_leaves_session_in_memory(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    accept_type_dialog(_select_sql_and_stay)

    with mock_file_dialog(tmp_path / "tracks.db"):
        result = ExportDialog.show_export_dialog(
            fake_parent, solution_tracks_2d, name="G", colormap=colormap
        )

    assert result is True  # a plain export, nothing to swap in
    assert not is_sql_backed(solution_tracks_2d)


def test_export_to_sql_with_rebind_returns_database_backed_tracks(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    db_path = tmp_path / "tracks.db"
    accept_type_dialog(_select_sql_and_rebind)

    with mock_file_dialog(db_path):
        result = ExportDialog.show_export_dialog(
            fake_parent, solution_tracks_2d, name="G", colormap=colormap
        )

    assert isinstance(result, Tracks)
    assert is_sql_backed(result)
    assert sql_database_path(result) == db_path
    # The object handed in is left alone.
    assert not is_sql_backed(solution_tracks_2d)


def test_export_to_sql_overwrites_existing_file(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """The save dialog already confirmed; clearing the path first is what keeps
    tracksdata's SQL-level copy eligible."""
    db_path = tmp_path / "tracks.db"
    db_path.write_bytes(b"not a database")
    accept_type_dialog(_select_sql_and_stay)

    with mock_file_dialog(db_path):
        result = ExportDialog.show_export_dialog(
            fake_parent, solution_tracks_2d, name="G", colormap=colormap
        )

    assert result is True
    assert tracks_from_sql(db_path).graph_full.num_nodes() > 0


def test_export_to_sql_refuses_own_database(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """Exporting a database over itself would destroy it before reading it."""
    db_path = tmp_path / "tracks.db"
    write_tracks_to_sql(solution_tracks_2d, db_path)
    opened = tracks_from_sql(db_path)

    accept_type_dialog(_select_sql)
    with (
        mock_file_dialog(db_path),
        patch(
            "motile_tracker.import_export.menus.export_dialog.QMessageBox.warning"
        ) as mock_warning,
    ):
        result = ExportDialog.show_export_dialog(
            fake_parent, opened, name="G", colormap=colormap
        )

    assert result is False
    mock_warning.assert_called_once()
    assert tracks_from_sql(db_path).graph_full.num_nodes() > 0


def test_export_to_sql_cancel_writes_nothing(
    solution_tracks_2d, fake_parent, tmp_path, colormap, accept_type_dialog
):
    db_path = tmp_path / "tracks.db"
    accept_type_dialog(_select_sql)

    fd = MagicMock()
    fd.exec_.return_value = False
    with patch(
        "motile_tracker.import_export.menus.export_dialog.QFileDialog",
        return_value=fd,
    ):
        result = ExportDialog.show_export_dialog(
            fake_parent, solution_tracks_2d, name="G", colormap=colormap
        )

    assert result is False
    assert not db_path.exists()


def test_already_on_disk_note_shown_for_database_backed_tracks(
    solution_tracks_2d,
    fake_parent,
    tmp_path,
    colormap,
    accept_type_dialog,
    mock_file_dialog,
):
    """Tracks that live in a database are told so, since for them exporting is
    about sharing rather than about not losing work."""
    db_path = tmp_path / "tracks.db"
    write_tracks_to_sql(solution_tracks_2d, db_path)
    opened = tracks_from_sql(db_path)

    captured = accept_type_dialog(_select_sql)
    with mock_file_dialog(tmp_path / "copy.db"):
        ExportDialog.show_export_dialog(
            fake_parent, opened, name="G", colormap=colormap
        )

    labels = captured["dialog"].findChildren(QLabel)
    assert any(str(db_path) in label.text() for label in labels)
