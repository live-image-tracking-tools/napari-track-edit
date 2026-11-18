from pathlib import Path

import zarr
from funtracks.utils import get_store_path
from qtpy.QtWidgets import (
    QLayout,
)

from napari_track_edit.import_export.geff_io import is_geff


def geff_group_path(root: zarr.Group) -> Path:
    """Return the filesystem path to a geff zarr group.

    Handles both zarr v2 and v3: works from the group's store and its relative
    path within that store, rather than v3-only attributes like `store_path`.

    Args:
        root (zarr.Group): The geff group (may be a subgroup of its store).

    Returns:
        Path: The filesystem path to the geff group itself.
    """
    return get_store_path(root.store) / Path(root.path)


def find_geff_paths(folder: Path, depth: int = 2) -> list[Path]:
    """All geff stores at or below `folder`, searching at most `depth` levels.

    Searches the filesystem rather than zarr groups. A zarr group only lists
    children of its own zarr format, and opening a plain folder as a group
    creates one there, so a zarr search misses a v2 geff inside a plain folder
    and writes into the folder while doing so.

    Args:
        folder (Path): The directory to search.
        depth (int): How many directory levels below `folder` to search. Keeps
            a folder like the home directory from being walked entirely.

    Returns:
        list[Path]: The geff stores found, in sorted order. A geff is not
            searched for further geffs inside it, and folders that cannot be
            read are skipped.
    """
    try:
        if is_geff(folder):
            return [folder]
        if depth == 0:
            return []
        children = sorted(p for p in folder.iterdir() if p.is_dir())
    except PermissionError:
        return []
    return [found for child in children for found in find_geff_paths(child, depth - 1)]


def find_single_geff(folder: Path) -> Path:
    """The one geff store at or below `folder`, see find_geff_paths.

    Raises:
        ValueError: If there is no geff, or more than one so that picking one
            would be a guess.
    """
    geff_paths = find_geff_paths(folder)
    if not geff_paths:
        raise ValueError("No GEFF group found in the selected directory.")
    if len(geff_paths) > 1:
        raise ValueError(
            "Multiple GEFF groups found in the selected directory, "
            "select one of them directly:\n"
            + "\n".join(str(p.relative_to(folder)) for p in geff_paths)
        )
    return geff_paths[0]


def clear_layout(layout: QLayout) -> None:
    """Recursively clear all widgets and layouts in a QLayout.

    Args:
        layout (QLayout): The layout to clear.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        # If the item is a layout itself, clear it recursively
        elif item.layout() is not None:
            clear_layout(item.layout())
