import collections
import math

import numpy as np
import pytest
from napari.utils.key_bindings import coerce_keybinding
from napari_orthogonal_views.ortho_view_widget import OrthoViewWidget

from napari_track_edit.data_views.views.layers.contour_labels import ContourLabels
from napari_track_edit.data_views.views.layers.out_of_slice_points import ZOnlyPoints
from napari_track_edit.data_views.views.layers.track_labels import TrackLabels
from napari_track_edit.data_views.views.layers.track_points import TrackPoints
from napari_track_edit.data_views.views.ortho_views import (
    initialize_ortho_views,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


class MockEvent:
    def __init__(self, value):
        self.value = value


def test_ortho_views(viewer, qtbot, solution_tracks_3d_with_division):
    """Test if the tracks layers are correctly displayed on the orthoviews"""

    # Initalize orthogonal views
    m = initialize_ortho_views(viewer)

    # Create example tracks
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    assert isinstance(viewer.layers[-1], TrackLabels)
    assert isinstance(viewer.layers[-2], TrackPoints)

    # change attributes on the TrackLabels layer to check that they are correctly copied
    viewer.layers[-1].contour = 1
    viewer.layers[-1].mode = "erase"

    # show orthogonal views and check attributes
    m.show()
    qtbot.waitUntil(lambda: m.is_shown(), timeout=1000)
    assert isinstance(m.right_widget, OrthoViewWidget)
    assert isinstance(
        m.right_widget.vm_container.viewer_model.layers[-1], ContourLabels
    )
    assert isinstance(
        m.bottom_widget.vm_container.viewer_model.layers[-1], ContourLabels
    )
    assert isinstance(m.right_widget.vm_container.viewer_model.layers[-2], ZOnlyPoints)
    assert isinstance(m.bottom_widget.vm_container.viewer_model.layers[-2], ZOnlyPoints)

    # the copies get the shared key bindings, so [M] starts a new track from them too
    for copy in (
        m.right_widget.vm_container.viewer_model.layers[-1],
        m.bottom_widget.vm_container.viewer_model.layers[-1],
        m.right_widget.vm_container.viewer_model.layers[-2],
        m.bottom_widget.vm_container.viewer_model.layers[-2],
    ):
        assert copy.keymap[coerce_keybinding("m")] == tracks_viewer.request_new_track
    assert (
        m.right_widget.vm_container.viewer_model.layers[-1].contour
        == viewer.layers[-1].contour
    )
    assert (
        m.right_widget.vm_container.viewer_model.layers[-1].mode
        == viewer.layers[-1].mode
    )

    # set to paint mode and test syncing
    viewer.layers[-1].mode = "paint"
    assert (
        viewer.layers[-1].mode
        == m.right_widget.vm_container.viewer_model.layers[-1].mode
        == m.bottom_widget.vm_container.viewer_model.layers[-1].mode
    )

    # Test paint event on main viewer (indices, orig value, target_value)
    event_val = [
        (
            (np.array([1]), np.array([15]), np.array([45]), np.array([75])),
            np.array([2], dtype=np.uint16),
            np.uint16(5),
        )
    ]
    event = MockEvent(event_val)
    step = list(viewer.dims.current_step)
    step[0] = 1
    viewer.dims.current_step = step
    viewer.layers[-1]._on_paint(event)

    assert int(np.asarray(viewer.layers[-1].data[1, 15, 45, 75])) == 5
    assert np.array_equal(
        np.asarray(viewer.layers[-1].data),
        np.asarray(m.right_widget.vm_container.viewer_model.layers[-1].data),
    )

    # test paint event on one of the ortho views and see if a new node is added
    assert tracks_viewer.tracks.graph_solution.num_nodes() == 5
    step = list(viewer.dims.current_step)
    step[0] = 2
    viewer.dims.current_step = step
    m.right_widget.vm_container.viewer_model.layers[-1].paint(
        coord=(2, 63, 20, 30), new_label=6, refresh=True
    )
    assert tracks_viewer.tracks.graph_solution.num_nodes() == 6

    # test syncing of properties
    viewer.layers[-1].selected_label = 7  # forward sync only
    assert (
        viewer.layers[-1].selected_label
        == m.right_widget.vm_container.viewer_model.layers[-1].selected_label
        == m.bottom_widget.vm_container.viewer_model.layers[-1].selected_label
    )

    m.cleanup()


def n_slots(signal):
    """Number of callbacks on a napari EventEmitter or a psygnal SignalInstance."""

    callbacks = getattr(signal, "callbacks", None)
    return len(callbacks) if callbacks is not None else len(signal)


def assert_same_colors(copied_layer, orig_layer, tag):
    """Assert that both layers show every label in exactly the same color."""

    copied_colors = copied_layer.colormap.color_dict
    orig_colors = orig_layer.colormap.color_dict
    assert copied_colors.keys() == orig_colors.keys(), f"{tag}: different labels"
    for label, color in orig_colors.items():
        assert np.allclose(copied_colors[label], color), f"{tag}: label {label} differs"


def test_colormap_shared_with_ortho_views(
    viewer, qtbot, solution_tracks_3d_with_division
):
    """The copied layers show the same colors as the original, and share its colormap.

    Building a DirectLabelColormap validates every color again, which is expensive for
    a large graph and happened per view on every colormap event. The copies only need a
    colormap of their own when their background opacity differs from the original's,
    which is the 3D + contours case.
    """

    m = initialize_ortho_views(viewer)
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")
    m.show()
    qtbot.waitUntil(lambda: m.is_shown(), timeout=1000)

    seg_layer = tracks_viewer.tracking_layers.seg_layer
    copies = [
        widget.vm_container.viewer_model.layers[seg_layer.name]
        for widget in (m.right_widget, m.bottom_widget)
    ]
    nodes = tracks_viewer.tracks.graph_solution.node_ids()

    def check_shared(tag):
        for copied_layer in copies:
            assert_same_colors(copied_layer, seg_layer, tag)
            assert copied_layer.colormap is seg_layer.colormap, f"{tag}: not shared"

    check_shared("initial")

    tracks_viewer.selected_nodes.add(nodes[0], False)
    check_shared("after node selection")

    tracks_viewer.set_display_mode("lineage")
    check_shared("after switching to lineage mode")

    seg_layer.contour = 1
    check_shared("after enabling contours")

    seg_layer.new_label()  # adds a label, so a new entry in the color dict
    check_shared("after a new label")

    # Rendering the main viewer in 3D with contours on is the one case where the copies
    # need their own colormap: contours are not rendered in 3D, so the original hides its
    # background labels while the (2D) copies must keep showing them.
    viewer.dims.ndisplay = 3
    tracks_viewer.selected_nodes.add(nodes[1], False)
    background_label = next(
        label for label in seg_layer.background if label not in (None, 0)
    )
    for copied_layer in copies:
        assert copied_layer.colormap is not seg_layer.colormap
        assert seg_layer.colormap.color_dict[background_label][3] == 0
        assert (
            copied_layer.colormap.color_dict[background_label][3]
            == seg_layer.background_opacity
        )
        # the colors themselves must still match
        for label, color in seg_layer.colormap.color_dict.items():
            assert np.allclose(copied_layer.colormap.color_dict[label][:3], color[:3])

    # and back to sharing once the main viewer is 2D again
    viewer.dims.ndisplay = 2
    tracks_viewer.selected_nodes.add(nodes[0], False)
    check_shared("back in 2D")

    m.cleanup()


def test_point_outline_updates_ortho_views_once(
    viewer, qtbot, solution_tracks_3d_with_division
):
    """Updating the point outline must emit a single border color event.

    The orthogonal views re-slice their copy of the points layer whenever the border
    color changes (napari's size setter is silent, which is why the views listen to the
    border color), so emitting the same state twice doubles that work per view.
    """

    m = initialize_ortho_views(viewer)
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")
    m.show()
    qtbot.waitUntil(lambda: m.is_shown(), timeout=1000)

    points_layer = tracks_viewer.tracking_layers.points_layer
    copies = [
        widget.vm_container.viewer_model.layers[points_layer.name]
        for widget in (m.right_widget, m.bottom_widget)
    ]

    emitted = collections.Counter()
    points_layer.events.border_color.connect(
        lambda event: emitted.update(["border_color"])
    )

    node = tracks_viewer.tracks.graph_solution.node_ids()[1]
    tracks_viewer.selected_nodes.add(node, False)
    assert emitted["border_color"] == 1, emitted

    # the selected point is highlighted and enlarged, and the copies follow
    index = points_layer.node_index_dict[node]
    assert np.allclose(points_layer.border_color[index], (0, 1, 1, 1))
    assert points_layer.size[index] == math.ceil(1.3 * points_layer.default_size)
    for copied_layer in copies:
        assert np.array_equal(copied_layer.size, points_layer.size)
        assert np.array_equal(copied_layer.shown, points_layer.shown)

    # hiding all but one node must reach the copies as well
    points_layer.update_point_outline([int(node)])
    assert points_layer.shown.sum() == 1
    for copied_layer in copies:
        assert np.array_equal(copied_layer.shown, points_layer.shown)

    points_layer.update_point_outline("all")
    assert points_layer.shown.all()
    for copied_layer in copies:
        assert np.array_equal(copied_layer.shown, points_layer.shown)

    m.cleanup()


def test_hook_connections_released_on_hide(
    viewer, qtbot, solution_tracks_3d_with_division
):
    """The hooks connect to the *original* layers but close over the copied layers, so
    hiding the orthogonal views has to disconnect them again.

    If they survive, every hide/show cycle adds another handler that rebuilds the
    colormap of / re-slices a copied layer nobody sees anymore, which makes every
    selection and every paint permanently slower.
    """

    m = initialize_ortho_views(viewer)
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")

    seg_layer = tracks_viewer.tracking_layers.seg_layer
    points_layer = tracks_viewer.tracking_layers.points_layer

    def hook_slot_counts():
        return (
            n_slots(seg_layer.events.colormap),  # colormap_hook
            n_slots(points_layer.events.border_color),  # point_data_hook
            n_slots(points_layer.data_updated),  # point_data_hook
            n_slots(seg_layer.events.paint),  # paint_event_hook + container
        )

    baseline = hook_slot_counts()

    for _ in range(3):
        m.show()
        qtbot.waitUntil(lambda: m.is_shown(), timeout=1000)
        assert hook_slot_counts() > baseline  # connected while shown

        m.hide()
        assert hook_slot_counts() == baseline  # and released again

    m.cleanup()


def test_point_size_stable_when_editing_in_ortho_views(
    viewer, qtbot, solution_tracks_3d_without_segmentation, monkeypatch
):
    """Adding or selecting points in an orthogonal view must not change the point size.

    Selected points are drawn 30% larger, and napari copies the size of a selected point
    into current_size, which TrackPoints reads as a size slider change. Every add or
    selection made in an orthogonal view therefore used to grow the points by another
    30% (5 -> 7 -> 10 -> 13 -> ...).
    """

    monkeypatch.setattr(
        "napari_track_edit.data_views.views.layers.track_points.confirm_force_operation",
        lambda message: (True, False),
    )

    m = initialize_ortho_views(viewer)
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(
        tracks=solution_tracks_3d_without_segmentation, name="test"
    )
    m.show()
    qtbot.waitUntil(lambda: m.is_shown(), timeout=1000)

    points_layer = tracks_viewer.tracking_layers.points_layer
    right = m.right_widget.vm_container.viewer_model.layers[points_layer.name]
    bottom = m.bottom_widget.vm_container.viewer_model.layers[points_layer.name]
    default_size = points_layer.default_size

    # adding points in an orthogonal view
    for i in range(4):
        right.add(np.array([0, 20, 55 + i, 65 + i], dtype=float))
        assert points_layer.default_size == default_size

    # selecting points, in an orthogonal view and in the main viewer
    for index in range(3):
        bottom.selected_data = {index}
    assert points_layer.default_size == default_size
    for node in tracks_viewer.tracks.graph_solution.node_ids()[:3]:
        tracks_viewer.selected_nodes.add(node, False)
    assert points_layer.default_size == default_size

    # a real size change still works, and reaches the orthogonal views
    points_layer.current_size = default_size + 3
    assert points_layer.default_size == default_size + 3
    for copied_layer in (right, bottom):
        assert np.array_equal(copied_layer.size, points_layer.size)

    m.cleanup()
