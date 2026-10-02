"""Fixtures for the benchmark suite.

Runs under pytest's default (prepend) import mode, which puts this directory on
sys.path, so ``synthetic_data`` is importable by bare name here and in the bench
modules. The parent ``tests/conftest.py`` autouse ``reset_tracks_viewer`` fixture
clears the TracksViewer singleton around every test, so each benchmark builds its
own viewer/app; mutating benchmarks additionally use freshly-generated tracks.
"""

from __future__ import annotations

import os

import pytest
from synthetic_data import PRESETS, generate_synthetic_tracks

from napari_track_edit.application_menus import StartupWidget
from napari_track_edit.data_views import TreeWidget
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer

# CI benchmarks only the `large` preset: the `small` preset's absolute times are so
# short (~0.03-0.06s) that normal runner jitter reads as huge percent swings and
# trips the regression gate. `large` exercises the same code paths at a stable scale.
# Set MT_BENCH_PRESET (small/large/xlarge/large_2d) to pin a different size locally.
DEFAULT_SWEEP = ["large"]
_env_preset = os.environ.get("MT_BENCH_PRESET")
SWEEP = [_env_preset] if _env_preset else DEFAULT_SWEEP


@pytest.fixture(scope="session", params=SWEEP)
def bench_params(request):
    return PRESETS[request.param]


@pytest.fixture(scope="session")
def shared_tracks(bench_params):
    """Session-scoped tracks for READ-ONLY benchmarks (never mutate these)."""
    return generate_synthetic_tracks(bench_params)


@pytest.fixture
def fresh_tracks(bench_params):
    """Freshly-generated tracks for MUTATING benchmarks (delete/add/undo/redo)."""
    return generate_synthetic_tracks(bench_params)


@pytest.fixture
def build_app(make_napari_viewer):
    """Return a builder: tracks -> (viewer, tracks_viewer, tree_widget).

    Uses make_napari_viewer so the viewer is torn down by napari's fixture.
    """

    def _build(tracks):
        viewer = make_napari_viewer()
        StartupWidget(viewer, mode="editing")
        tv = TracksViewer.get_instance(viewer)
        tv.tracks_list.add_tracks(tracks, "synthetic")
        tree_widget = viewer.window._qt_window.findChild(TreeWidget)
        return viewer, tv, tree_widget

    return _build
