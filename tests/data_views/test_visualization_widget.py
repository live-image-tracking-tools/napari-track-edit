import numpy as np
import pytest
from napari_orthogonal_views.ortho_view_manager import _VIEWER_MANAGERS

from napari_track_edit.application_menus.plane_slider_widget import PlaneSliderWidget
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


def test_overlay_stays_hidden_when_changing_display_mode(visualization_widget):
    """Regression: set_display_mode (e.g. pressing Q) forced the text overlay to be
    visible again, while the checkbox stayed unchecked."""

    widget, tracks_viewer = visualization_widget
    widget.show_viewer_overlay.setChecked(False)

    for mode in ("lineage", "group", "all"):
        tracks_viewer.set_display_mode(mode)
        assert widget.viewer.text_overlay.visible is False
        assert not widget.show_viewer_overlay.isChecked()

    widget.show_viewer_overlay.setChecked(True)
    tracks_viewer.set_display_mode("lineage")
    assert widget.viewer.text_overlay.visible is True


def test_reopened_widget_shows_current_overlay_state(visualization_widget, qtbot):
    widget, _ = visualization_widget
    widget.show_viewer_overlay.setChecked(False)

    new_widget = VisualizationWidget(widget.viewer)
    qtbot.addWidget(new_widget)

    assert not new_widget.show_viewer_overlay.isChecked()
    # take it off the shared viewer before qtbot deletes it, as MenuManager does
    new_widget.cleanup()


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
    """The 'Orthogonal views' checkbox, against a real ortho view manager."""

    @pytest.fixture
    def manager(self, viewer):
        yield
        if viewer in _VIEWER_MANAGERS:
            _VIEWER_MANAGERS[viewer].cleanup()

    def test_checkbox_initially_unchecked(self, visualization_widget):
        widget, _ = visualization_widget
        assert not widget.show_ortho_views.isChecked()

    def test_checkbox_shows_and_hides_ortho_views(self, visualization_widget, manager):
        widget, _ = visualization_widget

        widget.show_ortho_views.setChecked(True)
        ortho = _VIEWER_MANAGERS[widget.viewer]
        assert ortho.is_shown()

        widget.show_ortho_views.setChecked(False)
        assert not ortho.is_shown()

    def test_follows_the_ortho_views_checkbox(self, visualization_widget, manager):
        widget, _ = visualization_widget
        widget.show_ortho_views.setChecked(True)
        ortho_checkbox = _VIEWER_MANAGERS[
            widget.viewer
        ].main_controls_widget.show_checkbox

        ortho_checkbox.setChecked(False)
        assert not widget.show_ortho_views.isChecked()

        ortho_checkbox.setChecked(True)
        assert widget.show_ortho_views.isChecked()

    def test_ortho_views_survive_closing_the_widget(
        self, visualization_widget, manager, qtbot
    ):
        """Regression: after closing the visualization widget with ortho views active,
        toggling the ortho views' own checkbox raised because the deleted widget was
        still connected. Reopening the widget picks up the existing ortho views."""

        viewer = visualization_widget[0].viewer
        # not registered with qtbot, because this test deletes it
        widget = VisualizationWidget(viewer)
        widget.show_ortho_views.setChecked(True)
        ortho = _VIEWER_MANAGERS[viewer]

        # what MenuManager does when the dock is closed
        widget.cleanup()
        widget.setParent(None)
        widget.deleteLater()
        qtbot.wait(10)

        ortho.main_controls_widget.show_checkbox.setChecked(False)
        assert not ortho.is_shown()
        ortho.main_controls_widget.show_checkbox.setChecked(True)
        assert ortho.is_shown()

        new_widget = VisualizationWidget(viewer)
        qtbot.addWidget(new_widget)
        assert new_widget.show_ortho_views.isChecked()
        ortho.main_controls_widget.show_checkbox.setChecked(False)
        assert not new_widget.show_ortho_views.isChecked()
        new_widget.cleanup()


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


# Plane slider integration tests
class TestPlaneSlidersIntegration:
    """Tests for the plane and clipping plane controls in the visualization menu.

    The plane sliders act on the selected layer and, for the tracking layers, on the
    whole group of tracking layers.
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

    def test_tracking_layers_share_nothing_else(self, plane_sliders, viewer):
        """The group shares the plane controls only, the layers stay independent"""

        _, sliders, layers = plane_sliders
        viewer.layers.selection.active = layers.points_layer
        sliders._set_mode("clipping_plane")

        layers.points_layer.visible = False
        layers.points_layer.opacity = 0.2
        assert layers.seg_layer.visible
        assert layers.seg_layer.opacity != 0.2

    def test_plane_mode_gives_the_points_a_slab_and_leaves_the_seg_unclipped(
        self, plane_sliders, viewer
    ):
        """The points mimic plane mode with a slab, which must not clip the seg layer"""

        _, sliders, layers = plane_sliders
        viewer.layers.selection.active = layers.points_layer
        sliders._set_mode("plane")
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
        sliders._set_mode("clipping_plane")
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


class TestPlaneLinkedImage:
    """Tests for linking an image layer to the plane controls of the tracking layers.

    The link only shares the plane, its depiction and the clipping planes, unlike a
    napari link, which shares every common attribute (including e.g. the colormap of
    two labels layers, which napari cannot compare).
    """

    @pytest.fixture
    def linked(self, visualization_widget, viewer):
        widget, tracks_viewer = visualization_widget
        layers = tracks_viewer.tracking_layers
        image = viewer.add_image(
            np.random.random(layers.seg_layer.data.shape), name="raw"
        )
        viewer.add_image(np.zeros((2, 3, 4, 5)), name="other shape")
        viewer.dims.ndisplay = 3
        viewer.layers.selection.active = layers.seg_layer
        return widget, image, layers

    def test_lists_only_images_with_the_shape_of_the_segmentation(self, linked):
        widget, _, _ = linked
        dropdown = widget.plane_sliders.link_dropdown

        names = [dropdown.itemText(i) for i in range(dropdown.count())]
        assert names == ["raw"]

    def test_linked_image_follows_the_plane(self, linked):
        widget, image, layers = linked
        sliders = widget.plane_sliders
        sliders._set_mode("plane")
        sliders.plane_slider.setValue(3)

        widget.plane_sliders.link_dropdown.setCurrentText("raw")
        widget.plane_sliders.link_btn.setChecked(True)

        # the image takes on the plane of the group when it joins
        assert image.depiction == "plane"
        assert image.plane.position == layers.seg_layer.plane.position

        sliders.plane_slider.setValue(5)
        assert image.plane.position == (5.0, 0.0, 0.0)

        # only the plane controls are linked
        layers.seg_layer.visible = False
        assert image.visible

    def test_linked_image_is_clipped_with_the_group(self, linked):
        widget, image, _ = linked
        sliders = widget.plane_sliders
        widget.plane_sliders.link_dropdown.setCurrentText("raw")
        widget.plane_sliders.link_btn.setChecked(True)

        sliders._set_mode("clipping_plane")
        sliders.clipping_plane_slider.setValue((2, 6))

        lower, upper = image.experimental_clipping_planes
        assert lower.position == (2.0, 0.0, 0.0)
        assert upper.position == (6.0, 0.0, 0.0)
        assert lower.enabled and upper.enabled

    def test_selecting_the_image_drives_the_group(self, linked, viewer):
        widget, image, layers = linked
        sliders = widget.plane_sliders
        widget.plane_sliders.link_dropdown.setCurrentText("raw")
        widget.plane_sliders.link_btn.setChecked(True)

        viewer.layers.selection.active = image
        assert set(sliders._target_layers()) == {image, *layers.track_layers}

    def test_unlinking_releases_the_image(self, linked):
        widget, image, _ = linked
        sliders = widget.plane_sliders
        sliders._set_mode("plane")
        widget.plane_sliders.link_dropdown.setCurrentText("raw")
        widget.plane_sliders.link_btn.setChecked(True)
        sliders.plane_slider.setValue(3)

        widget.plane_sliders.link_btn.setChecked(False)
        sliders.plane_slider.setValue(5)

        assert image not in sliders._target_layers()
        # the image goes back to a plain volume, without clipping
        assert image.depiction == "volume"
        assert not any(plane.enabled for plane in image.experimental_clipping_planes)

    def test_unlinking_the_selected_image_shows_it_as_volume(self, linked, viewer):
        widget, image, _ = linked
        sliders = widget.plane_sliders
        sliders._set_mode("clipping_plane")
        widget.plane_sliders.link_dropdown.setCurrentText("raw")
        widget.plane_sliders.link_btn.setChecked(True)
        viewer.layers.selection.active = image

        widget.plane_sliders.link_btn.setChecked(False)

        assert sliders.mode == "volume"
        assert image.depiction == "volume"
        assert not any(plane.enabled for plane in image.experimental_clipping_planes)

    def test_link_row_works_without_a_selected_layer(self, linked, viewer, qtbot):
        widget, _, _ = linked
        viewer.layers.selection.clear()
        sliders = PlaneSliderWidget(viewer, link_group=list)
        qtbot.addWidget(sliders)

        # the plane controls wait for a selected layer, linking an image does not
        assert not sliders.mode_widget.isEnabled()
        assert sliders.link_widget.isEnabled()
        sliders.cleanup()

    def test_removing_the_image_unlinks_it(self, linked, viewer):
        widget, image, _ = linked
        widget.plane_sliders.link_dropdown.setCurrentText("raw")
        widget.plane_sliders.link_btn.setChecked(True)

        viewer.layers.remove(image)

        assert not widget.plane_sliders.link_btn.isChecked()
        assert widget.plane_sliders.linked_images == []

    def test_several_images_can_be_linked(self, linked, viewer):
        widget, image, layers = linked
        sliders = widget.plane_sliders
        second = viewer.add_image(
            np.random.random(layers.seg_layer.data.shape), name="raw 2"
        )
        viewer.layers.selection.active = layers.seg_layer  # adding selected the image
        sliders._set_mode("plane")
        sliders.plane_slider.setValue(3)

        for name in ("raw", "raw 2"):
            sliders.link_dropdown.setCurrentText(name)
            sliders.link_btn.setChecked(True)

        # picking another image in the dropdown no longer unlinks the first one
        assert sliders.linked_images == [image, second]
        sliders.plane_slider.setValue(5)
        for linked_image in (image, second):
            assert linked_image.depiction == "plane"
            assert linked_image.plane.position == (5.0, 0.0, 0.0)

    def test_chain_button_follows_the_picked_image(self, linked, viewer):
        widget, _, layers = linked
        sliders = widget.plane_sliders
        viewer.add_image(np.random.random(layers.seg_layer.data.shape), name="raw 2")

        sliders.link_dropdown.setCurrentText("raw")
        sliders.link_btn.setChecked(True)
        sliders.link_dropdown.setCurrentText("raw 2")
        assert not sliders.link_btn.isChecked()
        sliders.link_dropdown.setCurrentText("raw")
        assert sliders.link_btn.isChecked()

    def test_linked_images_are_marked_in_the_dropdown(self, linked, viewer):
        widget, _, layers = linked
        sliders = widget.plane_sliders
        dropdown = sliders.link_dropdown
        viewer.add_image(np.random.random(layers.seg_layer.data.shape), name="raw 2")

        dropdown.setCurrentText("raw")
        sliders.link_btn.setChecked(True)

        def marked():
            return {
                dropdown.itemText(i)
                for i in range(dropdown.count())
                if not dropdown.itemIcon(i).isNull()
            }

        assert marked() == {"raw"}
        # the marker survives the dropdown being rebuilt
        viewer.add_image(np.zeros((2, 3, 4, 5)), name="another")
        assert marked() == {"raw"}

        sliders.link_btn.setChecked(False)
        assert marked() == set()

    def test_unlinking_one_image_keeps_the_other(self, linked, viewer):
        widget, image, layers = linked
        sliders = widget.plane_sliders
        second = viewer.add_image(
            np.random.random(layers.seg_layer.data.shape), name="raw 2"
        )
        viewer.layers.selection.active = layers.seg_layer  # adding selected the image
        sliders._set_mode("plane")
        for name in ("raw", "raw 2"):
            sliders.link_dropdown.setCurrentText(name)
            sliders.link_btn.setChecked(True)

        sliders.link_dropdown.setCurrentText("raw")
        sliders.link_btn.setChecked(False)

        assert sliders.linked_images == [second]
        assert image.depiction == "volume"
        assert second.depiction == "plane"
