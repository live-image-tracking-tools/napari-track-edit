"""Data-model benchmarks (no napari GUI required).

These exercise motile_tracker's own pure hot paths, so they run without a display.
``extract_sorted_tracks`` is the O(N)+topological-sort routine behind every
tree-view refresh.

(SolutionTracks construction is intentionally *not* benchmarked here -- it is
funtracks' code and is covered by funtracks' own benchmark suite.)
"""

from __future__ import annotations

import napari
from bench_ui_actions import (
    ROUNDS,  # shared round count (median-gated; see that module)
)

from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_sorted_tracks,
)


def _colormap():
    # Same colormap TracksViewer builds (tracks_viewer.py).
    return napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)


def test_extract_sorted_tracks(benchmark, shared_tracks):
    """Build the sorted-tracks dataframe that drives the tree view."""
    cmap = _colormap()
    benchmark.pedantic(
        lambda: extract_sorted_tracks(shared_tracks, cmap),
        rounds=ROUNDS,
        iterations=1,
    )
