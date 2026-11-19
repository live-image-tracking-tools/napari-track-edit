"""Where history logs are written.

A log sits in a sidecar directory next to the file the tracks came from
(``X.geff`` -> ``X.geff.history/``), one file per session. Tracks without a file,
or whose sidecar cannot be written, log to ``<user data dir>/history/``.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from napari_track_edit.example_data import user_data_dir

HISTORY_SUFFIX = ".history"
LOG_SUFFIX = ".jsonl"

# Paths handed out in this process. The recorder only creates its file at the first
# edit, so two sessions started in the same second would otherwise get the same name.
_handed_out: set[Path] = set()


def slug(text: str) -> str:
    """Lowercase ``text``, keeping only characters that are safe in a file name."""
    cleaned = re.sub(r"[^a-z0-9._-]+", "_", text.lower()).strip("_")
    return cleaned or "unknown"


def sidecar_dir(source: Path) -> Path:
    """The history directory next to a source file or directory."""
    return source.with_name(source.name + HISTORY_SUFFIX)


def fallback_dir() -> Path:
    """The history directory for tracks without a writable source location."""
    return user_data_dir() / "history"


def is_writable(directory: Path) -> bool:
    """Whether a log can be written in ``directory``, without creating anything.

    Checks the directory if it exists, else the closest existing parent, so that
    opening tracks does not leave an empty history directory behind.
    """
    existing = directory
    while not existing.exists():
        if existing.parent == existing:
            return False
        existing = existing.parent
    return existing.is_dir() and os.access(existing, os.W_OK | os.X_OK)


def new_log_path(directory: Path, annotator: str, prefix: str | None = None) -> Path:
    """A fresh log file name in ``directory``: ``[<prefix>_]<timestamp>_<annotator>``.

    Args:
        directory (Path): The directory the log goes in.
        annotator (str): Who is editing.
        prefix (str | None): Put in front of the name, to tell logs of different
            tracks apart in the shared fallback directory.
    """
    stem = f"{datetime.now():%Y%m%dT%H%M%S}_{slug(annotator)}"
    if prefix is not None:
        stem = f"{slug(prefix)}_{stem}"
    path = directory / f"{stem}{LOG_SUFFIX}"
    counter = 2
    while path in _handed_out or path.exists():
        path = directory / f"{stem}_{counter}{LOG_SUFFIX}"
        counter += 1
    _handed_out.add(path)
    return path
