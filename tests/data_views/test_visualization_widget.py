from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from napari_track_edit.application_menus.visualization_widget import (
    VisualizationWidget,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


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

    return widget, tracks_viewer


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


def test_overlay_checkbox_toggles_text_overlay(visualization_widget):
    """Toggling the keybinds checkbox shows/hides the viewer text overlay.

    Regression: the checkbox was wired to 'stateChanged', which hands over Qt's check
    state as an int (2 when checked). napari's TextOverlay.visible is a strict
    pydantic bool, so checking the box raised a ValidationError instead.
    """

    widget, _ = visualization_widget
    checkbox = widget.show_viewer_overlay

    # starts checked, matching the overlay being shown with the display mode
    assert checkbox.isChecked()

    checkbox.setChecked(False)
    assert widget.viewer.text_overlay.visible is False

    checkbox.setChecked(True)
    assert widget.viewer.text_overlay.visible is True


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

    @patch(
        "napari_track_edit.application_menus.visualization_widget._VIEWER_MANAGERS", {}
    )
    @patch(
        "napari_track_edit.application_menus.visualization_widget.initialize_ortho_views"
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
            "napari_track_edit.application_menus.visualization_widget._VIEWER_MANAGERS",
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
            "napari_track_edit.application_menus.visualization_widget._VIEWER_MANAGERS",
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
        "napari_track_edit.application_menus.visualization_widget.initialize_ortho_views"
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
        "napari_track_edit.application_menus.visualization_widget.initialize_ortho_views"
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
        "napari_track_edit.application_menus.visualization_widget.initialize_ortho_views"
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
            "napari_track_edit.application_menus.visualization_widget._VIEWER_MANAGERS",
            {widget.viewer: mock_manager},
        ):
            # Manually call with checked=False (simulating external unchecking)
            widget.initialize_ortho_views(False)

            # Verify checkbox state is synced
            assert not widget.show_ortho_views.isChecked()


class TestColorByWidget:
    """The "Color by" dropdown: what it offers and what picking one does."""

    @pytest.fixture
    def group(self, visualization_widget):
        _widget, tracks_viewer = visualization_widget
        tracks_viewer.tracks.add_feature(
            "my_group",
            {
                "feature_type": "node",
                "value_type": "bool",
                "num_values": 1,
                "display_name": "my_group",
                "default_value": False,
            },
        )
        return "my_group"

    def test_lists_none_track_and_lineage(self, visualization_widget):
        widget, _tracks_viewer = visualization_widget
        combo = widget.color_by_widget.combo

        labels = [combo.itemText(i) for i in range(combo.count())]

        assert labels == ["None", "Tracklet ID", "Lineage ID"]

    def test_starts_on_the_feature_in_use(self, visualization_widget):
        widget, tracks_viewer = visualization_widget
        combo = widget.color_by_widget.combo

        assert combo.itemData(combo.currentIndex()) == tracks_viewer.color_feature_key

    def test_picking_a_feature_sets_it_on_the_viewer(self, visualization_widget):
        widget, tracks_viewer = visualization_widget
        combo = widget.color_by_widget.combo
        lineage_key = tracks_viewer.tracks.features.lineage_key

        combo.setCurrentIndex(combo.findData(lineage_key))

        assert tracks_viewer.color_feature_key == lineage_key

    def test_picking_none_colors_every_node_the_same(self, visualization_widget):
        widget, tracks_viewer = visualization_widget

        widget.color_by_widget.combo.setCurrentIndex(0)

        assert tracks_viewer.color_feature_key is None
        nodes = list(tracks_viewer.tracks.graph_solution.node_ids())
        colors = tracks_viewer.colormap.get_colors(nodes)
        assert np.all(colors[:, :3] == colors[0, :3])

    def test_follows_a_change_made_elsewhere(self, visualization_widget):
        widget, tracks_viewer = visualization_widget
        lineage_key = tracks_viewer.tracks.features.lineage_key

        tracks_viewer.set_color_feature(lineage_key)

        combo = widget.color_by_widget.combo
        assert combo.itemData(combo.currentIndex()) == lineage_key

    def test_picks_up_a_group_added_after_it_was_built(
        self, visualization_widget, group
    ):
        widget, _tracks_viewer = visualization_widget

        widget.color_by_widget._populate()  # what showing the panel does

        assert widget.color_by_widget.combo.findData(group) != -1

    def test_repopulating_does_not_change_the_feature(
        self, visualization_widget, group
    ):
        widget, tracks_viewer = visualization_widget
        tracks_viewer.set_color_feature(group)

        widget.color_by_widget._populate()

        assert tracks_viewer.color_feature_key == group
        combo = widget.color_by_widget.combo
        assert combo.itemData(combo.currentIndex()) == group
