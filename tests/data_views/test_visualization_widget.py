from unittest.mock import MagicMock, patch

import pytest

from motile_tracker.application_menus.visualization_widget import (
    VisualizationWidget,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture(autouse=True)
def clear_viewer_layers(viewer):
    """Clear viewer layers between tests."""
    yield
    viewer.layers.clear()


@pytest.fixture
def visualization_widget(viewer, solution_tracks_3d, qtbot):
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d, name="test")

    widget = VisualizationWidget(viewer)
    qtbot.addWidget(widget)

    assert tracks_viewer.tracking_layers.seg_layer is not None

    yield widget, tracks_viewer

    # the viewer is shared by the whole module, so take this widget back off it the way
    # MenuManager does when the menu is closed
    widget.cleanup()


@pytest.mark.parametrize("mode", ["lineage", "group", "all"])
def test_switch_display_modes(visualization_widget, mode):
    """Test that checking the radio buttons changes the display mode"""

    widget, tracks_viewer = visualization_widget

    widget.mode_widget.button_for_mode(mode).setChecked(True)

    assert tracks_viewer.mode == mode
    assert widget.background_widget.isEnabled() is (mode != "all")


@pytest.mark.parametrize("mode", ["lineage", "group", "all"])
def test_mode_update_syncs_radio_buttons(visualization_widget, mode):
    """Check that the radio button states are updated when the tracks_viewer updates its
    display mode."""

    widget, tracks_viewer = visualization_widget

    tracks_viewer.set_display_mode(mode)
    widget._update_widget_availability()
    radio = widget.mode_widget.button_for_mode(mode)

    assert radio.isChecked()


def test_opacity_updates_seg_layer(visualization_widget):
    """Test that changing the opacity in the widget updates the highlighted/foreground/
    background opacity of the labels."""

    widget, tracks_viewer = visualization_widget
    layer = tracks_viewer.tracking_layers.seg_layer

    widget.highlight_widget.opacity.setValue(0.25)
    widget.foreground_widget.opacity.setValue(0.5)
    widget.background_widget.opacity.setValue(0.75)

    assert layer.highlight_opacity == pytest.approx(0.25)
    assert layer.foreground_opacity == pytest.approx(0.5)
    assert layer.background_opacity == pytest.approx(0.75)


def test_contour_checkbox_updates_layer(visualization_widget):
    """Test that contour (fill) checkboxes are hidden, unless in contour mode, and that
    toggling them changes the contour state on the seg_layer."""

    widget, tracks_viewer = visualization_widget
    layer = tracks_viewer.tracking_layers.seg_layer

    # mode where contour is not available
    widget.mode_widget.button_for_mode("all").setChecked(True)
    layer.contour = 0

    assert widget.highlight_widget.contour.isHidden()
    assert widget.foreground_widget.contour.isHidden()

    # still hidden, because contour is still 0
    widget.mode_widget.button_for_mode("lineage").setChecked(True)

    assert widget.highlight_widget.contour.isHidden()
    assert widget.foreground_widget.contour.isHidden()

    # Enable contours, ensure widgets are visible
    layer.contour = 1

    assert not widget.highlight_widget.contour.isHidden()
    assert not widget.foreground_widget.contour.isHidden()

    # Check = fill = contour OFF
    widget.highlight_widget.contour.setChecked(True)
    widget.foreground_widget.contour.setChecked(False)

    assert layer.highlight_contour is False
    assert layer.foreground_contour is True


@pytest.mark.parametrize(
    "mode", ["all", "visible_no_contours", "visible_with_contours"]
)
def test_update_label_colormap_when_selecting(
    viewer,
    solution_tracks_3d,
    mode,
):
    """Test the actual values on the label colormap"""
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d, name="test")

    seg_layer = tracks_viewer.tracking_layers.seg_layer
    assert hasattr(seg_layer, "update_label_colormap")

    cmap = seg_layer.colormap

    # Select specific labels for deterministic testing
    keys = list(cmap.color_dict.keys())
    numeric_keys = [k for k in keys if isinstance(k, int) and k != 0][:3]
    k0, k1, k2 = numeric_keys[:3]  # two labels for testing

    # Set a random starting value, to ensure it got updated
    for k in [k1, k2]:
        cmap.color_dict[k][-1] = 0.5

    assert seg_layer.background_opacity == 0.3
    assert seg_layer.foreground_opacity == 0.6
    assert seg_layer.highlight_opacity == 1.0

    # Make the viewer highlight one label
    tracks_viewer.selected_nodes.add_list([k2], append=False)

    # Call update_label_colormap in each test mode
    if mode == "all":
        seg_layer.update_label_colormap("all")
        # visible == "all" → all non-0, non-None get alpha 0.6 (foreground opacity)
        assert seg_layer.colormap.color_dict[k0][-1] == pytest.approx(
            seg_layer.foreground_opacity
        )
        assert seg_layer.colormap.color_dict[k1][-1] == pytest.approx(
            seg_layer.foreground_opacity
        )
        assert seg_layer.colormap.color_dict[k2][-1] == seg_layer.highlight_opacity

        assert seg_layer.filled_labels == []

    elif mode == "visible_no_contours":
        visible = [k1]  # simulate lineage/group mode
        seg_layer.update_label_colormap(visible)

        # normal mode: background labels get 0.3, foreground labels get 0.6, highlighted gets 1
        assert seg_layer.colormap.color_dict[k0][-1] == pytest.approx(
            seg_layer.background_opacity
        )
        assert seg_layer.colormap.color_dict[k1][-1] == pytest.approx(
            seg_layer.foreground_opacity
        )
        assert seg_layer.colormap.color_dict[k2][-1] == seg_layer.highlight_opacity

        assert seg_layer.filled_labels == []

    elif mode == "visible_with_contours":
        seg_layer.contour = 1
        visible = [k1]
        seg_layer.update_label_colormap(visible)

        # contour mode: background labels have 0.3,
        assert seg_layer.colormap.color_dict[k0][-1] == pytest.approx(
            seg_layer.background_opacity
        )  # background
        assert seg_layer.colormap.color_dict[k1][-1] == pytest.approx(
            seg_layer.foreground_opacity
        )  # foreground
        assert seg_layer.colormap.color_dict[k2][-1] == pytest.approx(
            seg_layer.highlight_opacity
        )  # highlighted

        assert set(seg_layer.filled_labels) == {k1, k2}


def test_selecting_node_does_not_highlight_same_track_nodes(
    viewer,
    solution_tracks_3d_with_division,
):
    """Highlighting one node must not change the opacity of other nodes that share
    its track id.

    Regression test for per-track color-array aliasing: _get_colormap must give
    each node its own color array, because set_opacity mutates the alpha in place.
    In solution_tracks_3d_with_division, nodes 1 and 2 share track id 1 (the
    tracklet before the division). Selecting node 2 must leave node 1 at the
    foreground opacity, not the highlight opacity.
    """
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")
    seg_layer = tracks_viewer.tracking_layers.seg_layer

    same_track_unselected, selected = 1, 2
    assert tracks_viewer.tracks.get_track_id(
        same_track_unselected
    ) == tracks_viewer.tracks.get_track_id(selected)

    tracks_viewer.selected_nodes.add(selected, append=False)
    seg_layer.update_label_colormap("all")

    color_dict = seg_layer.colormap.color_dict
    assert color_dict[selected][-1] == pytest.approx(seg_layer.highlight_opacity)
    assert color_dict[same_track_unselected][-1] == pytest.approx(
        seg_layer.foreground_opacity
    )


# Ortho-views integration tests
class TestOrthoViewsIntegration:
    """Tests for orthogonal views checkbox and initialization."""

    def test_ortho_views_checkbox_initially_unchecked(self, visualization_widget):
        """Test that the ortho views checkbox starts unchecked."""
        widget, _ = visualization_widget
        assert not widget.show_ortho_views.isChecked()

    @patch("motile_tracker.application_menus.visualization_widget._VIEWER_MANAGERS", {})
    @patch(
        "motile_tracker.application_menus.visualization_widget.initialize_ortho_views"
    )
    def test_initialize_ortho_views_viewer_not_in_managers(
        self, mock_init, visualization_widget
    ):
        """Test ortho views initialization when viewer is not already in _VIEWER_MANAGERS."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_manager.main_controls_widget.show_orth_views.connect = MagicMock(
            return_value=MagicMock()
        )
        mock_init.return_value = mock_manager

        # Trigger checkbox
        widget.show_ortho_views.setChecked(True)

        # verify initialize_ortho_views was called
        mock_init.assert_called_once_with(widget.viewer)

        # verify manager was stored
        assert widget.orth_view_manager is not None
        assert widget.orth_views_connection is not None

    def test_initialize_ortho_views_with_existing_manager(self, visualization_widget):
        """Test ortho views when viewer is already in _VIEWER_MANAGERS."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_manager.show = MagicMock()
        mock_manager.hide = MagicMock()

        # Mock the _VIEWER_MANAGERS to already contain this viewer
        with patch(
            "motile_tracker.application_menus.visualization_widget._VIEWER_MANAGERS",
            {widget.viewer: mock_manager},
        ):
            widget.show_ortho_views.setChecked(True)

            # verify manager.show() was called
            mock_manager.show.assert_called_once()

    def test_ortho_views_hide_when_unchecked(self, visualization_widget):
        """Test that ortho views are hidden and resized when checkbox is unchecked."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_manager.show = MagicMock()
        mock_manager.hide = MagicMock()
        mock_manager.set_splitter_sizes = MagicMock()

        with patch(
            "motile_tracker.application_menus.visualization_widget._VIEWER_MANAGERS",
            {widget.viewer: mock_manager},
        ):
            # Check the box first
            widget.show_ortho_views.setChecked(True)
            mock_manager.show.assert_called_once()

            # Uncheck the box
            widget.show_ortho_views.setChecked(False)

            # Verify hide and set_splitter_sizes were called
            mock_manager.hide.assert_called_once()
            mock_manager.set_splitter_sizes.assert_called_once_with(0.0, 0.0)

    @patch(
        "motile_tracker.application_menus.visualization_widget.initialize_ortho_views"
    )
    def test_ortho_views_signal_connection(self, mock_init, visualization_widget):
        """Test that the ortho view manager's signal is connected to the widget."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_signal = MagicMock()
        mock_manager.main_controls_widget.show_orth_views = mock_signal
        mock_manager.main_controls_widget.destroyed = MagicMock()
        mock_signal.connect = MagicMock(return_value=MagicMock())

        mock_init.return_value = mock_manager

        widget.show_ortho_views.setChecked(True)

        # Verify signal was connected to initialize_ortho_views
        mock_signal.connect.assert_called_once()
        call_args = mock_signal.connect.call_args[0]
        assert call_args[0] == widget.initialize_ortho_views

    @patch(
        "motile_tracker.application_menus.visualization_widget.initialize_ortho_views"
    )
    def test_on_ortho_cleanup(self, mock_init, visualization_widget):
        """Test cleanup when ortho view manager is destroyed."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_manager.main_controls_widget.show_orth_views = MagicMock()
        mock_manager.main_controls_widget.destroyed = MagicMock()
        mock_manager.main_controls_widget.show_orth_views.connect = MagicMock(
            return_value=MagicMock()
        )

        mock_init.return_value = mock_manager

        widget.show_ortho_views.setChecked(True)

        # Simulate widget destruction
        widget._on_ortho_cleanup()

        # Verify checkbox is unchecked and disconnected
        assert not widget.show_ortho_views.isChecked()
        assert widget.orth_view_manager is None
        assert widget.orth_views_connection is None

    @patch(
        "motile_tracker.application_menus.visualization_widget.initialize_ortho_views"
    )
    def test_disconnect_ortho_views_with_valid_connection(
        self, mock_init, visualization_widget
    ):
        """Test _disconnect_ortho_views with valid connection."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_signal = MagicMock()
        mock_manager.main_controls_widget.show_orth_views = mock_signal
        mock_manager.main_controls_widget.destroyed = MagicMock()
        mock_signal.connect = MagicMock(return_value=MagicMock())
        mock_signal.disconnect = MagicMock()

        mock_init.return_value = mock_manager

        widget.show_ortho_views.setChecked(True)

        # Disconnect
        widget._disconnect_ortho_views()

        # Verify disconnect was called and connection is cleared
        mock_signal.disconnect.assert_called_once()
        assert widget.orth_views_connection is None
        assert widget.orth_view_manager is None

        # No-op, should not raise
        widget._disconnect_ortho_views()

        assert widget.orth_views_connection is None
        assert widget.orth_view_manager is None

    def test_initialize_ortho_views_syncs_checkbox_state(self, visualization_widget):
        """Test that initialize_ortho_views syncs checkbox state."""
        widget, _ = visualization_widget

        mock_manager = MagicMock()
        mock_manager.main_controls_widget.show_orth_views = MagicMock()
        mock_manager.main_controls_widget.destroyed = MagicMock()
        mock_manager.main_controls_widget.show_orth_views.connect = MagicMock(
            return_value=MagicMock()
        )

        with patch(
            "motile_tracker.application_menus.visualization_widget._VIEWER_MANAGERS",
            {widget.viewer: mock_manager},
        ):
            # Manually call with checked=False (simulating external unchecking)
            widget.initialize_ortho_views(False)

            # Verify checkbox state is synced
            assert not widget.show_ortho_views.isChecked()


# Plane slider integration tests
class TestPlaneSlidersIntegration:
    """Tests for the plane and clipping plane controls in the visualization menu.

    The plane sliders act on the selected layer and on the layers linked to it, which
    for the tracking layers is the group TracksLayerGroup links on their clipping
    planes alone.
    """

    @pytest.fixture
    def plane_sliders(self, visualization_widget, viewer):
        widget, tracks_viewer = visualization_widget
        viewer.dims.ndisplay = 3
        # start from an empty selection, so that every test below selects a layer that
        # was not already the active one and the plane sliders pick it up
        viewer.layers.selection.clear()
        return widget, widget.plane_sliders, tracks_viewer.tracking_layers

    def test_selecting_points_finds_the_whole_tracking_group(
        self, plane_sliders, viewer
    ):
        """With the points layer selected, the plane controls act on all three layers"""

        _, sliders, layers = plane_sliders
        viewer.layers.selection.active = layers.points_layer

        # the points layer has no plane of its own, so it borrows the one of the seg
        assert sliders._plane_layer() is layers.seg_layer
        assert set(sliders._target_layers()) == set(layers.track_layers)

    def test_plane_mode_gives_the_points_a_slab_and_leaves_the_seg_unclipped(
        self, plane_sliders, viewer
    ):
        """The points mimic plane mode with a slab, which must not clip the seg layer"""

        _, sliders, layers = plane_sliders
        viewer.layers.selection.active = layers.points_layer
        sliders._set_plane_mode()
        sliders.plane_slider.setValue(4)

        assert layers.seg_layer.depiction == "plane"
        assert layers.seg_layer.plane.position == (4.0, 0.0, 0.0)

        half_thickness = sliders.slab_thickness_box.value() / 2
        for layer in (layers.points_layer, layers.tracks_layer):
            lower, upper = layer.experimental_clipping_planes
            assert lower.position == (4.0 - half_thickness, 0.0, 0.0)
            assert upper.position == (4.0 + half_thickness, 0.0, 0.0)
            assert lower.enabled and upper.enabled

        # the layer that defines the plane is clipped by that plane, not by the slab
        for clip_plane in layers.seg_layer.experimental_clipping_planes:
            assert not clip_plane.enabled

    def test_clipping_plane_mode_is_shared_by_all_tracking_layers(
        self, plane_sliders, viewer
    ):
        """Outside plane mode the whole group is clipped the same way"""

        _, sliders, layers = plane_sliders
        viewer.layers.selection.active = layers.seg_layer
        sliders._set_clipping_plane_mode()
        sliders.clipping_plane_slider.setValue((2, 6))

        assert layers.seg_layer.depiction == "volume"
        for layer in layers.track_layers:
            lower, upper = layer.experimental_clipping_planes
            assert lower.position == (2.0, 0.0, 0.0)
            assert upper.position == (6.0, 0.0, 0.0)
            assert lower.enabled and upper.enabled

    def test_cleanup_takes_the_plane_sliders_off_the_viewer(
        self, plane_sliders, viewer
    ):
        """Closing the menu must not leave callbacks behind pointing at dead widgets"""

        widget, sliders, layers = plane_sliders
        viewer.layers.selection.active = layers.points_layer

        assert sliders._snap_cursor_to_plane in viewer.mouse_move_callbacks

        widget.cleanup()

        for callbacks in (
            viewer.mouse_move_callbacks,
            viewer.mouse_drag_callbacks,
            viewer.mouse_double_click_callbacks,
        ):
            assert sliders._snap_cursor_to_plane not in callbacks

        # idempotent
        widget.cleanup()
