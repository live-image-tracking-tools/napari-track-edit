"""Tests for CopyFromSourceWidget - copying detections from a source layer into the
current tracks."""

import contextlib

import numpy as np
import pytest
from napari.layers import Labels, Points

from motile_tracker.application_menus.copy_from_source_widget import (
    CopyFromSourceWidget,
)
from motile_tracker.application_menus.editing_selection_menu import (
    EditingSelectionWidget,
)
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views.layers.track_points import TrackPoints
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


def _source_labels(shape=(5, 100, 100)) -> np.ndarray:
    """Segmentation with one 4x4 label per frame, a different value in each frame, in a
    corner that the graph_2d fixture does not occupy."""

    data = np.zeros(shape, dtype=np.uint16)
    for t in range(shape[0]):
        data[t, 50:54, 10:14] = t + 1
    return data


def _source_points(n_frames=5) -> np.ndarray:
    return np.array([[t, 30.0, 40.0] for t in range(n_frames)])


class _RightClickEvent:
    """Minimal stand-in for a napari right-click mouse event."""

    def __init__(self, position):
        self.type = "mouse_press"
        self.button = 2
        self.position = position
        self.view_direction = None
        self.dims_displayed = [1, 2]


def _drive_callbacks(layer, event):
    """Run every mouse_drag_callback of a layer, driving generator callbacks the way
    napari does."""

    for callback in list(layer.mouse_drag_callbacks):
        result = callback(layer, event)
        if hasattr(result, "__next__"):
            with contextlib.suppress(StopIteration):
                while True:
                    next(result)


@pytest.fixture
def labels_app(make_napari_viewer, solution_tracks_2d):
    """A viewer with segmentation-backed tracks, a Labels source layer and the widget."""

    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")
    source = viewer.add_labels(_source_labels(), name="src")
    widget = CopyFromSourceWidget(viewer)
    return viewer, widget, source


def _multichannel_source_labels(shape=(5, 100, 100)) -> np.ndarray:
    """Two alternative segmentations of the same objects, stacked on a channel axis.

    Channel 0 holds a small 4x4 mask per frame, channel 1 a bigger 8x8 one covering
    it, so which channel a copy came from can be told from the copied pixel count.
    """

    data = np.zeros((2, *shape), dtype=np.uint16)
    for t in range(shape[0]):
        data[0, t, 50:54, 10:14] = t + 1
        data[1, t, 50:58, 10:18] = t + 1
    return data


@pytest.fixture
def multichannel_labels_app(make_napari_viewer, solution_tracks_2d):
    """A viewer with tracks and a Labels source carrying an extra channel axis."""

    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")
    source = viewer.add_labels(_multichannel_source_labels(), name="src")
    widget = CopyFromSourceWidget(viewer)
    return viewer, widget, source


@pytest.fixture
def points_app(make_napari_viewer, solution_tracks_2d_without_segmentation):
    """A viewer with points-only tracks, a Points source layer and the widget."""

    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(
        tracks=solution_tracks_2d_without_segmentation, name="test"
    )
    source = viewer.add_points(_source_points(), name="src_pts")
    widget = CopyFromSourceWidget(viewer)
    return viewer, widget, source


def test_source_dropdown_follows_mode(labels_app, points_app):
    """The source dropdown offers Labels for a segmentation-backed tree and Points
    for a points-only tree, in both cases excluding the track layers themselves."""

    _viewer, labels_widget, _source = labels_app
    assert labels_widget._mode == "labels"
    assert labels_widget.source_layer_dropdown.layer_types == (Labels,)
    assert labels_widget.source_layer_dropdown.exclude_types == (TrackLabels,)

    _viewer, points_widget, _source = points_app
    assert points_widget._mode == "points"
    assert points_widget.source_layer_dropdown.layer_types == (Points,)
    assert points_widget.source_layer_dropdown.exclude_types == (TrackPoints,)


def test_chain_toggle_connects_and_disconnects(labels_app):
    """Toggling the chain button attaches the copy callback to the target track layer
    (not to the source layer) and detaches it again."""

    viewer, widget, source = labels_app

    assert widget.chain_btn.isEnabled()
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)

    target = widget._get_target_layer()
    assert widget._source_layer is source
    assert widget._target_layer is target
    assert widget._target_callback in target.mouse_drag_callbacks
    assert hasattr(target, "_manual_copy_detection")
    assert not hasattr(source, "_manual_copy_detection")
    assert widget.copy_controls_box.isVisibleTo(widget)
    # the tracks layer stays active, so the editing shortcuts keep working
    assert viewer.layers.selection.active is target

    widget.chain_btn.setChecked(False)
    assert widget._source_layer is None
    assert widget._target_callback not in target.mouse_drag_callbacks
    assert not hasattr(target, "_manual_copy_detection")
    assert not widget.copy_controls_box.isVisibleTo(widget)


def test_right_click_on_target_copies_from_source(labels_app):
    """A right-click on the target track layer copies the source detection under the
    cursor into the tracks."""

    viewer, widget, _source = labels_app
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)

    tracks = widget.tracks_viewer.tracks
    n_nodes = tracks.graph.num_nodes()

    target = widget._get_target_layer()
    # right-click in the middle of the source label at t=3 (world coordinates)
    widget._target_callback(target, _RightClickEvent(position=(3, 51.5, 11.5)))

    assert tracks.graph.num_nodes() == n_nodes + 1
    node = next(
        node
        for node in tracks.graph.node_ids()
        if int(tracks.get_track_id(node)) == widget.tracks_viewer.selected_track
    )
    assert tracks.get_time(node) == 3


def test_copy_labels_from_source(labels_app):
    """Copying labels from a connected source layer adds nodes with the current
    tracklet id."""

    _viewer, widget, source = labels_app
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)

    tracks = widget.tracks_viewer.tracks
    n_nodes = tracks.graph.num_nodes()

    for t in range(3):
        frame = np.asarray(source.data[t])
        widget._add_segmentation_node(t, np.where(frame == t + 1))

    assert tracks.graph.num_nodes() == n_nodes + 3
    # all copies share the current tracklet id
    track_id = widget.tracks_viewer.selected_track
    copied = [
        node
        for node in tracks.graph.node_ids()
        if int(tracks.get_track_id(node)) == track_id
    ]
    assert len(copied) == 3


def test_copy_labels_as_new_track(labels_app):
    """With 'copy as new track' checked, copying into a frame that already holds a
    node of the current tracklet starts a new tracklet instead of growing it."""

    _viewer, widget, source = labels_app
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)

    tracks = widget.tracks_viewer.tracks
    n_nodes = tracks.graph.num_nodes()

    frame = np.asarray(source.data[0])
    widget._add_segmentation_node(0, np.where(frame == 1))
    first_track_id = widget.tracks_viewer.selected_track

    # copy a non-overlapping label into the same frame
    widget.new_track_on_copy_checkbox.setChecked(True)
    widget._add_segmentation_node(0, (np.array([70, 70, 71]), np.array([70, 71, 70])))

    assert tracks.graph.num_nodes() == n_nodes + 2
    assert widget.tracks_viewer.selected_track != first_track_id


def test_copy_points_from_source(points_app):
    """Copying points from a connected Points source layer adds point nodes."""

    _viewer, widget, source = points_app
    widget.source_layer_dropdown.setCurrentText("src_pts")
    widget.chain_btn.setChecked(True)
    assert widget._source_layer is source

    tracks = widget.tracks_viewer.tracks
    n_nodes = tracks.graph.num_nodes()

    for t in range(3):
        widget._add_node(t, position=np.array([30.0, 40.0]))

    assert tracks.graph.num_nodes() == n_nodes + 3


def test_right_click_on_target_copies_point(points_app):
    """A right-click on the target points layer copies the source point under the
    cursor, and a click away from any point copies nothing."""

    _viewer, widget, _source = points_app
    widget.source_layer_dropdown.setCurrentText("src_pts")
    widget.chain_btn.setChecked(True)

    tracks = widget.tracks_viewer.tracks
    n_nodes = tracks.graph.num_nodes()
    target = widget._get_target_layer()

    # nowhere near a source point: nothing is copied
    widget._target_callback(target, _RightClickEvent(position=(2, 80.0, 80.0)))
    assert tracks.graph.num_nodes() == n_nodes

    widget._target_callback(target, _RightClickEvent(position=(2, 30.0, 40.0)))
    assert tracks.graph.num_nodes() == n_nodes + 1


def test_new_tracks_reset_the_connection(
    labels_app, solution_tracks_2d_without_segmentation
):
    """Switching to another tracks object drops the source connection."""

    _viewer, widget, source = labels_app
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)
    assert widget._source_layer is source

    widget.tracks_viewer.update_tracks(
        tracks=solution_tracks_2d_without_segmentation, name="other"
    )
    assert widget._source_layer is None
    assert not widget.chain_btn.isChecked()
    assert widget._mode == "points"


def test_editing_selection_widget_has_copy_tab(make_napari_viewer, solution_tracks_2d):
    """The copy controls are shown as a separate tab in the Editing & Selection menu."""

    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_2d, name="test")

    widget = EditingSelectionWidget(viewer)
    assert widget.tabs.count() == 2
    assert isinstance(widget.tabs.widget(1), CopyFromSourceWidget)


def test_right_click_selects_without_recentering(labels_app):
    """Copying selects the copied node but must not move the dims sliders.

    The tracks layer is the active layer while copying, so a right-click also reaches its
    own click handler; that handler must ignore the right button, otherwise it selects
    (and centers on) whatever node was under the cursor.
    """

    viewer, widget, _source = labels_app
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)
    target = widget._get_target_layer()
    tracks_viewer = widget.tracks_viewer

    viewer.dims.set_current_step(0, 3)
    step_before = tuple(viewer.dims.current_step)

    # drive the full callback chain, the way napari dispatches a click
    _drive_callbacks(target, _RightClickEvent(position=(3, 51.5, 11.5)))

    assert tuple(viewer.dims.current_step) == step_before
    # the copied node is selected
    assert len(tracks_viewer.selected_nodes) == 1
    copied = tracks_viewer.selected_nodes[0]
    assert tracks_viewer.tracks.get_time(copied) == 3

    # right-clicking on top of a node in another frame does not select or jump to it
    node_position = tracks_viewer.tracks.get_position(1, incl_time=True)
    _drive_callbacks(target, _RightClickEvent(position=tuple(node_position)))

    assert tuple(viewer.dims.current_step) == step_before
    assert tracks_viewer.selected_nodes[0] == copied


def _frame(tracks, t=0):
    return np.asarray(tracks.segmentation[t])


@pytest.fixture
def overlapping_source(labels_app):
    """Add a source label at t=0 that partly overlaps node 1 of the tracks.

    Node 1 covers rows/columns 30-70, the source label covers 60-79, so the click at
    (65, 65) lands on both, and (75, 75) lands on the source label only.
    """

    viewer, widget, source = labels_app
    source.data[0][60:80, 60:80] = 9
    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)
    return viewer, widget, source


def test_click_on_existing_label_replaces_it_with_the_active_track(overlapping_source):
    """Clicking a label that is already in the tracks replaces it with the copied label,
    under the *active* tracklet id - a right-click copies, it never selects the node that
    was clicked on."""

    _viewer, widget, _source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()
    active_track = widget.tracks_viewer.selected_track
    # the active tracklet has no node in this frame yet
    assert widget._current_track_node(0, active_track) is None

    widget._target_callback(target, _RightClickEvent(position=(0, 65.5, 65.5)))

    # the clicked node is gone, the copy belongs to the still-active tracklet
    assert not tracks.graph.has_node(1)
    assert widget.tracks_viewer.selected_track == active_track
    new_node = int(_frame(tracks)[65, 65])
    assert int(tracks.get_track_id(new_node)) == active_track

    # and covers exactly the copied label
    expected = np.zeros((100, 100), dtype=bool)
    expected[60:80, 60:80] = True
    np.testing.assert_array_equal(_frame(tracks) == new_node, expected)


def test_click_on_own_label_replaces_its_pixels_in_place(overlapping_source):
    """Clicking the active tracklet's own label keeps the node (and its edges): only its
    pixels are replaced by the copied ones."""

    _viewer, widget, source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()

    # first copy: the active tracklet gets a node in frame 0 (rows/cols 60-79)
    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))
    node = int(_frame(tracks)[75, 75])
    active_track = widget.tracks_viewer.selected_track
    assert int(tracks.get_track_id(node)) == active_track

    # a second, shifted source label (rows/cols 70-89) over that same node
    source.data[0][60:80, 60:80] = 0
    source.data[0][70:90, 70:90] = 8
    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))

    # same node, same tracklet, pixels replaced by the new label
    assert tracks.graph.has_node(node)
    assert int(tracks.get_track_id(node)) == active_track
    assert widget.tracks_viewer.selected_track == active_track
    expected = np.zeros((100, 100), dtype=bool)
    expected[70:90, 70:90] = True
    np.testing.assert_array_equal(_frame(tracks) == node, expected)


def test_replace_of_another_track_is_refused_with_preserve_labels(overlapping_source):
    """With 'preserve labels' on, clicking a label of another tracklet copies nothing."""

    _viewer, widget, _source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()
    target.preserve_labels = True
    # node 1 belongs to tracklet 1, which is not the active one
    assert int(tracks.get_track_id(1)) != widget.tracks_viewer.selected_track

    before = _frame(tracks).copy()
    n_nodes = tracks.graph.num_nodes()

    widget._target_callback(target, _RightClickEvent(position=(0, 65.5, 65.5)))

    assert tracks.graph.num_nodes() == n_nodes
    np.testing.assert_array_equal(_frame(tracks), before)


def test_own_label_can_be_replaced_with_preserve_labels(overlapping_source):
    """With 'preserve labels' on, a label of the active tracklet can still be updated,
    but the copy does not reach into the labels of other tracklets."""

    _viewer, widget, source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()

    # give the active tracklet a node in frame 0 (rows/cols 71-79, node 1 keeps 30-70)
    target.preserve_labels = True
    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))
    node = int(_frame(tracks)[75, 75])
    active_track = widget.tracks_viewer.selected_track
    assert node != 1

    # a second, shifted source label over that same node and over node 1
    source.data[0][60:80, 60:80] = 0
    source.data[0][50:90, 50:90] = 8
    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))

    frame = _frame(tracks)
    # the active tracklet's own label was replaced ...
    assert tracks.graph.has_node(node)
    assert int(tracks.get_track_id(node)) == active_track
    assert frame[85, 85] == node
    # ... but node 1 (a different tracklet) was left untouched
    assert tracks.graph.has_node(1)
    assert frame[65, 65] == 1
    assert frame[55, 55] == 1


def test_replace_as_new_track_deletes_the_clicked_node(overlapping_source):
    """With 'copy as new track' on, the clicked node is deleted and the copied label
    becomes a new node with a new tracklet id."""

    _viewer, widget, _source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()
    widget.new_track_on_copy_checkbox.setChecked(True)

    widget._target_callback(target, _RightClickEvent(position=(0, 65.5, 65.5)))

    assert not tracks.graph.has_node(1)
    new_node = int(_frame(tracks)[65, 65])
    assert new_node != 0
    assert int(tracks.get_track_id(new_node)) != 1

    expected = np.zeros((100, 100), dtype=bool)
    expected[60:80, 60:80] = True
    np.testing.assert_array_equal(_frame(tracks) == new_node, expected)


def test_copy_onto_background_respects_preserve_labels(overlapping_source):
    """Clicking where the target is empty copies the label, but with 'preserve labels'
    on only the pixels that are not already part of another label."""

    _viewer, widget, _source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()
    target.preserve_labels = True

    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))

    frame = _frame(tracks)
    new_node = int(frame[75, 75])
    assert new_node not in (0, 1)
    # node 1 kept all of its pixels ...
    assert frame[65, 65] == 1
    # ... and the copy only took the part that was still empty
    expected = np.zeros((100, 100), dtype=bool)
    expected[60:80, 60:80] = True
    expected[60:71, 60:71] = False  # node 1 covers rows/cols 30-70
    np.testing.assert_array_equal(frame == new_node, expected)


def test_copy_onto_background_overwrites_without_preserve_labels(overlapping_source):
    """Without 'preserve labels', the same click copies the label in full and shrinks
    the label it overlaps."""

    _viewer, widget, _source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()

    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))

    frame = _frame(tracks)
    new_node = int(frame[75, 75])
    expected = np.zeros((100, 100), dtype=bool)
    expected[60:80, 60:80] = True
    np.testing.assert_array_equal(frame == new_node, expected)
    # node 1 is still there, shrunk by the overlap
    assert tracks.graph.has_node(1)
    assert frame[65, 65] == new_node
    assert frame[40, 40] == 1


def test_click_on_other_label_joins_the_active_track_node(overlapping_source):
    """Clicking a label of another tracklet while the active tracklet already has a node
    in this frame deletes the clicked node and grows the active tracklet's node with the
    copied pixels (a tracklet can only have one node per frame)."""

    _viewer, widget, source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()

    # the active tracklet gets a node in frame 0
    widget._target_callback(target, _RightClickEvent(position=(0, 75.5, 75.5)))
    node = int(_frame(tracks)[75, 75])
    active_track = widget.tracks_viewer.selected_track

    # a source label on top of node 1, which belongs to a different tracklet
    source.data[0][60:80, 60:80] = 0
    source.data[0][30:40, 30:40] = 7
    widget._target_callback(target, _RightClickEvent(position=(0, 35.5, 35.5)))

    assert not tracks.graph.has_node(1)
    assert int(tracks.get_track_id(node)) == active_track
    assert widget.tracks_viewer.selected_track == active_track
    # the active tracklet's node kept its pixels and gained the copied ones
    frame = _frame(tracks)
    assert frame[75, 75] == node
    assert frame[35, 35] == node


def test_copy_controls_show_the_illustration(labels_app):
    """The copy behaviour illustration is shown at the bottom of the copy controls, and
    scales with the width of the panel."""

    _viewer, widget, _source = labels_app

    assert widget.illustration.renderer().isValid()
    assert widget.illustration.heightForWidth(300) == pytest.approx(
        300 * 366 / 588.29, abs=1
    )
    box_layout = widget.copy_controls_box.layout()
    assert box_layout.itemAt(box_layout.count() - 1).widget() is widget.illustration


def test_replace_is_undone_in_one_step(overlapping_source):
    """A replacement takes several segmentation actions, but they are committed as one
    group, so a single undo brings back the label that was replaced."""

    viewer, widget, _source = overlapping_source
    tracks = widget.tracks_viewer.tracks
    target = widget._get_target_layer()

    before = _frame(tracks).copy()
    n_actions = len(tracks.action_history.undo_stack)

    widget._target_callback(target, _RightClickEvent(position=(0, 65.5, 65.5)))

    assert not np.array_equal(_frame(tracks), before)
    assert len(tracks.action_history.undo_stack) == n_actions + 1

    viewer.dims.set_current_step(0, 3)
    step_before = tuple(viewer.dims.current_step)
    widget.tracks_viewer.undo()

    assert tracks.graph.has_node(1)
    np.testing.assert_array_equal(_frame(tracks), before)
    # undoing does not jump the view to the restored node
    assert tuple(viewer.dims.current_step) == step_before

    widget.tracks_viewer.redo()
    assert tuple(viewer.dims.current_step) == step_before
    assert not tracks.graph.has_node(1)


def test_copy_from_a_lazily_loaded_source(dask_source, monkeypatch):
    """A dask-backed source hands out unevaluated scalars; the copy has to materialise
    them, or the pixel lookup stays lazy and comes back with arrays of unknown length."""

    _viewer, widget, _source = dask_source
    monkeypatch.setattr(
        "motile_tracker.application_menus.copy_from_source_widget.confirm_extend_segmentation",
        lambda current, new: True,
    )

    widget.source_layer_dropdown.setCurrentText("src")
    widget.chain_btn.setChecked(True)

    tracks = widget.tracks_viewer.tracks
    n_nodes = tracks.graph_solution.num_nodes()
    target = widget._get_target_layer()
    # t=7 is outside the original segmentation, so this also covers the extended region
    widget._target_callback(target, _RightClickEvent(position=(7, 51.5, 11.5)))

    assert tracks.graph_solution.num_nodes() == n_nodes + 1
    frame = np.asarray(tracks.segmentation[7])
    # the copied label covers exactly the 4x4 block the source holds at t=7
    assert frame[50:54, 10:14].all()
    assert frame.sum() == frame[50:54, 10:14].sum()


def _copied_node(widget, t):
    """The node of the current tracklet in frame `t`, and its pixel count."""

    tracks = widget.tracks_viewer.tracks
    track_id = widget.tracks_viewer.selected_track
    node = next(
        node
        for node in tracks.graph.node_ids()
        if int(tracks.get_track_id(node)) == track_id and tracks.get_time(node) == t
    )
    n_pixels = int(np.count_nonzero(np.asarray(tracks.segmentation[t]) == node))
    return node, n_pixels


class TestMultiChannelSource:
    """A source layer can hold several alternative segmentations of the same objects on
    extra leading axes; the sliders pick which one a copy reads from."""

    def test_connects_and_reports_the_extra_axis(self, multichannel_labels_app):
        _viewer, widget, source = multichannel_labels_app
        widget.source_layer_dropdown.setCurrentText("src")
        widget.chain_btn.setChecked(True)

        assert widget._source_layer is source
        assert widget._leading_axes(source) == 1
        assert widget.channel_hint.isVisibleTo(widget.copy_controls_box)

        widget.chain_btn.setChecked(False)
        assert not widget.channel_hint.isVisibleTo(widget.copy_controls_box)

    def test_single_channel_source_reports_no_extra_axis(self, labels_app):
        _viewer, widget, source = labels_app
        widget.source_layer_dropdown.setCurrentText("src")
        widget.chain_btn.setChecked(True)

        assert widget._leading_axes(source) == 0
        assert not widget.channel_hint.isVisibleTo(widget.copy_controls_box)

    @pytest.mark.parametrize(("channel", "n_pixels"), [(0, 16), (1, 64)])
    def test_right_click_copies_the_selected_channel(
        self, multichannel_labels_app, channel, n_pixels
    ):
        """The channel in the click position - which napari fills from the slider -
        decides which of the two mask options is copied."""

        _viewer, widget, _source = multichannel_labels_app
        widget.source_layer_dropdown.setCurrentText("src")
        widget.chain_btn.setChecked(True)

        tracks = widget.tracks_viewer.tracks
        n_nodes = tracks.graph.num_nodes()

        target = widget._get_target_layer()
        # a point inside the label in both channels, at t=3
        event = _RightClickEvent(position=(channel, 3, 51.5, 11.5))
        widget._target_callback(target, event)

        assert tracks.graph.num_nodes() == n_nodes + 1
        node, copied_pixels = _copied_node(widget, t=3)
        assert tracks.get_time(node) == 3
        assert copied_pixels == n_pixels

    def test_click_outside_the_smaller_channel_is_ignored(
        self, multichannel_labels_app
    ):
        """A position that only holds a label in channel 1 copies nothing on channel 0."""

        _viewer, widget, _source = multichannel_labels_app
        widget.source_layer_dropdown.setCurrentText("src")
        widget.chain_btn.setChecked(True)

        tracks = widget.tracks_viewer.tracks
        n_nodes = tracks.graph.num_nodes()

        target = widget._get_target_layer()
        # (56, 16) is inside the 8x8 mask of channel 1, but background in channel 0
        widget._target_callback(target, _RightClickEvent(position=(0, 3, 56.5, 16.5)))
        assert tracks.graph.num_nodes() == n_nodes

        widget._target_callback(target, _RightClickEvent(position=(1, 3, 56.5, 16.5)))
        assert tracks.graph.num_nodes() == n_nodes + 1

    def test_segmentation_is_not_grown_for_the_channel_axis(
        self, multichannel_labels_app
    ):
        """Only the trailing dims of a source have to fit inside the segmentation, so a
        matching multi-channel source does not trigger the grow dialog."""

        _viewer, widget, _source = multichannel_labels_app
        tracks = widget.tracks_viewer.tracks
        shape_before = tuple(tracks.segmentation.shape)

        widget.source_layer_dropdown.setCurrentText("src")
        widget.chain_btn.setChecked(True)

        assert widget._source_layer is not None  # connected without asking
        assert tuple(tracks.segmentation.shape) == shape_before

    def test_clicked_track_label_ignores_the_channel_axis(
        self, multichannel_labels_app
    ):
        """The clicked node is read from the target layer, which has no channel axis:
        napari lines the click position up on the trailing dimensions."""

        _viewer, widget, _source = multichannel_labels_app
        widget.source_layer_dropdown.setCurrentText("src")
        widget.chain_btn.setChecked(True)

        # node 1 of the graph_2d fixture sits at (50, 50) in t=0
        for channel in (0, 1):
            event = _RightClickEvent(position=(channel, 0, 50, 50))
            assert widget._clicked_track_label(event) == 1

        # a spot the tracks do not occupy reads as background
        event = _RightClickEvent(position=(0, 0, 51.5, 11.5))
        assert widget._clicked_track_label(event) == 0
