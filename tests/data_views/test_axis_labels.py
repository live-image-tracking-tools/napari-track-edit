import numpy as np
import tracksdata as td
from funtracks.data_model import SolutionTracks
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from tracksdata.nodes._mask import Mask

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


class TestAxisLabels:
    """The tracks name the sliders they own.

    napari shows dims.axis_labels on the dim sliders, and they are indexed by world
    axis, so the tracks' names go on the trailing axes they occupy and any extra
    leading axis keeps its own label.
    """

    def _tracks_3d(self, tmp_path):
        graph = _make_single_node_graph(
            tmp_path,
            pos=[5, 10, 10],
            seg_bbox=[4, 9, 9, 6, 11, 11],
            seg_shape=(2, 20, 20, 20),
        )
        return SolutionTracks(
            graph=graph, scale=[1.0, 1.0, 1.0, 1.0], ndim=4, time_attr="t"
        )

    def test_tracks_name_their_own_axes_only(self, viewer, tmp_path):
        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=self._tracks_3d(tmp_path), name="test")

        assert tuple(viewer.dims.axis_labels) == ("t", "z", "y", "x")

        # a channel layer arriving later widens the viewer; napari prepends, so the
        # names stay on the tracks' own axes and the new one keeps its own label
        viewer.add_image(np.zeros((3, 2, 20, 20, 20), dtype=np.uint8), name="chan")
        viewer.dims.set_axis_label(0, "channel")

        dims = tracks_viewer.tracks_dims
        labels = viewer.dims.axis_labels
        assert tuple(labels) == ("channel", "t", "z", "y", "x")
        # the labelling and the axis map agree, or a slider would say one thing
        # while centering did another
        assert labels[dims.time_axis] == "t"
        assert tuple(labels[axis] for axis in dims.spatial_axes) == ("z", "y", "x")

    def test_2d_tracks_are_labelled_without_a_z(self, viewer, tmp_path):
        """The old hardcoded suffix gave 2D+time tracks ('z','y','x'), naming the
        time axis 'z'."""

        graph = create_empty_graphview_graph(
            node_attributes=["pos", "area"],
            ndim=3,
            database=str(tmp_path / "graph2d.db"),
        )
        graph.bulk_add_nodes(
            nodes=[{"t": 0, "pos": [10, 10], "area": 100.0, "solution": True}],
            indices=[1],
        )
        tracks = SolutionTracks(
            graph=graph, scale=[1.0, 1.0, 1.0], ndim=3, time_attr="t"
        )

        tracks_viewer = TracksViewer.get_instance(viewer)
        tracks_viewer.update_tracks(tracks=tracks, name="test")

        assert tuple(viewer.dims.axis_labels) == ("t", "y", "x")
