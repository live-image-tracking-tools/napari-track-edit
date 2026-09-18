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
        pos: Node position in world coordinates [z, y, x].
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
    - Node positions in the graph are in WORLD coordinates (scaled)
    - viewer.dims.point is in WORLD coordinates
    - viewer.dims.current_step is an index into the dims range
    - center_view should position the viewer at the node's world coordinates
    """

    def test_center_view_with_z_scale_less_than_one(self, viewer, tmp_path):
        """Test center_view when z-scale < 1 (common for anisotropic z).

        With z-scale = 0.5:
        - Segmentation pixel z=10 corresponds to world z=5
        - Node at world z=5 should display correctly
        """

        # Create graph - positions are in WORLD coordinates
        # Node at world position [5, 10, 10]; pixel z=10 (box [9:11,9:11,9:11])
        graph = _make_single_node_graph(
            tmp_path,
            pos=[5, 10, 10],
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

        # Center on node 1 at world position [25, 50, 50]
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

        # Node at world position [10, 10, 10]; pixel z=5 (box [4:6,9:11,9:11])
        graph = _make_single_node_graph(
            tmp_path,
            pos=[10, 10, 10],
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

        # Node at world z=5 (box [9:11,9:11,9:11])
        graph = _make_single_node_graph(
            tmp_path,
            pos=[5, 10, 10],
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
        Points: in world coordinates at z=5
        No segmentation layer.
        """

        # Add image layer with z-scale=0.5
        image_data = np.random.rand(2, 20, 20, 20)
        viewer.add_image(image_data, name="raw_image", scale=[1.0, 0.5, 1.0, 1.0])

        # Node at world position [5, 10, 10] — no segmentation
        graph = _make_single_node_graph(tmp_path, pos=[5, 10, 10])

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
        Points: scale [1, 0.5, 1, 1], positions at world z=5
        No segmentation layer.

        This tests the case where the image and points have different scales,
        which affects how dims.range is computed.
        """

        # Add image layer with no z-scale (1.0)
        image_data = np.random.rand(2, 20, 20, 20)
        viewer.add_image(image_data, name="raw_image")

        # Node at world position [5, 10, 10] — no segmentation
        graph = _make_single_node_graph(tmp_path, pos=[5, 10, 10])

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

        # Node at world position [5, 10, 10] (box [9:11,9:11,9:11])
        graph = _make_single_node_graph(
            tmp_path,
            pos=[5, 10, 10],
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


class TestCenterViewInEditingMode:
    """Test that the restriction on centering while a tracking layer is in an editing
    mode only applies to interactions in the napari canvas.

    Centering while painting is annoying, but requests coming from the tree view, the
    table or the menus should still center, whatever mode the layers are in.
    """

    node_point = (0, 5, 10, 10)  # the location of node 1
    away_point = (1, 15, 15, 15)  # somewhere else, to center away from

    def _make_tracks_viewer(self, viewer, tmp_path, segmentation: bool) -> TracksViewer:
        """Set up a tracks viewer with a single node at world position [5, 10, 10]."""

        if segmentation:
            graph = _make_single_node_graph(
                tmp_path,
                pos=[5, 10, 10],
                seg_bbox=[4, 9, 9, 6, 11, 11],
                seg_shape=(2, 20, 20, 20),
            )
        else:
            # without a segmentation, an image layer is needed to give the viewer a
            # dims range: with only a single point, the range is degenerate and
            # dims.point cannot be moved off the node
            viewer.add_image(np.zeros((2, 20, 20, 20)), name="raw_image")
            graph = _make_single_node_graph(tmp_path, pos=[5, 10, 10])

        tracks = SolutionTracks(
            graph=graph, scale=[1.0, 1.0, 1.0, 1.0], ndim=4, time_attr="t"
        )
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")
        return tracks_viewer

    def test_seg_layer_mode_only_restricts_the_canvas(self, viewer, tmp_path):
        """With a segmentation layer, its mode decides whether canvas interactions
        center, and requests from the other views center regardless."""

        tracks_viewer = self._make_tracks_viewer(viewer, tmp_path, segmentation=True)
        seg_layer = tracks_viewer.tracking_layers.seg_layer
        seg_layer.mode = "paint"

        # a request from another view (tree view, table, menus) centers in paint mode
        viewer.dims.point = self.away_point
        tracks_viewer.center_on_node(1)
        assert viewer.dims.point == self.node_point

        # the same request from the canvas does not
        viewer.dims.point = self.away_point
        with tracks_viewer.viewer_interaction():
            tracks_viewer.center_on_node(1)
        assert viewer.dims.point == self.away_point

        # ... but it does once the layer is back in pan_zoom mode
        seg_layer.mode = "pan_zoom"
        with tracks_viewer.viewer_interaction():
            tracks_viewer.center_on_node(1)
        assert viewer.dims.point == self.node_point

    def test_points_layer_mode_restricts_the_canvas_without_seg_layer(
        self, viewer, tmp_path
    ):
        """Without a segmentation layer, the points layer mode decides.

        Selecting a point with the select tool goes through _update_selection (not
        process_click), so that path has to be marked as a canvas interaction too.
        """

        tracks_viewer = self._make_tracks_viewer(viewer, tmp_path, segmentation=False)
        points_layer = tracks_viewer.tracking_layers.points_layer
        points_layer.mode = "select"

        # selecting a point in the canvas fires items_changed -> _update_selection
        viewer.dims.point = self.away_point
        points_layer.selected_data = {points_layer.node_index_dict[1]}
        assert viewer.dims.point == self.away_point

        # a request from another view still centers, whatever the points layer mode is
        tracks_viewer.center_on_node(1)
        assert viewer.dims.point == self.node_point
