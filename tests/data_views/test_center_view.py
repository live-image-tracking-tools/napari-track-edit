"""Tests for center_view functionality with different scale configurations."""

import napari
import numpy as np
import pytest
import tracksdata as td
from funtracks.data_model import SolutionTracks
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from tracksdata.nodes._mask import Mask

from motile_tracker.data_views.views.ortho_views import initialize_ortho_views
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


def _make_single_node_graph(
    tmp_path,
    pos: list,
    seg_bbox: list | None = None,
    seg_shape: tuple | None = None,
) -> td.graph.GraphView:
    """Create a 3D+time tracksdata graph with a single node at the given position.

    Args:
        tmp_path: Pytest tmp_path for the SQLite database.
        pos: Node position in pixel coordinates [z, y, x].
        seg_bbox: Bounding box [z0, y0, x0, z1, y1, x1] for the node's mask.
            If provided, mask/bbox node attributes and shape metadata
            are added so SolutionTracks can reconstruct the segmentation.
        seg_shape: Full segmentation array shape (t, z, y, x). Required when
            seg_bbox is provided.
    """
    node_attributes = ["pos", "area"]
    if seg_bbox is not None:
        node_attributes += [td.DEFAULT_ATTR_KEYS.MASK, td.DEFAULT_ATTR_KEYS.BBOX]

    graph = create_empty_graphview_graph(
        node_attributes=node_attributes,
        ndim=4,
        database=str(tmp_path / "graph.db"),
    )

    node: dict = {"t": 0, "pos": list(pos), "area": 1000.0, "solution": True}
    if seg_bbox is not None:
        bbox = np.array(seg_bbox, dtype=np.int64)
        mask_shape = tuple(int(bbox[i + 3] - bbox[i]) for i in range(3))
        node[td.DEFAULT_ATTR_KEYS.MASK] = Mask(
            np.ones(mask_shape, dtype=bool), bbox=bbox
        )
        node[td.DEFAULT_ATTR_KEYS.BBOX] = bbox

    graph.bulk_add_nodes(nodes=[node], indices=[1])

    if seg_shape is not None:
        graph._update_metadata(shape=seg_shape)

    return graph


@pytest.fixture
def viewer(make_napari_viewer):
    """Per-test viewer for center_view tests.

    These tests check viewer.dims.point and _indices_view, which depend on
    viewer.dims.current_step. Napari does not reset current_step when layers
    are cleared, so a fresh viewer per test is required for isolation.
    """
    return make_napari_viewer()


class TestCenterViewWithScale:
    """Test center_view correctly handles scaled data.

    The key thing to understand:
    - Node positions in the graph are in PIXEL coordinates
    - viewer.dims.point is in WORLD coordinates
    - viewer.dims.current_step is an index into the dims range
    - center_view should convert the node position with tracks.scale and position
      the viewer at the resulting world coordinates
    """

    def test_center_view_with_z_scale_less_than_one(self, viewer, tmp_path):
        """Test center_view when z-scale < 1 (common for anisotropic z).

        With z-scale = 0.5:
        - Segmentation pixel z=10 corresponds to world z=5
        - Node at world z=5 should display correctly
        """

        # Create graph - positions are in PIXEL coordinates
        # Node at pixel z=10 (box [9:11,9:11,9:11]), i.e. world z=5
        graph = _make_single_node_graph(
            tmp_path,
            pos=[10, 10, 10],
            seg_bbox=[9, 9, 9, 11, 11, 11],
            seg_shape=(2, 20, 20, 20),
        )

        scale = [1.0, 0.5, 1.0, 1.0]  # t, z, y, x
        tracks = SolutionTracks(graph=graph, scale=scale, ndim=4, time_attr="t")

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Get the point index for node 1
        points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = points_layer.node_index_dict[1]

        tracks_viewer.tracking_layers.center_view(node=1)

        # Verify viewer is positioned at world z=5
        new_point = viewer.dims.point
        assert abs(new_point[1] - 5) < 1, f"Expected world z≈5, got {new_point[1]}"

        # Verify point is visible using _indices_view
        visible_indices = points_layer._indices_view
        assert node_index in visible_indices, (
            f"Point index {node_index} not in visible indices {visible_indices}. "
            f"Viewer dims.point={viewer.dims.point}"
        )

    def test_center_view_with_z_scale_greater_than_one(self, viewer, tmp_path):
        """Test center_view when z-scale > 1.

        With z-scale = 2.0:
        - Segmentation pixel z=5 corresponds to world z=10
        """

        # Node at pixel z=5 (box [4:6,9:11,9:11]), i.e. world z=10
        graph = _make_single_node_graph(
            tmp_path,
            pos=[5, 10, 10],
            seg_bbox=[4, 9, 9, 6, 11, 11],
            seg_shape=(2, 20, 20, 20),
        )

        scale = [1.0, 2.0, 1.0, 1.0]
        tracks = SolutionTracks(graph=graph, scale=scale, ndim=4, time_attr="t")

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Get the point index for node 1
        points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = points_layer.node_index_dict[1]

        tracks_viewer.tracking_layers.center_view(node=1)

        # Verify viewer is positioned at world z=10
        new_point = viewer.dims.point
        assert abs(new_point[1] - 10) < 1, f"Expected world z≈10, got {new_point[1]}"

        # Verify point is visible using _indices_view
        visible_indices = points_layer._indices_view
        assert node_index in visible_indices, (
            f"Point index {node_index} not in visible indices {visible_indices}. "
            f"Viewer dims.point={viewer.dims.point}"
        )

    def test_center_view_with_image_layer_different_scale(self, viewer, tmp_path):
        """Test center_view when image layer has different scale than tracks seg layer.

        Image layer: scale [1,1,1,1], 20 z-pixels -> world z 0-20
        Seg layer: scale [1,0.5,1,1], 20 z-pixels -> world z 0-10
        """

        # Add an image layer with no scale (1.0 for all dims)
        image_data = np.random.rand(2, 20, 20, 20)
        viewer.add_image(image_data, name="raw_image")

        # Node at pixel z=10 (box [9:11,9:11,9:11]), i.e. world z=5
        graph = _make_single_node_graph(
            tmp_path,
            pos=[10, 10, 10],
            seg_bbox=[9, 9, 9, 11, 11, 11],
            seg_shape=(2, 20, 20, 20),
        )

        scale = [1.0, 0.5, 1.0, 1.0]
        tracks = SolutionTracks(graph=graph, scale=scale, ndim=4, time_attr="t")

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Get the point index for node 1
        points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = points_layer.node_index_dict[1]

        tracks_viewer.tracking_layers.center_view(node=1)

        # Verify viewer is positioned at world z=5
        new_point = viewer.dims.point
        assert abs(new_point[1] - 5) < 1, f"Expected world z≈5, got {new_point[1]}"

        # Verify point is visible using _indices_view
        visible_indices = points_layer._indices_view
        assert node_index in visible_indices, (
            f"Point index {node_index} not in visible indices {visible_indices}. "
            f"Viewer dims.point={viewer.dims.point}"
        )

    def test_center_view_no_scale(self, viewer, tmp_path):
        """Test center_view when no scale is set (defaults to 1.0)."""

        graph = _make_single_node_graph(
            tmp_path,
            pos=[10, 10, 10],
            seg_bbox=[9, 9, 9, 11, 11, 11],
            seg_shape=(2, 20, 20, 20),
        )

        tracks = SolutionTracks(graph=graph, ndim=4, time_attr="t")

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Get the point index for node 1
        points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = points_layer.node_index_dict[1]

        tracks_viewer.tracking_layers.center_view(node=1)

        # With no scale, world coords = pixel coords
        new_point = viewer.dims.point
        assert new_point[0] == 0  # time
        assert new_point[1] == 10  # z
        assert new_point[2] == 10  # y
        assert new_point[3] == 10  # x

        # Verify point is visible using _indices_view
        visible_indices = points_layer._indices_view
        assert node_index in visible_indices, (
            f"Point index {node_index} not in visible indices {visible_indices}. "
            f"Viewer dims.point={viewer.dims.point}"
        )

    def test_center_view_no_segmentation_with_scaled_image(self, viewer, tmp_path):
        """Test center_view when there is no segmentation, only points and an image layer.

        Image layer: scale [1, 0.5, 1, 1], 20 z-pixels -> world z 0-10
        Points: in pixel coordinates at z=10, i.e. world z=5
        No segmentation layer.
        """

        # Add image layer with z-scale=0.5
        image_data = np.random.rand(2, 20, 20, 20)
        viewer.add_image(image_data, name="raw_image", scale=[1.0, 0.5, 1.0, 1.0])

        # Node at pixel position [10, 10, 10] — no segmentation
        graph = _make_single_node_graph(tmp_path, pos=[10, 10, 10])

        tracks = SolutionTracks(
            graph=graph, scale=[1.0, 0.5, 1.0, 1.0], ndim=4, time_attr="t"
        )

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Get the point index for node 1
        points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = points_layer.node_index_dict[1]

        tracks_viewer.tracking_layers.center_view(node=1)

        # Verify viewer is positioned at world z=5
        new_point = viewer.dims.point
        assert abs(new_point[1] - 5) < 1, f"Expected world z≈5, got {new_point[1]}"

        # Verify point is visible using _indices_view
        visible_indices = points_layer._indices_view
        assert node_index in visible_indices, (
            f"Point index {node_index} not in visible indices {visible_indices}. "
            f"Viewer dims.point={viewer.dims.point}"
        )

    def test_center_view_no_segmentation_mismatched_scales(self, viewer, tmp_path):
        """Test center_view with no segmentation and mismatched image/points scales.

        Image layer: scale [1, 1, 1, 1], 20 z-pixels -> world z 0-20
        Points: scale [1, 0.5, 1, 1], positions at pixel z=10, i.e. world z=5
        No segmentation layer.

        This tests the case where the image and points have different scales,
        which affects how dims.range is computed.
        """

        # Add image layer with no z-scale (1.0)
        image_data = np.random.rand(2, 20, 20, 20)
        viewer.add_image(image_data, name="raw_image")

        # Node at pixel position [10, 10, 10] — no segmentation
        graph = _make_single_node_graph(tmp_path, pos=[10, 10, 10])

        tracks = SolutionTracks(
            graph=graph, scale=[1.0, 0.5, 1.0, 1.0], ndim=4, time_attr="t"
        )

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Get the point index for node 1
        points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = points_layer.node_index_dict[1]

        tracks_viewer.tracking_layers.center_view(node=1)

        # Verify viewer is positioned at world z=5
        new_point = viewer.dims.point
        assert abs(new_point[1] - 5) < 1, f"Expected world z≈5, got {new_point[1]}"

        # Verify point is visible using _indices_view
        visible_indices = points_layer._indices_view
        assert node_index in visible_indices, (
            f"Point index {node_index} not in visible indices {visible_indices}. "
            f"Viewer dims.point={viewer.dims.point}"
        )

    def test_center_view_syncs_ortho_views(self, viewer, qtbot, tmp_path):
        """Test that center_view properly syncs ortho views so points are visible.

        When center_view is called, the ortho views should also update their
        dims.current_step so that the point is visible in all views.
        """

        # Initialize orthogonal views
        ortho_manager = initialize_ortho_views(viewer)

        # Node at pixel position [10, 10, 10] (box [9:11,9:11,9:11]), world z=5
        graph = _make_single_node_graph(
            tmp_path,
            pos=[10, 10, 10],
            seg_bbox=[9, 9, 9, 11, 11, 11],
            seg_shape=(2, 20, 20, 20),
        )

        scale = [1.0, 0.5, 1.0, 1.0]  # z-scale = 0.5
        tracks = SolutionTracks(graph=graph, scale=scale, ndim=4, time_attr="t")

        # Show orthogonal views BEFORE adding tracks so they get the layers
        ortho_manager.show()
        qtbot.waitUntil(lambda: ortho_manager.is_shown(), timeout=1000)

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        # Wait for layers to sync to ortho views
        qtbot.wait(50)

        # Get the point index for node 1 from main points layer
        main_points_layer = tracks_viewer.tracking_layers.points_layer
        node_index = main_points_layer.node_index_dict[1]

        # Center on the node
        tracks_viewer.tracking_layers.center_view(node=1)

        # Wait for Qt event loop to process the dims sync
        qtbot.wait(50)

        # Verify main viewer point is visible
        main_visible = main_points_layer._indices_view
        assert node_index in main_visible, (
            f"Point not visible in main viewer. "
            f"Index {node_index} not in {main_visible}"
        )

        # Get ortho view points layers and verify point is visible in each
        right_vm = ortho_manager.right_widget.vm_container.viewer_model
        bottom_vm = ortho_manager.bottom_widget.vm_container.viewer_model
        right_points = next(
            layer
            for layer in right_vm.layers
            if isinstance(layer, napari.layers.Points)
        )
        bottom_points = next(
            layer
            for layer in bottom_vm.layers
            if isinstance(layer, napari.layers.Points)
        )

        # The ortho views use copied Points layers (not TrackPoints), so we check
        # _indices_view on those as well
        right_visible = right_points._indices_view
        bottom_visible = bottom_points._indices_view

        assert node_index in right_visible, (
            f"Point not visible in right ortho view. "
            f"Index {node_index} not in {right_visible}. "
            f"Ortho dims.point={right_vm.dims.point}"
        )
        assert node_index in bottom_visible, (
            f"Point not visible in bottom ortho view. "
            f"Index {node_index} not in {bottom_visible}. "
            f"Ortho dims.point={bottom_vm.dims.point}"
        )

        ortho_manager.cleanup()


def _make_track_graph(tmp_path, positions: list[tuple[int, int, int]]):
    """3D+time graph holding one track that walks through the given pixel positions."""
    graph = create_empty_graphview_graph(
        node_attributes=[
            "pos",
            "area",
            td.DEFAULT_ATTR_KEYS.MASK,
            td.DEFAULT_ATTR_KEYS.BBOX,
        ],
        ndim=4,
        database=str(tmp_path / "graph.db"),
    )
    nodes = []
    for t, (z, y, x) in enumerate(positions):
        bbox = np.array([z - 1, y - 1, x - 1, z + 2, y + 2, x + 2], dtype=np.int64)
        shape = tuple(int(bbox[i + 3] - bbox[i]) for i in range(3))
        nodes.append(
            {
                "t": t,
                "pos": [float(z), float(y), float(x)],
                "area": 27.0,
                "solution": True,
                td.DEFAULT_ATTR_KEYS.MASK: Mask(np.ones(shape, dtype=bool), bbox=bbox),
                td.DEFAULT_ATTR_KEYS.BBOX: bbox,
            }
        )
    ids = list(range(1, len(positions) + 1))
    graph.bulk_add_nodes(nodes=nodes, indices=ids)
    graph.bulk_add_edges(
        [
            {"source_id": a, "target_id": b, "solution": True}
            for a, b in zip(ids, ids[1:], strict=False)
        ]
    )
    graph._update_metadata(shape=(len(positions), 60, 600, 600))
    return graph


def test_center_view_does_not_pan_for_a_visible_node(viewer, tmp_path):
    """Centering on a node that is already on screen must leave the camera alone.

    The in-view check must be against what the canvas is showing. Using
    ``points_layer.corner_pixels`` does not do that: napari clips those to the
    layer's own data extent, so they describe the bounding box of the point cloud,
    and every node on the edge of a track reads as "out of view". The resulting
    pointless camera pans are what desynchronise napari's cursor.position (which
    it only refreshes on real mouse events), and the orthogonal views' "T"
    shortcut then acts on a stale mouse position.
    """
    # a track wandering across the middle of the image, so its bounding box is
    # much smaller than the image and the first/last nodes sit on its edge
    positions = [(30, 280 + 8 * i, 290 + 6 * i) for i in range(12)]
    scale = [1.0, 1.0, 0.416, 0.416]
    tracks = SolutionTracks(
        graph=_make_track_graph(tmp_path, positions),
        scale=scale,
        ndim=4,
        time_attr="t",
    )

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")
    layers = tracks_viewer.tracking_layers

    # Sit on the middle node, then jump to the ends of the track. The whole track
    # spans ~37 x 27 world units and the view is far wider, so all of it is on
    # screen and none of these jumps needs a pan.
    tracks_viewer.center_on_node(6)
    for node in (1, len(positions), 6):
        min_y, max_y, min_x, max_x = layers._visible_world_range()
        location = layers._to_world(tracks.get_position(node, incl_time=True))
        y_dim, x_dim = viewer.dims.displayed[-2], viewer.dims.displayed[-1]
        assert min_y < location[y_dim] < max_y, "test setup: node is off screen"
        assert min_x < location[x_dim] < max_x, "test setup: node is off screen"

        before = tuple(viewer.camera.center)
        tracks_viewer.center_on_node(node)
        assert tuple(viewer.camera.center) == before, (
            f"centering on visible node {node} panned the camera from {before} to "
            f"{tuple(viewer.camera.center)}"
        )


def test_center_view_pans_for_an_offscreen_node(viewer, tmp_path):
    """The counterpart: a node outside the view does still bring the camera along."""
    positions = [(30, 30, 30), (30, 560, 560)]
    tracks = SolutionTracks(
        graph=_make_track_graph(tmp_path, positions),
        scale=[1.0, 1.0, 0.416, 0.416],
        ndim=4,
        time_attr="t",
    )

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")
    layers = tracks_viewer.tracking_layers

    tracks_viewer.center_on_node(1)
    viewer.camera.zoom = viewer.camera.zoom * 8  # zoom in so node 2 is off screen

    min_y, max_y, _, _ = layers._visible_world_range()
    location = layers._to_world(tracks.get_position(2, incl_time=True))
    y_dim = viewer.dims.displayed[-2]
    assert not (min_y < location[y_dim] < max_y), "test setup: node 2 is on screen"

    before = tuple(viewer.camera.center)
    tracks_viewer.center_on_node(2)
    assert tuple(viewer.camera.center) != before
