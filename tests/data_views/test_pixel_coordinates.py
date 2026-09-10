"""Positions are stored in pixels and displayed in world units.

funtracks keeps node positions in pixel coordinates and carries the voxel size
in ``tracks.scale``. Everything the user sees - the napari canvas, the tree plot
and the table view - is in world units, so each consumer has to apply that scale
itself. These tests pin down that split for an anisotropic scale.
"""

import napari
import numpy as np
import pytest
from funtracks.data_model import Tracks

from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_sorted_tracks,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

SCALE = [1.0, 2.0, 5.0]  # t, y, x


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


def _tracks(graph_2d) -> Tracks:
    return Tracks(graph=graph_2d, ndim=3, time_attr="t", scale=SCALE)


def test_layers_carry_the_scale_and_keep_pixel_data(viewer, graph_2d):
    """The tracking layers hold pixel data plus tracks.scale, like the seg layer."""
    tracks = _tracks(graph_2d)

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=tracks, name="test")
    layers = tracks_viewer.tracking_layers

    for layer in (layers.points_layer, layers.tracks_layer, layers.seg_layer):
        np.testing.assert_allclose(layer.scale, SCALE)

    # The points layer data is the unscaled graph position, and napari turns it
    # into the world coordinate the user sees.
    nodes = layers.points_layer.nodes
    np.testing.assert_allclose(
        layers.points_layer.data, tracks.get_positions(nodes, incl_time=True)
    )
    world = layers.points_layer.data_to_world(layers.points_layer.data[0])
    np.testing.assert_allclose(world, layers.points_layer.data[0] * np.array(SCALE))


def test_tree_dataframe_holds_world_positions(graph_2d):
    """The tree plot and table view show positions in world units."""
    tracks = _tracks(graph_2d)
    colormap = napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)

    df, _ = extract_sorted_tracks(tracks, colormap)

    node_ids = df["node_id"].to_list()
    pixel_pos = tracks.get_positions(node_ids)
    np.testing.assert_allclose(df["y"].to_numpy(), pixel_pos[:, 0] * SCALE[1])
    np.testing.assert_allclose(df["x"].to_numpy(), pixel_pos[:, 1] * SCALE[2])

    # Only the position is converted: the bounding box indexes the segmentation
    # and stays in pixels.
    np.testing.assert_allclose(
        df["Bounding box_0"].to_numpy(),
        [tracks.get_node_attr(node, "bbox")[0] for node in node_ids],
    )


def test_tree_dataframe_unscaled_without_scale(graph_2d):
    """Without a scale the displayed positions are the stored ones."""
    tracks = Tracks(graph=graph_2d, ndim=3, time_attr="t")
    colormap = napari.utils.colormaps.label_colormap(49, seed=0.5, background_value=0)

    df, _ = extract_sorted_tracks(tracks, colormap)

    pixel_pos = tracks.get_positions(df["node_id"].to_list())
    np.testing.assert_allclose(df["y"].to_numpy(), pixel_pos[:, 0])
    np.testing.assert_allclose(df["x"].to_numpy(), pixel_pos[:, 1])
