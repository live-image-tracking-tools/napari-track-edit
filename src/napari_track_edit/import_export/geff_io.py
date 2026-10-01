"""Helpers for writing geff stores that hold extra, non-geff files.

Saving tracks writes a geff store, and dependent applications add their own
files inside it by listening to TracksList.tracks_saved. That is a supported
arrangement — a geff is a zarr directory, and rewriting the geff leaves
everything else alone — but it makes both zarr and geff chatty.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from funtracks.data_model import Tracks
from funtracks.import_export import write_to_geff


def is_geff(directory: Path) -> bool:
    """Whether the given directory is itself a geff store.

    A geff keeps its graph in `nodes`/`edges` groups at the top level, so their
    presence distinguishes a directory that is a geff from one that merely
    contains one, or is empty.

    Note that geff's own `check_for_geff` cannot be used here: it reports
    whether a geff exists at or under a store, and so returns True for an old
    run directory containing tracks.geff, for a v1 run directory, and even for
    an empty one.
    """
    return (directory / "nodes").exists() and (directory / "edges").exists()


def write_geff_over(tracks: Tracks, path: Path) -> None:
    """Write tracks to a geff store, replacing any geff already there.

    Saved tracks are a geff store that dependents may also keep their own files
    in: tracks_saved listeners write extra data (e.g. solver params) inside the
    store, and it survives because writing a geff only replaces geff-controlled
    groups. Zarr walks the directory on the way and warns once per file it does
    not recognise, and geff warns that it found non-geff members. Both are
    expected for any store with extras in it and say nothing the caller can act
    on, so they are silenced.

    The filters match on message rather than category: zarr only grew a
    dedicated ZarrUserWarning class in 3.x, and this package supports 2.x,
    where importing it fails outright.

    `overwrite` is only passed when there really is a geff to replace, because
    geff deletes the old graph by removing its `nodes`/`edges` groups outright
    and raises KeyError if they are absent. An empty directory needs more than
    that: geff's `check_for_geff` reports one as an existing geff, so writing
    without `overwrite` raises FileExistsError while writing with it raises
    KeyError. Removing it first leaves geff to create the store itself. Only
    an empty directory is removed, never one holding a caller's own files.

    Args:
        tracks (Tracks): The tracks to write.
        path (Path): The geff store to write them to. Created if it does not
            exist; any geff already there is replaced.
    """
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Object at .* is not recognized as a component of a Zarr hierarchy",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="Found non-geff members in zarr.*",
            category=UserWarning,
        )
        write_to_geff(tracks, path, overwrite=is_geff(path))
