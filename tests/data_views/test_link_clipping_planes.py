import pytest
from napari.layers.utils._link_layers import get_linked_layers, layer_is_linked
from napari.layers.utils.plane import ClippingPlane

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.fixture
def tracking_layers(viewer, solution_tracks_3d):
    """The three tracking layers of a 3D dataset, already added to the viewer"""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d, name="test")
    layers = tracks_viewer.tracking_layers

    assert layers.seg_layer is not None
    assert layers.points_layer is not None
    assert layers.tracks_layer is not None

    return layers


def _add_clipping_planes(layer, normal=(1.0, 0.0, 0.0)):
    """Give a layer the pair of clipping planes the plane sliders operate on"""

    layer.experimental_clipping_planes = [
        ClippingPlane(normal=normal, position=(0.0, 0.0, 0.0), enabled=False),
        ClippingPlane(
            normal=tuple(-n for n in normal),
            position=(0.0, 0.0, 0.0),
            enabled=False,
        ),
    ]


def test_tracking_layers_are_linked_on_their_clipping_planes(tracking_layers):
    """Adding the tracking layers puts them in one link group"""

    for layer in tracking_layers.track_layers:
        assert layer_is_linked(layer)

    assert get_linked_layers(tracking_layers.points_layer) == {
        tracking_layers.seg_layer,
        tracking_layers.tracks_layer,
    }


def test_moving_a_clipping_plane_propagates(tracking_layers):
    """Moving one plane of one layer moves the same plane on the other layers"""

    seg = tracking_layers.seg_layer
    points = tracking_layers.points_layer
    tracks = tracking_layers.tracks_layer
    _add_clipping_planes(seg)

    assert len(points.experimental_clipping_planes) == 2
    assert len(tracks.experimental_clipping_planes) == 2

    seg.experimental_clipping_planes[0].position = (2.0, 0.0, 0.0)

    assert points.experimental_clipping_planes[0].position == (2.0, 0.0, 0.0)
    assert tracks.experimental_clipping_planes[0].position == (2.0, 0.0, 0.0)

    seg.experimental_clipping_planes[0].enabled = True

    assert points.experimental_clipping_planes[0].enabled
    assert tracks.experimental_clipping_planes[0].enabled


def test_clipping_planes_propagate_in_both_directions(tracking_layers):
    """A change on the points layer reaches the segmentation just as well"""

    seg = tracking_layers.seg_layer
    points = tracking_layers.points_layer
    _add_clipping_planes(seg)

    points.experimental_clipping_planes[1].position = (7.0, 0.0, 0.0)

    assert seg.experimental_clipping_planes[1].position == (7.0, 0.0, 0.0)


def test_other_attributes_are_not_linked(tracking_layers):
    """Only the clipping planes are shared, the layers stay independent otherwise"""

    seg = tracking_layers.seg_layer
    points = tracking_layers.points_layer

    seg.visible = False
    seg.opacity = 0.1

    assert points.visible
    assert points.opacity != pytest.approx(0.1)


def test_a_layer_showing_a_plane_ignores_linked_clipping_planes(tracking_layers):
    """The slab that mimics plane mode on the points must not clip the segmentation

    The plane sliders clip the layers without a plane of their own to a slab around the
    plane of the segmentation. That slab is theirs alone: taking it over would clip the
    layer that defines the plane.
    """

    seg = tracking_layers.seg_layer
    points = tracking_layers.points_layer
    _add_clipping_planes(seg)
    seg.depiction = "plane"

    points.experimental_clipping_planes[0].position = (4.0, 0.0, 0.0)
    points.experimental_clipping_planes[0].enabled = True

    assert seg.experimental_clipping_planes[0].position == (0.0, 0.0, 0.0)
    assert not seg.experimental_clipping_planes[0].enabled


def test_unlink_experimental_clipping_planes(tracking_layers):
    """Unlinking stops the layers from following each other"""

    seg = tracking_layers.seg_layer
    points = tracking_layers.points_layer
    _add_clipping_planes(seg)

    tracking_layers.unlink_experimental_clipping_planes()

    for layer in tracking_layers.track_layers:
        assert not layer_is_linked(layer)

    seg.experimental_clipping_planes[0].position = (3.0, 0.0, 0.0)

    assert points.experimental_clipping_planes[0].position == (0.0, 0.0, 0.0)


def test_layers_without_segmentation_are_linked(
    viewer, solution_tracks_3d_without_segmentation
):
    """Without a segmentation, the points and tracks layers are still linked"""

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(
        tracks=solution_tracks_3d_without_segmentation, name="test"
    )
    layers = tracks_viewer.tracking_layers

    assert layers.seg_layer is None
    assert get_linked_layers(layers.points_layer) == {layers.tracks_layer}


def test_2d_layers_are_linked_over_their_three_dimensions(viewer, solution_tracks_2d):
    """2D tracking layers have three dimensions (t, y, x), so they are linked as well

    Clipping planes need three dimensions to act on, which is all the guard in
    `link_experimental_clipping_planes` asks for.
    """

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")
    layers = tracks_viewer.tracking_layers

    assert all(layer.ndim == 3 for layer in layers.track_layers)
    for layer in layers.track_layers:
        assert layer_is_linked(layer)
