"""Tests for TracksList and TracksButton.

Covers add/remove/select tracks, save/load/export dialogs, signal emission,
and the load_motile_run bug fix (must call MotileRun.load, not Tracks.load).
"""

import warnings
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from funtracks.data_model import SolutionTracks, Tracks
from funtracks.import_export import write_to_geff
from qtpy.QtWidgets import QDialog
from tracksdata.nodes import Mask

from motile_tracker.data_views.views_coordinator.tracks_list import (
    TracksButton,
    TracksList,
    default_save_dir,
)
from motile_tracker.motile.backend.motile_run import MotileRun, SolverParams


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    yield
    viewer.layers.clear()


@pytest.fixture
def motile_run(graph_2d):
    return MotileRun(graph=graph_2d, run_name="test", solver_params=SolverParams())


@pytest.fixture
def tracks_list():
    return TracksList()


# ---------------------------------------------------------------------------
# TracksButton
# ---------------------------------------------------------------------------


class TestTracksButton:
    def test_init_stores_tracks_and_name(self, motile_run):
        btn = TracksButton(motile_run, "my_run")
        assert btn.tracks is motile_run
        assert btn.name.text() == "my_run"

    def test_size_hint_height(self, motile_run):
        btn = TracksButton(motile_run, "my_run")
        assert btn.sizeHint().height() == 30


# ---------------------------------------------------------------------------
# TracksList — add / remove / select
# ---------------------------------------------------------------------------


class TestTracksListAddRemove:
    def test_add_tracks_appends_item(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=False)
        assert tracks_list.tracks_list.count() == 1

    def test_add_tracks_with_select(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=True)
        assert tracks_list.tracks_list.currentRow() == 0

    def test_add_multiple_tracks(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=False)
        tracks_list.add_tracks(motile_run, "run2", select=False)
        assert tracks_list.tracks_list.count() == 2

    def test_remove_tracks(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=False)
        item = tracks_list.tracks_list.item(0)
        tracks_list.remove_tracks(item)
        assert tracks_list.tracks_list.count() == 0

    def test_selection_changed_emits_signal(self, tracks_list, motile_run):
        emitted = []
        tracks_list.view_tracks.connect(lambda t, n: emitted.append((t, n)))
        tracks_list.add_tracks(motile_run, "run1", select=True)
        # Selecting the row triggers _selection_changed
        assert len(emitted) == 1
        assert emitted[0][1] == "run1"

    def test_add_solution_tracks_not_wrapped(self, tracks_list, solution_tracks_2d):
        """SolutionTracks added to the list should NOT be wrapped in MotileRun."""
        tracks_list.add_tracks(solution_tracks_2d, "imported", select=False)
        item = tracks_list.tracks_list.item(0)
        widget = tracks_list.tracks_list.itemWidget(item)
        assert isinstance(widget.tracks, SolutionTracks)
        assert not isinstance(widget.tracks, MotileRun)

    def test_view_tracks_emits_solution_tracks_for_plain_tracks(
        self, tracks_list, graph_2d
    ):
        """The list stores plain Tracks, but view_tracks must emit a
        SolutionTracks because the views and actions still need track IDs.
        """
        # the fixture graph stores track ids in "track_id", so that has to be
        # declared: tracklet_attr is how a caller names an existing column
        plain_tracks = Tracks(graph_2d, ndim=3, time_attr="t", tracklet_attr="track_id")

        emitted = []
        tracks_list.view_tracks.connect(lambda t, n: emitted.append((t, n)))
        tracks_list.add_tracks(plain_tracks, "plain", select=True)

        # stored as-is, not converted on the way in
        item = tracks_list.tracks_list.item(0)
        assert tracks_list.tracks_list.itemWidget(item).tracks is plain_tracks

        assert len(emitted) == 1
        converted = emitted[0][0]
        assert isinstance(converted, SolutionTracks)
        # the conversion must carry over the attributes the views rely on
        # rather than re-deriving them
        assert converted.scale == plain_tracks.scale
        assert converted.ndim == plain_tracks.ndim
        assert (converted.segmentation is None) == (plain_tracks.segmentation is None)
        # the point of converting: the views need track ids to actually be on
        # the graph, not merely named by the FeatureDict
        assert converted.features.tracklet_key in converted.graph.node_attr_keys()
        assert converted.features.lineage_key in converted.graph.node_attr_keys()

    def test_view_tracks_computes_missing_track_ids(self, tracks_list, graph_2d):
        """Tracks with no track id column at all must come out of the
        conversion with one computed, not merely declared.

        Tracks imported from a geff that never had track ids land here. On
        funtracks < 2.1, passing a FeatureDict to Tracks.__init__ activates the
        declared features without computing the missing ones, so the conversion
        has to enable them itself. From 2.1 the constructor already computes
        them, so this only checks that the outcome is the same either way.
        """
        graph_2d.remove_node_attr_key("track_id")
        graph_2d.remove_node_attr_key("lineage_id")
        plain_tracks = Tracks(graph_2d, ndim=3, time_attr="t")

        emitted = []
        tracks_list.view_tracks.connect(lambda t, n: emitted.append((t, n)))
        tracks_list.add_tracks(plain_tracks, "plain", select=True)

        converted = emitted[0][0]
        assert converted.features.tracklet_key in converted.graph.node_attr_keys()
        assert converted.features.lineage_key in converted.graph.node_attr_keys()

    def test_view_tracks_segmentation_follows_edits(self, tracks_list, graph_2d):
        """The emitted tracks must own their segmentation, not borrow the old one.

        A GraphArrayView renders from, and listens to, the single graph object
        it was built with. Handing the original view to the converted tracks
        left it bound to the graph of the tracks in the list, so an edit made
        through the converted tracks (painting a label) never invalidated its
        cache: the pixels snapped back while the centroid moved.
        """
        plain_tracks = Tracks(graph_2d, ndim=3, time_attr="t", tracklet_attr="track_id")
        assert plain_tracks.segmentation is not None

        emitted = []
        tracks_list.view_tracks.connect(lambda t, n: emitted.append((t, n)))
        tracks_list.add_tracks(plain_tracks, "plain", select=True)
        converted = emitted[0][0]

        assert converted.segmentation.graph is converted.graph_solution

        node = 1
        time = converted.get_time(node)
        assert (np.asarray(converted.segmentation[time]) == node).any()

        old_mask = converted.get_mask(node)
        converted.update_mask(
            node, Mask(np.zeros_like(old_mask.mask), bbox=old_mask.bbox)
        )

        assert not (np.asarray(converted.segmentation[time]) == node).any()

    def test_view_tracks_passes_through_motile_run(self, tracks_list, motile_run):
        """A MotileRun is already a SolutionTracks, so it must be emitted
        unchanged rather than rebuilt (which would drop its solver params).
        """
        emitted = []
        tracks_list.view_tracks.connect(lambda t, n: emitted.append((t, n)))
        tracks_list.add_tracks(motile_run, "run1", select=True)

        assert len(emitted) == 1
        assert emitted[0][0] is motile_run


# ---------------------------------------------------------------------------
# TracksList — save path fields
# ---------------------------------------------------------------------------


class TestTracksListSavePathFields:
    def test_save_dir_defaults_to_appdirs(self, tracks_list):
        """The save directory starts where the sample data lives, not in the
        user's home directory."""
        assert tracks_list.save_dir_line.text() == str(default_save_dir())

    def test_save_name_empty_before_any_selection(self, tracks_list):
        assert tracks_list.save_name_line.text() == ""

    def test_selecting_tracks_fills_save_name(self, tracks_list, motile_run):
        """The field holds the bare name; .geff is a fixed label in the UI."""
        tracks_list.add_tracks(motile_run, "run1", select=True)
        assert tracks_list.save_name_line.text() == "run1"

    def test_save_name_follows_selection(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.add_tracks(motile_run, "run2", select=True)
        assert tracks_list.save_name_line.text() == "run2"

    def test_save_name_strips_geff_suffix_from_tracks_name(
        self, tracks_list, motile_run
    ):
        """Tracks loaded from a geff are named after the store, so the suffix
        must not be doubled up."""
        tracks_list.add_tracks(motile_run, "loaded.geff", select=True)
        assert tracks_list.save_name_line.text() == "loaded"
        assert tracks_list.save_path().name == "loaded.geff"

    def test_user_edit_stops_autofill(self, tracks_list, motile_run):
        """Once the user types their own name, selecting another row must not
        overwrite it."""
        tracks_list.add_tracks(motile_run, "run1", select=True)

        # textEdited only fires on real user input, so simulate it directly
        tracks_list.save_name_line.setText("my_own_name")
        tracks_list.save_name_line.textEdited.emit("my_own_name")

        tracks_list.add_tracks(motile_run, "run2", select=True)

        assert tracks_list.save_name_line.text() == "my_own_name"

    def test_save_path_combines_dir_and_name(self, tracks_list, motile_run, tmp_path):
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))

        assert tracks_list.save_path() == tmp_path / "run1.geff"

    def test_save_path_none_when_name_blank(self, tracks_list, tmp_path):
        tracks_list.save_dir_line.setText(str(tmp_path))
        tracks_list.save_name_line.setText("")

        assert tracks_list.save_path() is None

    def test_save_path_none_when_dir_blank(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.save_dir_line.setText("   ")

        assert tracks_list.save_path() is None

    def test_save_path_tolerates_typed_suffix(self, tracks_list, tmp_path):
        """A user who types the suffix anyway should not get 'x.geff.geff'."""
        tracks_list.save_dir_line.setText(str(tmp_path))
        tracks_list.save_name_line.setText("mine.geff")

        assert tracks_list.save_path() == tmp_path / "mine.geff"

    def test_programmatic_fill_does_not_count_as_user_edit(
        self, tracks_list, motile_run
    ):
        """Auto-filling the field must not mark it as user-edited, or the
        first selection would freeze the name forever."""
        tracks_list.add_tracks(motile_run, "run1", select=True)
        assert tracks_list._save_name_edited is False

    def test_browse_sets_save_dir(self, tracks_list, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_list."
            "QFileDialog.getExistingDirectory",
            lambda *a, **k: str(tmp_path),
        )
        tracks_list._browse_save_dir()
        assert tracks_list.save_dir_line.text() == str(tmp_path)

    def test_browse_cancelled_leaves_save_dir(self, tracks_list, monkeypatch):
        before = tracks_list.save_dir_line.text()
        monkeypatch.setattr(
            "motile_tracker.data_views.views_coordinator.tracks_list."
            "QFileDialog.getExistingDirectory",
            lambda *a, **k: "",
        )
        tracks_list._browse_save_dir()
        assert tracks_list.save_dir_line.text() == before


# ---------------------------------------------------------------------------
# TracksList — save
# ---------------------------------------------------------------------------


class TestTracksListSave:
    def test_save_motile_run_writes_geff_at_save_path(
        self, tracks_list, motile_run, tmp_path
    ):
        """The run is written at exactly the path shown in the save fields,
        with no intervening subdirectory."""
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        item = tracks_list.tracks_list.item(0)

        tracks_list.save_tracks(item)

        save_path = tmp_path / "run1.geff"
        assert (save_path / "nodes").exists()
        assert list(tmp_path.iterdir()) == [save_path]

    def test_save_emits_tracks_saved_signal(self, tracks_list, motile_run, tmp_path):
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        item = tracks_list.tracks_list.item(0)

        emitted = []
        tracks_list.tracks_saved.connect(lambda t, p: emitted.append((t, p)))

        tracks_list.save_tracks(item)

        assert len(emitted) == 1
        assert emitted[0][0] is motile_run
        assert emitted[0][1] == tmp_path / "run1.geff"

    def test_save_motile_run_emits_geff_path_with_params_inside(
        self, tracks_list, motile_run, tmp_path
    ):
        """tracks_saved names the geff store, and the solver params live
        inside it rather than beside it.
        """
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        item = tracks_list.tracks_list.item(0)

        emitted = []
        tracks_list.tracks_saved.connect(lambda t, p: emitted.append((t, p)))

        tracks_list.save_tracks(item)

        path = emitted[0][1]
        assert path.exists()
        assert (path / "solver_params.json").exists()

    def test_save_does_nothing_without_a_filename(
        self, tracks_list, motile_run, tmp_path
    ):
        """With no name there is nowhere to save, so warn rather than raise."""
        tracks_list.add_tracks(motile_run, "run1", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        tracks_list.save_name_line.setText("")
        item = tracks_list.tracks_list.item(0)

        emitted = []
        tracks_list.tracks_saved.connect(lambda t, p: emitted.append((t, p)))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tracks_list.save_tracks(item)

        assert len(caught) == 1
        assert list(tmp_path.iterdir()) == []
        assert len(emitted) == 0

    def test_save_creates_missing_save_directory(
        self, tracks_list, motile_run, tmp_path
    ):
        """The default save directory may not exist yet on a fresh install."""
        tracks_list.add_tracks(motile_run, "run1", select=True)
        missing = tmp_path / "does" / "not" / "exist"
        tracks_list.save_dir_line.setText(str(missing))
        item = tracks_list.tracks_list.item(0)

        tracks_list.save_tracks(item)

        assert (missing / "run1.geff").exists()


# ---------------------------------------------------------------------------
# TracksList — save SolutionTracks directly (not wrapped in MotileRun)
# ---------------------------------------------------------------------------


class TestTracksListSaveSolutionTracks:
    def test_solution_tracks_saved_directly_to_path(
        self, tracks_list, solution_tracks_2d, tmp_path
    ):
        """SolutionTracks are written with write_to_geff at the save path,
        not wrapped in a MotileRun."""
        tracks_list.add_tracks(solution_tracks_2d, "imported", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        item = tracks_list.tracks_list.item(0)

        tracks_list.save_tracks(item)

        assert (tmp_path / "imported.geff").exists()

    def test_solution_tracks_save_emits_signal(
        self, tracks_list, solution_tracks_2d, tmp_path
    ):
        tracks_list.add_tracks(solution_tracks_2d, "imported", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        item = tracks_list.tracks_list.item(0)

        emitted = []
        tracks_list.tracks_saved.connect(lambda t, p: emitted.append((t, p)))

        tracks_list.save_tracks(item)

        assert len(emitted) == 1
        assert emitted[0][0] is solution_tracks_2d
        assert emitted[0][1] == tmp_path / "imported.geff"

    def test_save_respects_edited_name(self, tracks_list, solution_tracks_2d, tmp_path):
        """A name the user typed is where the tracks go."""
        tracks_list.add_tracks(solution_tracks_2d, "imported", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        tracks_list.save_name_line.setText("chosen_by_me")
        tracks_list.save_name_line.textEdited.emit("chosen_by_me")
        item = tracks_list.tracks_list.item(0)

        tracks_list.save_tracks(item)

        assert (tmp_path / "chosen_by_me.geff").exists()
        assert not (tmp_path / "imported.geff").exists()


# ---------------------------------------------------------------------------
# TracksList — overwrite confirmation
# ---------------------------------------------------------------------------


class TestTracksListOverwrite:
    """Saving no longer goes through a file dialog, so this confirmation is the
    only thing guarding an existing store."""

    def _setup(self, tracks_list, tracks, tmp_path):
        tracks_list.add_tracks(tracks, "imported", select=True)
        tracks_list.save_dir_line.setText(str(tmp_path))
        return tracks_list.tracks_list.item(0)

    def test_no_confirmation_when_path_is_free(
        self, tracks_list, solution_tracks_2d, tmp_path, monkeypatch
    ):
        item = self._setup(tracks_list, solution_tracks_2d, tmp_path)
        asked = []
        monkeypatch.setattr(
            tracks_list, "_confirm_overwrite", lambda p: asked.append(p) or True
        )

        tracks_list.save_tracks(item)

        assert asked == []

    def test_overwrite_confirmed_writes(
        self, tracks_list, solution_tracks_2d, tmp_path, monkeypatch
    ):
        item = self._setup(tracks_list, solution_tracks_2d, tmp_path)
        monkeypatch.setattr(tracks_list, "_confirm_overwrite", lambda p: True)

        tracks_list.save_tracks(item)
        tracks_list.save_tracks(item)

        assert (tmp_path / "imported.geff").exists()

    def test_overwrite_declined_does_not_write_or_emit(
        self, tracks_list, solution_tracks_2d, tmp_path, monkeypatch
    ):
        item = self._setup(tracks_list, solution_tracks_2d, tmp_path)
        tracks_list.save_tracks(item)

        monkeypatch.setattr(tracks_list, "_confirm_overwrite", lambda p: False)
        emitted = []
        tracks_list.tracks_saved.connect(lambda t, p: emitted.append((t, p)))
        marker = tmp_path / "imported.geff" / "untouched.txt"
        marker.write_text("still here")

        tracks_list.save_tracks(item)

        assert marker.read_text() == "still here"
        assert len(emitted) == 0


# ---------------------------------------------------------------------------
# TracksList — load_motile_run (bug fix: must use MotileRun.load)
# ---------------------------------------------------------------------------


class TestTracksListLoadMotileRun:
    def test_load_motile_run_success(self, tracks_list, motile_run, tmp_path):
        save_dir = motile_run.save(tmp_path / "run1.geff")

        tracks_list.file_dialog.exec_ = MagicMock(return_value=True)
        tracks_list.file_dialog.selectedFiles = MagicMock(return_value=[str(save_dir)])

        tracks, name, path = tracks_list.load_motile_run()

        assert isinstance(tracks, MotileRun)
        assert name == save_dir.stem
        # the run dir is itself the geff store, so loading and saving name the
        # same thing
        assert path == save_dir

    def test_load_motile_run_adds_to_list_via_load_tracks(
        self, tracks_list, motile_run, tmp_path
    ):
        save_dir = motile_run.save(tmp_path)

        tracks_list.dropdown_menu.setCurrentText("Motile Run")
        tracks_list.file_dialog.exec_ = MagicMock(return_value=True)
        tracks_list.file_dialog.selectedFiles = MagicMock(return_value=[str(save_dir)])

        tracks_list.load_tracks()

        assert tracks_list.tracks_list.count() == 1

    def test_load_motile_run_bad_path_warns(self, tracks_list, tmp_path):
        bad_path = tmp_path / "nonexistent_run"
        tracks_list.file_dialog.exec_ = MagicMock(return_value=True)
        tracks_list.file_dialog.selectedFiles = MagicMock(return_value=[str(bad_path)])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = tracks_list.load_motile_run()

        assert len(caught) == 1
        assert result is None

    def test_load_motile_run_dialog_cancelled(self, tracks_list):
        tracks_list.file_dialog.exec_ = MagicMock(return_value=False)
        assert tracks_list.load_motile_run() is None


# ---------------------------------------------------------------------------
# TracksList — load_internal_tracks
# ---------------------------------------------------------------------------


class TestTracksListLoadGeff:
    def test_load_internal_tracks_success(
        self, tracks_list, solution_tracks_2d, tmp_path
    ):
        geff_path = tmp_path / "saved_tracks.geff"
        write_to_geff(solution_tracks_2d, geff_path)

        tracks_list.dropdown_menu.setCurrentText("Tracks (geff)")
        tracks_list.file_dialog.exec_ = MagicMock(return_value=True)
        tracks_list.file_dialog.selectedFiles = MagicMock(return_value=[str(geff_path)])

        tracks_list.load_tracks()

        assert tracks_list.tracks_list.count() == 1
        item = tracks_list.tracks_list.item(0)
        widget = tracks_list.tracks_list.itemWidget(item)
        assert widget.name.text() == "saved_tracks"

    def test_load_internal_tracks_emits_signal(
        self, tracks_list, solution_tracks_2d, tmp_path
    ):
        geff_path = tmp_path / "saved_tracks.geff"
        write_to_geff(solution_tracks_2d, geff_path)

        tracks_list.dropdown_menu.setCurrentText("Tracks (geff)")
        tracks_list.file_dialog.exec_ = MagicMock(return_value=True)
        tracks_list.file_dialog.selectedFiles = MagicMock(return_value=[str(geff_path)])

        emitted = []
        tracks_list.tracks_loaded.connect(lambda t, p: emitted.append((t, p)))

        tracks_list.load_tracks()

        assert len(emitted) == 1
        # tracks_loaded hands out the stored object as-is, which is a plain
        # Tracks. Only view_tracks converts to SolutionTracks.
        assert isinstance(emitted[0][0], Tracks)
        assert emitted[0][1] == geff_path

    def test_load_internal_tracks_bad_path_warns(self, tracks_list, tmp_path):
        bad_path = tmp_path / "nonexistent.geff"
        tracks_list.file_dialog.exec_ = MagicMock(return_value=True)
        tracks_list.file_dialog.selectedFiles = MagicMock(return_value=[str(bad_path)])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = tracks_list.load_internal_tracks()

        assert len(caught) == 1
        assert result is None

    def test_load_internal_tracks_dialog_cancelled(self, tracks_list):
        tracks_list.file_dialog.exec_ = MagicMock(return_value=False)
        assert tracks_list.load_internal_tracks() is None
        assert tracks_list.tracks_list.count() == 0


# ---------------------------------------------------------------------------
# TracksList — load_tracks dispatch
# ---------------------------------------------------------------------------


class TestTracksListLoadDispatch:
    def test_load_tracks_dispatches_geff_tracks(self, tracks_list):
        tracks_list.dropdown_menu.setCurrentText("Tracks (geff)")
        with patch.object(
            tracks_list, "load_internal_tracks", return_value=None
        ) as mock:
            tracks_list.load_tracks()
            mock.assert_called_once()

    def test_load_tracks_dispatches_motile_run(self, tracks_list):
        tracks_list.dropdown_menu.setCurrentText("Motile Run")
        with patch.object(tracks_list, "load_motile_run", return_value=None) as mock:
            tracks_list.load_tracks()
            mock.assert_called_once()

    def test_load_tracks_dispatches_csv(self, tracks_list):
        tracks_list.dropdown_menu.setCurrentText("External tracks from CSV")
        with patch.object(tracks_list, "_load_tracks", return_value=None) as mock:
            tracks_list.load_tracks()
            mock.assert_called_once_with(import_type="csv")

    def test_load_tracks_dispatches_geff(self, tracks_list):
        tracks_list.dropdown_menu.setCurrentText("External tracks from geff")
        with patch.object(tracks_list, "_load_tracks", return_value=None) as mock:
            tracks_list.load_tracks()
            mock.assert_called_once_with("geff")


# ---------------------------------------------------------------------------
# TracksList — _load_tracks (CSV / GEFF via ImportDialog)
# ---------------------------------------------------------------------------


class TestTracksListLoadExternal:
    def test_load_tracks_accepted_adds_tracks(self, tracks_list, motile_run, tmp_path):
        mock_dialog = MagicMock()
        mock_dialog.exec_.return_value = QDialog.Accepted
        mock_dialog.tracks = motile_run
        mock_dialog.name = "imported"
        mock_dialog.source_path = tmp_path / "test.csv"

        tracks_list.dropdown_menu.setCurrentText("External tracks from CSV")
        with patch(
            "motile_tracker.data_views.views_coordinator.tracks_list.ImportDialog",
            return_value=mock_dialog,
        ):
            tracks_list.load_tracks()

        assert tracks_list.tracks_list.count() == 1

    def test_load_tracks_rejected_adds_nothing(self, tracks_list):
        mock_dialog = MagicMock()
        mock_dialog.exec_.return_value = QDialog.Rejected

        with patch(
            "motile_tracker.data_views.views_coordinator.tracks_list.ImportDialog",
            return_value=mock_dialog,
        ):
            assert tracks_list._load_tracks("csv") is None

        assert tracks_list.tracks_list.count() == 0

    def test_load_tracks_accepted_but_none_tracks(self, tracks_list):
        mock_dialog = MagicMock()
        mock_dialog.exec_.return_value = QDialog.Accepted
        mock_dialog.tracks = None

        with patch(
            "motile_tracker.data_views.views_coordinator.tracks_list.ImportDialog",
            return_value=mock_dialog,
        ):
            assert tracks_list._load_tracks("csv") is None

        assert tracks_list.tracks_list.count() == 0


# ---------------------------------------------------------------------------
# TracksList — show_export_dialog
# ---------------------------------------------------------------------------


class TestTracksListExport:
    def test_show_export_dialog_called(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=False)
        item = tracks_list.tracks_list.item(0)

        with patch(
            "motile_tracker.data_views.views_coordinator.tracks_list.ExportDialog.show_export_dialog"
        ) as mock_export:
            tracks_list.show_export_dialog(item)
            mock_export.assert_called_once()

    def test_show_export_dialog_emits_request_colormap(self, tracks_list, motile_run):
        tracks_list.add_tracks(motile_run, "run1", select=False)
        item = tracks_list.tracks_list.item(0)

        emitted = []
        tracks_list.request_colormap.connect(lambda: emitted.append(True))

        with patch(
            "motile_tracker.data_views.views_coordinator.tracks_list.ExportDialog.show_export_dialog"
        ):
            tracks_list.show_export_dialog(item)

        assert len(emitted) == 1
