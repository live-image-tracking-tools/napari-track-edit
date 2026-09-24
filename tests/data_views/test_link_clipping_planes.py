import numpy as np
import pytest
from napari.layers import Image, Labels, Points
from napari.layers.utils._link_layers import layer_is_linked
from napari.layers.utils.plane import ClippingPlane

from napari_track_edit.data_views.views.layers.tracks_layer_group import (
    TracksLayerGroup,
)


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.mark.xfail(reason="Open issue on linking clipping planes in napari")
def test_link_experimental_clipping_planes(viewer):
    """Test if the clipping planes in the TracksLayersGroup are correctly linked by changing the position and emitting events"""

    layer1 = Image(np.random.rand(10, 15, 20))
    label_data = np.zeros((10, 10, 10), dtype=np.uint8)
    label_data[2:5, 2:5, 2:5] = 1
    layer2 = Labels(label_data)
    layer3 = Points(data=np.array([[1, 2, 3], [4, 5, 6]]))

    # Step 2: Create a TracksLayerGroup and set the layers
    tracks_layer_group = TracksLayerGroup(viewer, None, "test", None)
    tracks_layer_group.tracks_layer = layer1
    tracks_layer_group.seg_layer = layer2
    tracks_layer_group.points_layer = layer3

    # Verify layers are not linked
    assert not layer_is_linked(layer1)
    assert not layer_is_linked(layer2)
    assert not layer_is_linked(layer3)

    # linke layers
    tracks_layer_group.link_experimental_clipping_planes()

    # Verify that the layers are linked
    assert layer_is_linked(layer1)
    assert layer_is_linked(layer2)
    assert layer_is_linked(layer3)

    # initiate clipping planes
    layer1.experimental_clipping_planes.append(
        ClippingPlane(
            normal=(np.float64(1.0), np.float64(0.0), np.float64(0.0)),
            position=(0.0, 0.0, 0.0),
            enabled=False,
        )
    )
    layer1.experimental_clipping_planes.append(
        ClippingPlane(
            normal=[-n for n in layer1.experimental_clipping_planes[0].normal],
            position=(0.0, 0.0, 0.0),
            enabled=False,
        )
    )

    layer2.experimental_clipping_planes.append(
        ClippingPlane(
            normal=(np.float64(1.0), np.float64(0.0), np.float64(0.0)),
            position=(0.0, 0.0, 0.0),
            enabled=False,
        )
    )
    layer2.experimental_clipping_planes.append(
        ClippingPlane(
            normal=[-n for n in layer1.experimental_clipping_planes[0].normal],
            position=(0.0, 0.0, 0.0),
            enabled=False,
        )
    )

    layer3.experimental_clipping_planes.append(
        ClippingPlane(
            normal=(np.float64(1.0), np.float64(0.0), np.float64(0.0)),
            position=(0.0, 0.0, 0.0),
            enabled=False,
        )
    )
    layer3.experimental_clipping_planes.append(
        ClippingPlane(
            normal=[-n for n in layer1.experimental_clipping_planes[0].normal],
            position=(0.0, 0.0, 0.0),
            enabled=False,
        )
    )

    # change the position of the clipping plane in layer1 and verify that it is reflected in layer2 and layer3
    plane_normal = np.array(layer1.experimental_clipping_planes[0].normal)
    layer1.experimental_clipping_planes[0].position = tuple(
        np.array([0, 0, 0]) + 2 * plane_normal
    )

    assert layer1.experimental_clipping_planes != layer2.experimental_clipping_planes
    layer1.events.experimental_clipping_planes()  # Simulate event emission
    assert (
        layer1.experimental_clipping_planes
        == layer2.experimental_clipping_planes
        == layer3.experimental_clipping_planes
    )

    # verify that enabling the clipping plane in one layer is reflected in the others
    layer1.experimental_clipping_planes[0].enabled = True
    assert (
        layer1.experimental_clipping_planes[0].enabled
        != layer2.experimental_clipping_planes[0].enabled
    )
    layer1.events.experimental_clipping_planes()  # Simulate event emission
    assert (
        layer1.experimental_clipping_planes[0].enabled
        == layer2.experimental_clipping_planes[0].enabled
        == layer3.experimental_clipping_planes[0].enabled
    )

    tracks_layer_group.unlink_experimental_clipping_planes()
    # Verify layers are not linked anymore
    assert not layer_is_linked(layer1)
    assert not layer_is_linked(layer2)
    assert not layer_is_linked(layer3)
