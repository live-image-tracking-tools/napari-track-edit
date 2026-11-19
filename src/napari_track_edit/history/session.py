"""The history log of one tracks object in the tracks list.

Wraps funtracks' HistoryRecorder with what NTE decides: where the log goes, who the
annotator is, and starting a new log after a save. Every edit, undo and redo of the
tracks is recorded; see the funtracks history log docs for the file format.
"""

from __future__ import annotations

import getpass
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from funtracks.history import HistoryRecorder
from napari.utils.notifications import show_warning
from qtpy.QtCore import QSettings

from napari_track_edit.history.paths import (
    fallback_dir,
    is_writable,
    new_log_path,
    sidecar_dir,
)
from napari_track_edit.import_export.sql_io import is_sql_backed, sql_database_path

if TYPE_CHECKING:
    from funtracks.data_model import Tracks

_ANNOTATOR_KEY = "history/annotator"


def _settings() -> QSettings:
    return QSettings("napari-track-edit", "napari-track-edit")


def default_annotator() -> str:
    """The OS username, or "unknown" if it cannot be determined."""
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - getuser raises various errors without a user
        return "unknown"


def load_annotator() -> str:
    """The annotator name from the settings, defaulting to the OS username."""
    name = _settings().value(_ANNOTATOR_KEY, "", type=str)
    return name or default_annotator()


def store_annotator(name: str) -> None:
    """Remember the annotator name for the next sessions."""
    _settings().setValue(_ANNOTATOR_KEY, name)


class _NotifyHandler(logging.Handler):
    """Show warnings of the funtracks recorder (a failed log, a partial edit) in
    napari, since the user would otherwise not notice that recording stopped."""

    def emit(self, record: logging.LogRecord) -> None:
        show_warning(record.getMessage())


def _install_notify_handler() -> None:
    funtracks_logger = logging.getLogger("funtracks.history.recorder")
    if not any(isinstance(h, _NotifyHandler) for h in funtracks_logger.handlers):
        funtracks_logger.addHandler(_NotifyHandler(level=logging.WARNING))


def _source_kind(path: Path) -> str:
    if path.suffix == ".geff":
        return "geff"
    if path.suffix == ".csv":
        return "csv"
    return "other"


class HistorySession:
    """Record the edits of one tracks object to a history log.

    The log goes next to the file the tracks came from (a database-backed tracks
    object always logs next to its database), or to the fallback directory if there
    is no such file or it cannot be written. The log file is only created at the first
    edit.

    Args:
        tracks (Tracks): The tracks to record.
        name (str): The name shown in the tracks list, used to name fallback logs.
        source_path (Path | None): The file the tracks were loaded from, if any.
        annotator (str): Who is editing.
    """

    def __init__(
        self,
        tracks: Tracks,
        name: str,
        source_path: Path | None,
        annotator: str,
    ):
        _install_notify_handler()
        self.tracks = tracks
        self._name = name
        self._annotator = annotator
        self._previous_log: Path | None = None
        database = sql_database_path(tracks) if is_sql_backed(tracks) else None
        if database is not None:
            source = {"kind": "sql", "path": str(database)}
            directory = sidecar_dir(database)
        elif source_path is not None:
            source = {"kind": _source_kind(source_path), "path": str(source_path)}
            directory = sidecar_dir(source_path)
        else:
            source = {"kind": "none", "path": None}
            directory = None
        self._kind = source["kind"]
        self._recorder = self._start(directory, source)

    @property
    def log_path(self) -> Path:
        """The log file of the current session (created at its first edit)."""
        return self._recorder.path

    def set_annotator(self, name: str) -> None:
        """Record that a different person continues editing from here on."""
        self._annotator = name
        self._recorder.set_annotator(name)

    def saved(self, path: Path) -> None:
        """Record that the tracks were saved to the geff store at ``path``.

        Database-backed tracks keep logging next to their database, which is where
        the edits keep going. Otherwise the current log is closed and a new one starts
        next to the saved store, with the saved state as its baseline, so that every
        log replays onto its own baseline.

        Args:
            path (Path): The geff store the tracks were saved to.
        """
        if self._kind == "sql":
            self._recorder.mark_saved(path, self.log_path)
            return
        # A session without edits leaves no file; link past it to the last real log
        old_log = self.log_path
        previous = old_log if old_log.exists() else self._previous_log
        source = {"kind": "geff", "path": str(path)}
        directory = sidecar_dir(path)
        next_log = self._log_path_in(directory)
        self._recorder.mark_saved(path, next_log)
        self._recorder.close()
        self._previous_log = previous
        self._kind = source["kind"]
        self._recorder = self._start(directory, source, log_path=next_log)

    def close(self) -> None:
        """Finish the log. Safe to call more than once."""
        self._recorder.close()

    def _log_path_in(self, directory: Path | None) -> Path:
        if directory is not None and is_writable(directory):
            return new_log_path(directory, self._annotator)
        fallback = new_log_path(fallback_dir(), self._annotator, prefix=self._name)
        if directory is not None:
            show_warning(
                f"Cannot write the history log in {directory}; writing it to "
                f"{fallback} instead."
            )
        return fallback

    def _start(
        self,
        directory: Path | None,
        source: dict[str, Any],
        log_path: Path | None = None,
    ) -> HistoryRecorder:
        return HistoryRecorder(
            self.tracks,
            log_path if log_path is not None else self._log_path_in(directory),
            annotator=self._annotator,
            source=source,
            provenance_packages=["napari-track-edit"],
            previous_log=self._previous_log,
        )
