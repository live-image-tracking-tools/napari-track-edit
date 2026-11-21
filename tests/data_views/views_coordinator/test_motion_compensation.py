"""Tests for following the detections when stepping through time."""

import numpy as np
import pytest
from funtracks.data_model import Tracks
from funtracks.user_actions import UserDeleteNodes
from funtracks.utils.tracksdata_utils import create_empty_graph

from napari_track_edit.application_menus.visualization_widget import (
    VisualizationWidget,
)
from napari_track_edit.data_views.views.ortho_views import initialize_ortho_views
from napari_track_edit.data_views.views_coordinator.motion_compensation import (
    DetectionMotion,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer

CENTER = np.array([50.0, 50.0, 50.0])
RADIUS = 30.0
N_CELLS = 40
# between t=0 and t=1 the sphere collapses to half its size while its center moves
# 10 along x; between t=1 and t=2 it stays put
COLLAPSE_SCALE = 0.5
COLLAPSE_SHIFT = np.array([0.0, 0.0, 10.0])


def _sphere_points(n: int = N_CELLS) -> np.ndarray:
    """Points spread evenly over a sphere (Fibonacci lattice)."""
    i = np.arange(n) + 0.5
    polar = np.arccos(1 - 2 * i / n)
    azimuth = np.pi * (1 + 5**0.5) * i
    unit = np.stack(
        [
            np.cos(polar),
            np.sin(polar) * np.sin(azimuth),
            np.sin(polar) * np.cos(azimuth),
        ],
        axis=1,
    )
    return CENTER + RADIUS * unit


def _collapse(points: np.ndarray) -> np.ndarray:
    """Where the sphere's points end up after the collapse."""
    return CENTER + COLLAPSE_SCALE * (points - CENTER) + COLLAPSE_SHIFT


def _node_id(time: int, index: int) -> int:
    return time * N_CELLS + index + 1


@pytest.fixture
def collapsing_tracks() -> Tracks:
    """Unlinked detections of cells on a sphere that collapses between t=0 and t=1 and
    then stays put until t=2."""

    sphere = _sphere_points()
    graph = create_empty_graph(node_attributes=["pos"], ndim=4)
    nodes, indices = [], []
    for time, positions in enumerate([sphere, _collapse(sphere), _collapse(sphere)]):
        for index, pos in enumerate(positions):
            nodes.append({"t": time, "pos": pos.tolist(), "solution": True})
            indices.append(_node_id(time, index))
    graph.bulk_add_nodes(nodes=nodes, indices=indices)
    graph._update_metadata(shape=(3, 100, 100, 100))
    return Tracks(graph=graph, ndim=4, time_attr="t")


# --- the motion of the detections ------------------------------------------------


def test_detections_follow_a_collapse(collapsing_tracks):
    motion = DetectionMotion(collapsing_tracks)
    point = np.array([80.0, 50, 50])

    np.testing.assert_allclose(
        motion.map_position(point, 0, 1), _collapse(point), atol=1e-9
    )


def test_jumping_and_stepping_back(collapsing_tracks):
    motion = DetectionMotion(collapsing_tracks)
    point = np.array([80.0, 50, 50])

    forward = motion.map_position(point, 0, 2)
    np.testing.assert_allclose(forward, _collapse(point), atol=1e-9)
    np.testing.assert_allclose(motion.map_position(forward, 2, 0), point, atol=1e-9)


def test_no_detections_at_a_time_point(collapsing_tracks):
    motion = DetectionMotion(collapsing_tracks)

    assert motion.map_position(CENTER, 0, 3) is None


def test_a_single_detection_only_shifts():
    graph = create_empty_graph(node_attributes=["pos"], ndim=4)
    graph.bulk_add_nodes(
        nodes=[
            {"t": 0, "pos": [10.0, 10, 10], "solution": True},
            {"t": 1, "pos": [12.0, 10, 10], "solution": True},
        ],
        indices=[1, 2],
    )
    motion = DetectionMotion(Tracks(graph=graph, ndim=4, time_attr="t"))

    np.testing.assert_allclose(motion.map_position([50.0, 50, 50], 0, 1), [52, 50, 50])


# --- following in the viewer ---------------------------------------------------


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear the shared viewer's layers between tests, and stop this test's
    TracksViewer from following the time slider of the viewer that outlives it."""
    yield
    instance = getattr(TracksViewer, "_instance", None)
    if instance is not None:
        viewer.dims.events.point.disconnect(instance._on_dims_point_changed)
    viewer.layers.clear()


@pytest.fixture
def tracks_viewer(viewer, collapsing_tracks):
    # an empty image spanning the whole volume, because without a segmentation the
    # sliders would only span the extent of the points
    viewer.add_image(np.zeros((3, 100, 100, 100), dtype=np.uint8))
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=collapsing_tracks, name="test")
    return tracks_viewer


def test_not_following_keeps_the_view(viewer, tracks_viewer):
    viewer.dims.point = (0, 80, 50, 50)
    viewer.dims.set_current_step(0, 1)

    assert tuple(viewer.dims.point) == (1, 80, 50, 50)


def test_following_a_collapse(viewer, tracks_viewer):
    """Looking at a cell on the top of the sphere, the view follows that cell inwards
    when the sphere collapses."""

    tracks_viewer.set_follow(True)
    viewer.dims.point = (0, 80, 50, 50)
    viewer.dims.set_current_step(0, 1)

    # the top of the collapsed sphere: z 50 + 0.5 * 30, x shifted by 10
    np.testing.assert_allclose(viewer.dims.point, (1, 65, 50, 60), atol=1)


def test_stepping_back_returns_to_the_start(viewer, tracks_viewer):
    tracks_viewer.set_follow(True)
    viewer.dims.point = (0, 80, 50, 50)
    viewer.dims.set_current_step(0, 1)
    viewer.dims.set_current_step(0, 0)

    np.testing.assert_allclose(viewer.dims.point, (0, 80, 50, 50), atol=1)


def test_no_motion_keeps_the_view(viewer, tracks_viewer):
    """Between t=1 and t=2 the detections do not move, so neither does the view."""

    tracks_viewer.set_follow(True)
    viewer.dims.point = (1, 60, 40, 30)
    viewer.dims.set_current_step(0, 2)

    np.testing.assert_allclose(viewer.dims.point, (2, 60, 40, 30), atol=1)


def test_jumping_to_a_node_is_not_followed(viewer, tracks_viewer):
    """Selecting a node at the current z only changes time, but the view still lands
    exactly on the node."""

    tracks_viewer.set_follow(True)
    node = _node_id(1, 0)
    location = tracks_viewer.tracks.get_position(node)
    viewer.dims.point = (0, *location)

    tracks_viewer.tracking_layers.center_view(node)

    np.testing.assert_allclose(viewer.dims.point, (1, *location))


def test_slider_after_jumping_starts_from_the_new_time(viewer, tracks_viewer):
    tracks_viewer.set_follow(True)
    viewer.dims.point = (0, 80, 50, 50)
    tracks_viewer.tracking_layers.center_view(_node_id(1, 0))
    viewer.dims.set_current_step(0, 2)  # no motion between t=1 and t=2

    location = tracks_viewer.tracks.get_position(_node_id(1, 0))
    np.testing.assert_allclose(viewer.dims.point, (2, *location), atol=1)


def test_edits_make_the_motion_stale_until_recomputed(viewer, tracks_viewer):
    """Edits do not change the motion until it is recomputed: once all detections at
    t=1 are deleted and the motion is recomputed, stepping there no longer moves."""

    tracks_viewer.set_follow(True)
    UserDeleteNodes(tracks_viewer.tracks, [_node_id(1, i) for i in range(N_CELLS)])
    assert tracks_viewer.follow_stale

    # still the motion from before the edit
    viewer.dims.point = (0, 80, 50, 50)
    viewer.dims.set_current_step(0, 1)
    np.testing.assert_allclose(viewer.dims.point, (1, 65, 50, 60), atol=1)

    tracks_viewer.recompute_follow()
    assert not tracks_viewer.follow_stale

    viewer.dims.set_current_step(0, 0)
    viewer.dims.point = (0, 80, 50, 50)
    viewer.dims.set_current_step(0, 1)
    assert tuple(viewer.dims.point) == (1, 80, 50, 50)


def test_new_tracks_stop_following(tracks_viewer, collapsing_tracks):
    tracks_viewer.set_follow(True)
    tracks_viewer.update_tracks(tracks=collapsing_tracks, name="other")

    assert not tracks_viewer.follow_enabled


def test_orthogonal_views_follow_the_detections(viewer, collapsing_tracks, qtbot):
    """Every view follows, including the one whose own time slider was moved."""

    ortho_manager = initialize_ortho_views(viewer)
    ortho_manager.show()
    qtbot.waitUntil(ortho_manager.is_shown, timeout=1000)

    viewer.add_image(np.zeros((3, 100, 100, 100), dtype=np.uint8))
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=collapsing_tracks, name="test")
    tracks_viewer.set_follow(True)
    qtbot.wait(50)

    right_vm = ortho_manager.right_widget.vm_container.viewer_model
    bottom_vm = ortho_manager.bottom_widget.vm_container.viewer_model

    viewer.dims.point = (0, 80, 50, 50)
    qtbot.wait(50)

    # move time on the right orthogonal view, the way the user would
    right_vm.dims.set_current_step(0, 1)
    qtbot.wait(50)

    expected = (1, 65, 50, 60)
    np.testing.assert_allclose(viewer.dims.point, expected, atol=1)
    np.testing.assert_allclose(right_vm.dims.point, expected, atol=1)
    np.testing.assert_allclose(bottom_vm.dims.point, expected, atol=1)

    ortho_manager.cleanup()


def test_follow_widget(viewer, tracks_viewer, qtbot):
    """The checkbox switches following on and off. The recompute button is only
    enabled when the motion is out of date."""

    widget = VisualizationWidget(viewer)
    qtbot.addWidget(widget)
    checkbox = widget.follow_widget.checkbox
    recompute = widget.follow_widget.recompute_btn

    checkbox.setChecked(True)
    assert tracks_viewer.follow_enabled
    assert not recompute.isEnabled()

    UserDeleteNodes(tracks_viewer.tracks, [_node_id(2, 0)])
    assert recompute.isEnabled()
    recompute.click()
    assert not recompute.isEnabled()

    tracks_viewer.set_follow(False)
    assert not checkbox.isChecked()
