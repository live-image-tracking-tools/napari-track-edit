"""Round-tripping tracks through an on-disk SQL database.

No Qt here: sql_io deliberately holds no widgets, so the format itself can be
tested without a running application.
"""

from pathlib import Path

import numpy as np
import pytest
import tracksdata as td
from funtracks.data_model import Tracks
from funtracks.user_actions import UserDeleteNodes

from motile_tracker.import_export import sql_io
from motile_tracker.import_export.sql_io import (
    META_KEY,
    close_database,
    is_same_database,
    is_sql_backed,
    rebind_tracks_to_graph,
    sql_database_path,
    tracks_from_sql,
    write_tracks_to_sql,
)
from motile_tracker.motile.backend.motile_run import MotileRun
from motile_tracker.motile.backend.solver_params import SolverParams


@pytest.fixture
def tracks_2d(graph_2d) -> Tracks:
    """2D+time tracks with a segmentation and a non-trivial scale."""
    return Tracks(graph_2d, ndim=3, time_attr="t", scale=[1.0, 0.5, 0.25])


class TestRoundTrip:
    def test_graph_survives(self, tracks_2d, tmp_path):
        """Nodes, edges and node ids all come back."""
        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        reopened = tracks_from_sql(tmp_path / "tracks.db")

        assert isinstance(reopened.graph_full, td.graph.SQLGraph)
        assert reopened.graph_full.num_nodes() == tracks_2d.graph_full.num_nodes()
        assert reopened.graph_full.num_edges() == tracks_2d.graph_full.num_edges()
        # Node ids must be preserved, not just the count: the segmentation is
        # rendered by looking node ids up as label values.
        assert sorted(reopened.graph_full.node_ids()) == sorted(
            tracks_2d.graph_full.node_ids()
        )

    def test_description_survives(self, tracks_2d, tmp_path):
        """Scale, ndim and the feature keys are not in the graph, so they are
        recorded separately and must come back."""
        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        reopened = tracks_from_sql(tmp_path / "tracks.db")

        assert reopened.scale == tracks_2d.scale
        assert reopened.ndim == tracks_2d.ndim
        assert reopened.features.time_key == tracks_2d.features.time_key
        assert reopened.features.position_key == tracks_2d.features.position_key
        assert reopened.features.tracklet_key == tracks_2d.features.tracklet_key
        assert reopened.features.lineage_key == tracks_2d.features.lineage_key

    def test_segmentation_survives(self, tracks_2d, tmp_path):
        """The segmentation is rebuilt from the masks and the shape metadata,
        with no side file."""
        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        reopened = tracks_from_sql(tmp_path / "tracks.db")

        assert reopened.segmentation is not None
        np.testing.assert_array_equal(
            np.asarray(reopened.segmentation), np.asarray(tracks_2d.segmentation)
        )

    def test_3d_round_trip(self, graph_3d, tmp_path):
        tracks = Tracks(graph_3d, ndim=4, time_attr="t", scale=[1.0, 2.0, 0.5, 0.5])
        write_tracks_to_sql(tracks, tmp_path / "tracks.db")
        reopened = tracks_from_sql(tmp_path / "tracks.db")

        assert reopened.ndim == 4
        assert reopened.scale == [1.0, 2.0, 0.5, 0.5]
        np.testing.assert_array_equal(
            np.asarray(reopened.segmentation), np.asarray(tracks.segmentation)
        )

    def test_candidates_survive(self, tracks_2d, tmp_path):
        """Soft-deleted nodes are kept as candidates, unlike in a geff round trip.

        This is why the database is written from graph_full. It does not make the
        delete undoable after reopening - the action history is not part of the
        graph - but it does mean the node is still there to be reconnected, and
        that the solver's candidate set is intact.
        """
        victim = sorted(tracks_2d.graph_solution.node_ids())[-1]
        UserDeleteNodes(tracks_2d, [victim])
        assert tracks_2d.graph_full.num_nodes() > tracks_2d.graph_solution.num_nodes()

        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        reopened = tracks_from_sql(tmp_path / "tracks.db")

        assert reopened.graph_full.num_nodes() == tracks_2d.graph_full.num_nodes()
        assert reopened.graph_solution.num_nodes() == (
            tracks_2d.graph_solution.num_nodes()
        )
        assert victim in reopened.graph_full.node_ids()
        assert victim not in reopened.graph_solution.node_ids()

    def test_sql_to_sql(self, tracks_2d, tmp_path):
        """Exporting a database-backed tracks to another database.

        Takes tracksdata's SQL-level copy rather than going through Python,
        which is the path that matters for a graph too big to materialise.
        """
        write_tracks_to_sql(tracks_2d, tmp_path / "first.db")
        first = tracks_from_sql(tmp_path / "first.db")

        write_tracks_to_sql(first, tmp_path / "second.db")
        second = tracks_from_sql(tmp_path / "second.db")

        assert second.graph_full.num_nodes() == tracks_2d.graph_full.num_nodes()
        assert second.scale == tracks_2d.scale
        np.testing.assert_array_equal(
            np.asarray(second.segmentation), np.asarray(tracks_2d.segmentation)
        )


class TestLiveEditing:
    def test_edit_reaches_disk(self, tracks_2d, tmp_path):
        """An edit to database-backed tracks is on disk without any save."""
        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        opened = tracks_from_sql(tmp_path / "tracks.db")
        victim = sorted(opened.graph_solution.node_ids())[-1]

        UserDeleteNodes(opened, [victim])

        # Nothing was saved; open the same file again from scratch.
        reopened = tracks_from_sql(tmp_path / "tracks.db")
        assert victim not in reopened.graph_solution.node_ids()

    def test_segmentation_stays_fresh(self, tracks_2d, tmp_path):
        """Editing a database-backed graph updates the rendered segmentation.

        Guards the tracksdata root-to-view propagation this feature depends on:
        the segmentation reads from graph_solution, which for a SQL root is a
        separate copy, so without propagation it would silently render stale.
        """
        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        opened = tracks_from_sql(tmp_path / "tracks.db")
        before = np.asarray(opened.segmentation).copy()

        victim = sorted(opened.graph_solution.node_ids())[-1]
        UserDeleteNodes(opened, [victim])

        after = np.asarray(opened.segmentation)
        assert not np.array_equal(before, after)
        assert victim not in np.unique(after)


class TestForeignDatabase:
    """A database written by something other than motile_tracker."""

    @pytest.fixture
    def foreign_db(self, tracks_2d, tmp_path):
        path = tmp_path / "foreign.db"
        td.graph.SQLGraph.from_other(
            tracks_2d.graph_full, drivername="sqlite", database=str(path)
        )
        return path

    def test_opens_with_sniffed_keys(self, foreign_db, tracks_2d):
        """Without a recorded description the attribute keys are guessed.

        Tracks defaults its time attribute to "time", but funtracks graphs call
        it "t", so guessing is what keeps such a database loadable at all.
        """
        reopened = tracks_from_sql(foreign_db)

        assert reopened.features.time_key == "t"
        assert reopened.features.position_key == "pos"
        assert reopened.graph_full.num_nodes() == tracks_2d.graph_full.num_nodes()

    def test_opens_without_a_scale(self, foreign_db):
        """No scale recorded means no scale, same as loading a geff."""
        assert tracks_from_sql(foreign_db).scale is None

    def test_scale_can_be_supplied(self, foreign_db):
        """A caller that knows the scale can pass it in."""
        assert tracks_from_sql(foreign_db, scale=[1.0, 3.0, 3.0]).scale == [
            1.0,
            3.0,
            3.0,
        ]


class TestOverwrite:
    """Replacing a database must never destroy the old one on failure."""

    def test_overwrite_replaces_contents(self, tracks_2d, graph_3d, tmp_path):
        path = tmp_path / "tracks.db"
        # Released because Windows will not rename over an open file, which is
        # exactly the precondition the export path relies on.
        close_database(
            write_tracks_to_sql(Tracks(graph_3d, ndim=4, time_attr="t"), path)
        )

        write_tracks_to_sql(tracks_2d, path, overwrite=True)

        assert tracks_from_sql(path).ndim == 3

    def test_returned_graph_is_open_at_the_real_path(self, tracks_2d, tmp_path):
        """Overwriting stages a temp file; the caller must get the final one.

        Rebinding hands this graph to Tracks, so if it were still bound to the
        staging path every later edit would be written to the wrong file.
        """
        path = tmp_path / "tracks.db"
        close_database(write_tracks_to_sql(tracks_2d, path))

        graph = write_tracks_to_sql(tracks_2d, path, overwrite=True)

        assert Path(graph._url.database) == path
        assert not list(tmp_path.glob(".*.exporting"))

    def test_overwriting_an_open_database_is_refused_clearly(
        self, tracks_2d, tmp_path, monkeypatch
    ):
        """Replacing a database something else still holds open must not happen.

        Windows raises WinError 5 here; POSIX would silently replace the file
        and leave the other reader writing to a deleted inode. Both are reported
        as the same explicit refusal, so the message does not depend on the
        platform the user happens to be on.
        """
        path = tmp_path / "tracks.db"
        write_tracks_to_sql(tracks_2d, path)  # deliberately left open
        before = path.read_bytes()

        def deny(*args, **kwargs):
            raise PermissionError("[WinError 5] Access is denied")

        monkeypatch.setattr(sql_io.os, "replace", deny)
        with pytest.raises(OSError, match="still has it open"):
            write_tracks_to_sql(tracks_2d, path, overwrite=True)

        assert path.read_bytes() == before
        assert not list(tmp_path.glob(".*.exporting"))

    def test_failed_overwrite_leaves_the_original(
        self, tracks_2d, tmp_path, monkeypatch
    ):
        """A write that blows up must not take the existing database with it."""
        path = tmp_path / "tracks.db"
        write_tracks_to_sql(tracks_2d, path)
        before = path.read_bytes()

        monkeypatch.setattr(
            sql_io,
            "_write_new_database",
            lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")),
        )
        with pytest.raises(ValueError, match="boom"):
            write_tracks_to_sql(tracks_2d, path, overwrite=True)

        assert path.read_bytes() == before
        assert not list(tmp_path.glob(".*.exporting"))


class TestSameDatabase:
    """The guard standing between an export and the user's only copy."""

    @pytest.fixture
    def opened(self, tracks_2d, tmp_path):
        write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        return tracks_from_sql(tmp_path / "tracks.db")

    def test_exact_path(self, opened, tmp_path):
        assert is_same_database(tmp_path / "tracks.db", opened)

    def test_different_file(self, opened, tmp_path):
        assert not is_same_database(tmp_path / "other.db", opened)

    def test_in_memory_tracks_are_never_the_same(self, tracks_2d, tmp_path):
        assert not is_same_database(tmp_path / "tracks.db", tracks_2d)

    def test_symlinked_parent(self, opened, tmp_path):
        """Plain Path equality misses this; on macOS /tmp is a link already."""
        link = tmp_path / "link"
        link.symlink_to(tmp_path, target_is_directory=True)

        assert is_same_database(link / "tracks.db", opened)

    def test_nonexistent_path_through_a_symlinked_parent(self, opened, tmp_path):
        """samefile cannot help when the destination does not exist yet."""
        link = tmp_path / "link"
        link.symlink_to(tmp_path, target_is_directory=True)

        assert not is_same_database(link / "missing.db", opened)


class TestWriteGuards:
    def test_refuses_existing_file(self, tracks_2d, tmp_path):
        """The caller clears the destination, so the SQL-level copy stays usable."""
        path = tmp_path / "tracks.db"
        write_tracks_to_sql(tracks_2d, path)

        with pytest.raises(FileExistsError):
            write_tracks_to_sql(tracks_2d, path)

    def test_writes_over_empty_file(self, tracks_2d, tmp_path):
        """A zero-byte file is what a save dialog leaves behind, not real data."""
        path = tmp_path / "tracks.db"
        path.touch()

        write_tracks_to_sql(tracks_2d, path)
        assert tracks_from_sql(path).graph_full.num_nodes() > 0

    def test_records_description_under_one_key(self, tracks_2d, tmp_path):
        """Everything recorded is namespaced, so nothing collides with
        tracksdata's own metadata."""
        graph = write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")

        assert META_KEY in graph.metadata
        assert "shape" in graph.metadata  # copied by tracksdata, not by us


class TestBackendQueries:
    def test_in_memory_tracks(self, tracks_2d):
        assert not is_sql_backed(tracks_2d)
        assert sql_database_path(tracks_2d) is None

    def test_database_backed_tracks(self, tracks_2d, tmp_path):
        path = tmp_path / "tracks.db"
        write_tracks_to_sql(tracks_2d, path)
        reopened = tracks_from_sql(path)

        assert is_sql_backed(reopened)
        assert sql_database_path(reopened) == path


class TestRebind:
    def test_switches_backend_and_keeps_description(self, tracks_2d, tmp_path):
        graph = write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")

        rebound = rebind_tracks_to_graph(tracks_2d, graph)

        assert is_sql_backed(rebound)
        assert sql_database_path(rebound) == tmp_path / "tracks.db"
        assert rebound.scale == tracks_2d.scale
        assert rebound.ndim == tracks_2d.ndim
        assert rebound.features.time_key == tracks_2d.features.time_key

    def test_leaves_the_original_alone(self, tracks_2d, tmp_path):
        graph = write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")

        rebind_tracks_to_graph(tracks_2d, graph)

        assert not is_sql_backed(tracks_2d)

    def test_clears_undo_history(self, tracks_2d, tmp_path):
        """The old actions reference the old graph and cannot be replayed."""
        victim = sorted(tracks_2d.graph_solution.node_ids())[-1]
        UserDeleteNodes(tracks_2d, [victim])
        assert len(tracks_2d.action_history.undo_stack) > 0

        graph = write_tracks_to_sql(tracks_2d, tmp_path / "tracks.db")
        rebound = rebind_tracks_to_graph(tracks_2d, graph)

        assert len(rebound.action_history.undo_stack) == 0

    def test_motile_run_keeps_its_run(self, graph_2d, tmp_path):
        """A solved run rebinds to a run, so its solver params are not lost."""
        params = SolverParams(max_edge_distance=42.0)
        run = MotileRun(
            graph_2d,
            run_name="a run",
            time_attr="t",
            ndim=3,
            solver_params=params,
            gaps=[0.1],
        )

        graph = write_tracks_to_sql(run, tmp_path / "run.db")
        rebound = rebind_tracks_to_graph(run, graph)

        assert isinstance(rebound, MotileRun)
        assert rebound.run_name == "a run"
        assert rebound.solver_params.max_edge_distance == 42.0
        assert rebound.gaps == [0.1]
        assert rebound.time == run.time
        assert is_sql_backed(rebound)
