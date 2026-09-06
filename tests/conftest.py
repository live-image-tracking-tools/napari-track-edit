import numpy as np
import pytest
import tracksdata as td
from funtracks.data_model import SolutionTracks, Tracks
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from tracksdata.nodes._mask import Mask

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture
def click_node():
    """Return a helper that selects a node by simulating a layer click.

    Prefers the TrackLabels path when a seg layer exists, because that is
    the realistic path that produces np.int64 node IDs (via layer.get_value()
    on a numpy image array). When no seg layer is present, falls back to
    adding np.int64 directly so the type is still realistic.

    This ensures operations like connect_nodes() are tested with the same types
    they receive in the real UI, catching bugs like tracksdata's in_degree()
    failing on np.int64.

    Usage::

        click_node(tracks_viewer, node_id)               # select only this node
        click_node(tracks_viewer, node_id, append=True)  # shift-click (append)
    """

    class _Event:
        def __init__(self, append):
            self.modifiers = ["Shift"] if append else []

    def _click(tracks_viewer, node_id, append=False):
        seg_layer = tracks_viewer.tracking_layers.seg_layer
        if seg_layer is not None:
            # Realistic path: Labels layer returns np.int64 from image pixel values
            seg_layer.process_click(_Event(append), np.int64(node_id))
        else:
            # No seg layer: node_id comes from graph.node_ids() which returns Python int
            tracks_viewer.selected_nodes.add(node_id, append)

    return _click


@pytest.fixture(autouse=True)
def reset_tracks_viewer():
    """Reset TracksViewer singleton before and after each test.

    This autouse fixture ensures the TracksViewer singleton is cleared
    before and after each test to avoid state leakage between tests.
    """
    # clear the singleton before test
    if hasattr(TracksViewer, "_instance"):
        del TracksViewer._instance

    # after test, clear keymap and delete singleton
    yield
    if hasattr(TracksViewer, "_instance"):
        instance = TracksViewer._instance
        if hasattr(instance, "viewer") and instance.viewer is not None:
            instance.viewer.keymap.clear()
        del TracksViewer._instance


def _make_mask(bbox: list[int]) -> Mask:
    """Create a filled box Mask from a bbox.

    For 2D spatial masks: bbox = [y0, x0, y1, x1]
    For 3D spatial masks: bbox = [z0, y0, x0, z1, y1, x1]
    """
    ndim = len(bbox) // 2
    shape = tuple(bbox[i + ndim] - bbox[i] for i in range(ndim))
    return Mask(np.ones(shape, dtype=bool), bbox=np.array(bbox, dtype=np.int64))


@pytest.fixture
def graph_2d() -> td.graph.GraphView:
    """2D+time graph (ndim=3) with 6 nodes including a division and an unconnected node.

    Nodes include mask/bbox attributes (frame shape 100x100, 5 timepoints).
    """
    graph = create_empty_graphview_graph(
        node_attributes=[
            "pos",
            "area",
            "track_id",
            "lineage_id",
            td.DEFAULT_ATTR_KEYS.MASK,
            td.DEFAULT_ATTR_KEYS.BBOX,
        ],
        edge_attributes=["iou"],
        ndim=3,
    )
    # bboxes: [y0, x0, y1, x1]
    bboxes = [
        [30, 30, 71, 71],  # node 1, t=0: disk center=(50,50) r=20  → area 41*41=1681
        [10, 70, 31, 91],  # node 2, t=1: disk center=(20,80) r=10  → area 21*21=441
        [45, 30, 76, 61],  # node 3, t=1: disk center=(60,45) r=15  → area 31*31=961
        [0, 0, 4, 4],  # node 4, t=2: square (0:4, 0:4)        → area 4*4=16
        [0, 0, 4, 4],  # node 5, t=4: square (0:4, 0:4)        → area 4*4=16
        [96, 96, 100, 100],  # node 6, t=4: square (96:100, 96:100)  → area 4*4=16
    ]
    nodes = [
        {
            "t": 0,
            "pos": [50.0, 50.0],
            "area": 1681.0,
            "track_id": 1,
            "lineage_id": 1,
            "solution": True,
        },
        {
            "t": 1,
            "pos": [20.0, 80.0],
            "area": 441.0,
            "track_id": 2,
            "lineage_id": 1,
            "solution": True,
        },
        {
            "t": 1,
            "pos": [60.0, 45.0],
            "area": 961.0,
            "track_id": 3,
            "lineage_id": 1,
            "solution": True,
        },
        {
            "t": 2,
            "pos": [1.5, 1.5],
            "area": 16.0,
            "track_id": 3,
            "lineage_id": 1,
            "solution": True,
        },
        {
            "t": 4,
            "pos": [1.5, 1.5],
            "area": 16.0,
            "track_id": 3,
            "lineage_id": 1,
            "solution": True,
        },
        {
            "t": 4,
            "pos": [97.5, 97.5],
            "area": 16.0,
            "track_id": 5,
            "lineage_id": 2,
            "solution": True,
        },
    ]
    for node, bbox in zip(nodes, bboxes, strict=True):
        node[td.DEFAULT_ATTR_KEYS.MASK] = _make_mask(bbox)
        node[td.DEFAULT_ATTR_KEYS.BBOX] = np.array(bbox, dtype=np.int64)
    graph.bulk_add_nodes(nodes=nodes, indices=[1, 2, 3, 4, 5, 6])
    graph.bulk_add_edges(
        [
            {"source_id": 1, "target_id": 2, "iou": 0.0, "solution": True},
            {"source_id": 1, "target_id": 3, "iou": 0.395, "solution": True},
            {"source_id": 3, "target_id": 4, "iou": 0.0, "solution": True},
            {"source_id": 4, "target_id": 5, "iou": 1.0, "solution": True},
        ]
    )
    graph._update_metadata(shape=(5, 100, 100))
    return graph


@pytest.fixture
def graph_3d() -> td.graph.GraphView:
    """3D+time graph (ndim=4) with 3 nodes and a division.

    Nodes include mask/bbox attributes (frame shape 100x100x100, 2 timepoints).
    """
    graph = create_empty_graphview_graph(
        node_attributes=["pos", td.DEFAULT_ATTR_KEYS.MASK, td.DEFAULT_ATTR_KEYS.BBOX],
        ndim=4,
    )
    # bboxes: [z0, y0, x0, z1, y1, x1]
    bboxes = [
        [30, 30, 30, 71, 71, 71],  # node 1, t=0: sphere center=(50,50,50) r=20
        [10, 40, 70, 31, 61, 91],  # node 2, t=1: sphere center=(20,50,80) r=10
        [45, 35, 30, 76, 66, 61],  # node 3, t=1: sphere center=(60,50,45) r=15
    ]
    nodes = [
        {"t": 0, "pos": [50.0, 50.0, 50.0], "solution": True},
        {"t": 1, "pos": [20.0, 50.0, 80.0], "solution": True},
        {"t": 1, "pos": [60.0, 50.0, 45.0], "solution": True},
    ]
    for node, bbox in zip(nodes, bboxes, strict=True):
        node[td.DEFAULT_ATTR_KEYS.MASK] = _make_mask(bbox)
        node[td.DEFAULT_ATTR_KEYS.BBOX] = np.array(bbox, dtype=np.int64)
    graph.bulk_add_nodes(nodes=nodes, indices=[1, 2, 3])
    graph.bulk_add_edges(
        [
            {"source_id": 1, "target_id": 2, "solution": True},
            {"source_id": 1, "target_id": 3, "solution": True},
        ]
    )
    graph._update_metadata(shape=(2, 100, 100, 100))
    return graph


@pytest.fixture
def graph_3d_without_segmentation(graph_3d: td.graph.GraphView) -> td.graph.GraphView:
    """Return a copy of graph_3d without segmentation-related node attributes."""
    graph_without_seg = graph_3d.detach().filter().subgraph()
    graph_without_seg.remove_node_attr_key(td.DEFAULT_ATTR_KEYS.MASK)
    graph_without_seg.remove_node_attr_key(td.DEFAULT_ATTR_KEYS.BBOX)
    return graph_without_seg


@pytest.fixture
def graph_2d_without_segmentation(graph_2d: td.graph.GraphView) -> td.graph.GraphView:
    """Return a copy of graph_2d without segmentation-related node attributes."""
    graph_without_seg = graph_2d.detach().filter().subgraph()
    graph_without_seg.remove_node_attr_key(td.DEFAULT_ATTR_KEYS.MASK)
    graph_without_seg.remove_node_attr_key(td.DEFAULT_ATTR_KEYS.BBOX)
    graph_without_seg.remove_edge_attr_key("iou")
    return graph_without_seg


@pytest.fixture
def graph_3d_with_division() -> td.graph.GraphView:
    """3D+time graph (ndim=4) with 4 nodes and a division event (node 2 splits into 3 and 4).

    Nodes include mask/bbox attributes (frame shape 100x100x100, 5 timepoints).
    """
    graph = create_empty_graphview_graph(
        node_attributes=[
            "pos",
            "area",
            td.DEFAULT_ATTR_KEYS.MASK,
            td.DEFAULT_ATTR_KEYS.BBOX,
        ],
        ndim=4,
    )
    bboxes = [
        [45, 45, 45, 55, 55, 55],  # node 1, t=0
        [15, 45, 75, 25, 55, 85],  # node 2, t=1
        [55, 45, 40, 65, 55, 50],  # node 3, t=2
        [35, 65, 55, 45, 75, 65],  # node 4, t=2
    ]
    graph.bulk_add_nodes(
        nodes=[
            {
                "t": 0,
                "pos": [50.0, 50.0, 50.0],
                "area": 1000.0,
                td.DEFAULT_ATTR_KEYS.MASK: _make_mask(bboxes[0]),
                td.DEFAULT_ATTR_KEYS.BBOX: np.array(bboxes[0], dtype=np.int64),
                "solution": True,
            },
            {
                "t": 1,
                "pos": [20.0, 50.0, 80.0],
                "area": 1000.0,
                td.DEFAULT_ATTR_KEYS.MASK: _make_mask(bboxes[1]),
                td.DEFAULT_ATTR_KEYS.BBOX: np.array(bboxes[1], dtype=np.int64),
                "solution": True,
            },
            {
                "t": 2,
                "pos": [60.0, 50.0, 45.0],
                "area": 1000.0,
                td.DEFAULT_ATTR_KEYS.MASK: _make_mask(bboxes[2]),
                td.DEFAULT_ATTR_KEYS.BBOX: np.array(bboxes[2], dtype=np.int64),
                "solution": True,
            },
            {
                "t": 2,
                "pos": [40.0, 70.0, 60.0],
                "area": 1000.0,
                td.DEFAULT_ATTR_KEYS.MASK: _make_mask(bboxes[3]),
                td.DEFAULT_ATTR_KEYS.BBOX: np.array(bboxes[3], dtype=np.int64),
                "solution": True,
            },
        ],
        indices=[1, 2, 3, 4],
    )
    graph.bulk_add_edges(
        [
            {"source_id": 1, "target_id": 2, "solution": True},
            {"source_id": 2, "target_id": 3, "solution": True},
            {"source_id": 2, "target_id": 4, "solution": True},
        ]
    )
    graph._update_metadata(shape=(5, 100, 100, 100))
    return graph


@pytest.fixture
def solution_tracks_2d(graph_2d) -> SolutionTracks:
    """Return a SolutionTracks object wrapping graph_2d."""
    return SolutionTracks(graph=graph_2d, ndim=3, time_attr="t")


@pytest.fixture
def solution_tracks_3d(graph_3d) -> SolutionTracks:
    """Return a SolutionTracks object wrapping graph_3d."""
    return SolutionTracks(graph=graph_3d, ndim=4, time_attr="t")


@pytest.fixture
def solution_tracks_3d_with_division(graph_3d_with_division) -> SolutionTracks:
    """Return a SolutionTracks object wrapping graph_3d_with_division."""
    return SolutionTracks(graph=graph_3d_with_division, ndim=4, time_attr="t")


@pytest.fixture
def solution_tracks_2d_without_segmentation(
    graph_2d_without_segmentation,
) -> SolutionTracks:
    """Return a SolutionTracks object wrapping graph_2d_without_segmentation."""
    return SolutionTracks(graph=graph_2d_without_segmentation, ndim=3, time_attr="t")


@pytest.fixture
def solution_tracks_3d_without_segmentation(
    graph_3d_without_segmentation,
) -> SolutionTracks:
    """Return a SolutionTracks object wrapping graph_3d_without_segmentation."""
    return SolutionTracks(graph=graph_3d_without_segmentation, ndim=4, time_attr="t")


@pytest.fixture
def segmentation_2d(graph_2d):
    return np.asarray(Tracks(graph_2d, ndim=3, time_attr="t").segmentation)


@pytest.fixture
def segmentation_3d(graph_3d):
    return np.asarray(Tracks(graph_3d, ndim=4, time_attr="t").segmentation)
