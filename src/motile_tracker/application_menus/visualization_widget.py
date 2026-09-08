import contextlib

import napari
from napari.layers import Points
from napari.layers.points._points_mouse_bindings import add as napari_add_point
from napari_orthogonal_views.ortho_view_manager import _VIEWER_MANAGERS
from napari_plane_sliders import PlaneSliderWidget
from psygnal import Signal
from qtpy.QtCore import QSignalBlocker
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledDoubleSlider

from motile_tracker.data_views.views.ortho_views import initialize_ortho_views
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class VisualizationConfigWidget(QWidget):
    """Sliders and checkboxes for adjusting the opacity and contour display."""

    update_visualization = Signal()

    def __init__(
        self,
        label: str,
        default_opacity: float,
        default_contour: bool,
        use_contour: bool = True,
    ):
        super().__init__()

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.orth_views_connection = None
        self.orth_view_manager = None

        box = QGroupBox(label)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(8, 6, 8, 6)
        box_layout.setSpacing(6)

        self.opacity = QLabeledDoubleSlider()
        self.opacity.setValue(default_opacity)
        self.opacity.setSingleStep(0.1)
        self.opacity.setRange(0, 1)
        self.opacity.setDecimals(2)
        self.opacity.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.opacity.valueChanged.connect(self.update_visualization)
        box_layout.addWidget(self.opacity)

        self.contour = None
        if use_contour:
            self.contour = QCheckBox("Fill")
            self.contour.setChecked(default_contour)
            self.contour.stateChanged.connect(self.update_visualization)
            self.contour.setEnabled(False)
            self.contour.setVisible(False)
            self.contour.setToolTip(
                "When checked, will fill labels instead of showing contours only"
            )
            self.contour.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            box_layout.addWidget(self.contour)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(box)
        layout.addStretch(0)


class ModeWidget(QWidget):
    """Compact radio buttons for display mode."""

    update_mode = Signal(str)

    def __init__(self):
        super().__init__()

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        box = QGroupBox("Display Mode")
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        self.radio_group = QButtonGroup(self)
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(12, 8, 12, 8)
        box_layout.setSpacing(14)

        for text, mode in [("All", "all"), ("Lineage", "lineage"), ("Group", "group")]:
            btn = QRadioButton(text)
            btn.setProperty("mode", mode)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            btn.setStyleSheet("""
                QRadioButton {
                    padding: 3px 8px;
                }
            """)

            self.radio_group.addButton(btn)
            box_layout.addWidget(btn)

            if mode == "all":
                btn.setChecked(True)

        self.radio_group.buttonToggled.connect(self._on_toggled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(box)

    @property
    def current_mode(self) -> str:
        btn = self.radio_group.checkedButton()
        return btn.property("mode") if btn else None

    def button_for_mode(self, mode: str) -> QRadioButton:
        for btn in self.radio_group.buttons():
            if btn.property("mode") == mode:
                return btn
        raise KeyError(f"No radio button for mode '{mode}'")

    def _on_toggled(self, button, checked):
        if checked:
            self.update_mode.emit(button.property("mode"))


class VisualizationWidget(QWidget):
    """Widget to adjust opacity and contour display in different TrackLabels layer display modes."""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        # Initialize ortho-views attributes
        self.orth_views_connection = None
        self.orth_view_manager = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.tracks_viewer.mode_updated.connect(self._update_widget_availability)

        self.mode_widget = ModeWidget()
        self.mode_widget.update_mode.connect(self._update_mode)

        self.highlight_widget = VisualizationConfigWidget(
            "Highlight opacity", 1.0, True
        )
        self.foreground_widget = VisualizationConfigWidget(
            "Foreground opacity", 0.6, True
        )
        self.background_widget = VisualizationConfigWidget(
            "Background opacity", 0.3, True, use_contour=False
        )

        self.highlight_widget.update_visualization.connect(self._update_visualization)
        self.foreground_widget.update_visualization.connect(self._update_visualization)
        self.background_widget.update_visualization.connect(self._update_visualization)

        self.background_widget.setEnabled(False)  # initially disabled

        main_layout.addWidget(self.mode_widget)
        main_layout.addWidget(self.highlight_widget)
        main_layout.addWidget(self.foreground_widget)
        main_layout.addWidget(self.background_widget)

        self.show_ortho_views = QCheckBox("Orthogonal views")
        self.show_ortho_views.stateChanged.connect(self.initialize_ortho_views)
        self.show_ortho_views.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        main_layout.addWidget(self.show_ortho_views)

        # Plane and clipping plane controls. They act on the layer that is selected in
        # the viewer and on the layers it is linked to, which for the tracking layers
        # means the group linked on their clipping planes by TracksLayerGroup.
        self.plane_sliders = PlaneSliderWidget(self.viewer)
        plane_box = QGroupBox("Plane views")
        plane_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        plane_box_layout = QVBoxLayout(plane_box)
        plane_box_layout.setContentsMargins(8, 6, 8, 6)
        plane_box_layout.setSpacing(6)
        plane_box_layout.addWidget(self.plane_sliders)
        main_layout.addWidget(plane_box)

        main_layout.addStretch(1)

        self.setMaximumHeight(620)

    def cleanup(self) -> None:
        """Detach from the viewer before this widget is destroyed. Idempotent.

        Called by MenuManager when the menu is closed. The plane sliders install
        callbacks and event connections on the viewer itself, which would outlive this
        widget and raise when they touch its deleted Qt children.
        """

        self._disconnect_ortho_views()
        self._disconnect_plane_sliders()

    def _disconnect_plane_sliders(self) -> None:
        """Take the plane sliders back off the viewer and the points layers.

        These reach into `PlaneSliderWidget`, which does not tear itself down; without
        it a reopened Visualization menu leaves the callbacks of the previous one
        behind, pointing at deleted widgets.
        """

        sliders = self.plane_sliders
        with contextlib.suppress(TypeError, RuntimeError, ValueError):
            self.viewer.dims.events.ndisplay.disconnect(sliders.on_ndisplay_changed)
        with contextlib.suppress(TypeError, RuntimeError, ValueError):
            self.viewer.layers.selection.events.changed.disconnect(
                sliders._on_selection_changed
            )

        for callbacks in (
            self.viewer.mouse_move_callbacks,
            self.viewer.mouse_drag_callbacks,
            self.viewer.mouse_double_click_callbacks,
        ):
            with contextlib.suppress(ValueError):
                callbacks.remove(sliders._snap_cursor_to_plane)

        # restore the napari callback on any points layer whose add mode we took over
        for layer in self.viewer.layers:
            if not isinstance(layer, Points):
                continue
            with contextlib.suppress(TypeError, RuntimeError, ValueError):
                layer.events.mode.disconnect(sliders._on_point_mode_changed)
            if sliders._add_point_on_plane in layer.mouse_drag_callbacks:
                layer.mouse_drag_callbacks.remove(sliders._add_point_on_plane)
                if str(layer.mode) == "add":
                    layer.mouse_drag_callbacks.append(napari_add_point)

    def initialize_ortho_views(self, checked: bool):
        """Initializes the ortho views."""

        if self.show_ortho_views.isChecked() != checked:
            # sync checkbox state, since there are two ways to trigger this function (checkbox or menu action in ortho view widget)
            self.show_ortho_views.setChecked(checked)
        if self.viewer in _VIEWER_MANAGERS:
            self.orth_view_manager = _VIEWER_MANAGERS[self.viewer]
            if not checked:
                self.orth_view_manager.hide()
                self.orth_view_manager.set_splitter_sizes(
                    0.0, 0.0
                )  # minimal size for right and bottom
            else:
                self.orth_view_manager.show()
        else:
            self.orth_view_manager = initialize_ortho_views(
                self.viewer
            )  # store to be able to disconnect later
            self.orth_views_connection = (
                self.orth_view_manager.main_controls_widget.show_orth_views.connect(
                    self.initialize_ortho_views
                )
            )
            # remove connection and reset checkbox when destroyed
            self.orth_view_manager.main_controls_widget.destroyed.connect(
                self._on_ortho_cleanup
            )
            self.orth_view_manager.show()

    def _on_ortho_cleanup(self):
        """Called when ortho_view_manager cleans up and deletes its widgets."""
        self._disconnect_ortho_views()
        # Uncheck the checkbox without triggering initialize_ortho_views
        self.show_ortho_views.blockSignals(True)
        self.show_ortho_views.setChecked(False)
        self.show_ortho_views.blockSignals(False)

    def _disconnect_ortho_views(self):
        """Safely disconnect from ortho views signals."""

        if (
            self.orth_views_connection is not None
            and self.orth_view_manager is not None
        ):
            with contextlib.suppress(TypeError, RuntimeError):
                self.orth_view_manager.main_controls_widget.show_orth_views.disconnect(
                    self.orth_views_connection
                )
            self.orth_views_connection = None
        self.orth_view_manager = None

    def _update_mode(self, mode: str) -> None:
        """Update the display mode on the Tracksviewer"""

        self.tracks_viewer.set_display_mode(mode)
        self._update_widget_availability()

    def _update_widget_availability(self):
        """Update the radio buttons, show/hide the contour checkboxes when changing
        between contour and normal mode. Disable the background widget when the display
        mode is 'All', as there are no background labels in that case."""

        # ensure the correct radio button is checked
        mode = self.tracks_viewer.mode
        with QSignalBlocker(self.mode_widget.radio_group):
            self.mode_widget.button_for_mode(self.tracks_viewer.mode).setChecked(True)
        if self.tracks_viewer.tracking_layers.seg_layer is not None:
            self.highlight_widget.setVisible(True)
            self.foreground_widget.setVisible(True)
            self.background_widget.setVisible(True)

            self.background_widget.setEnabled(mode != "all")

            show_contour = (
                self.tracks_viewer.tracking_layers.seg_layer.contour > 0
                and mode != "all"
            )

            for w in (self.highlight_widget, self.foreground_widget):
                w.contour.setVisible(show_contour)
                w.contour.setEnabled(show_contour)

            self._update_visualization()

        else:
            self.highlight_widget.setVisible(False)
            self.foreground_widget.setVisible(False)
            self.background_widget.setVisible(False)

    def _update_visualization(self):
        """Apply the values from the widget and send an update signal."""

        layer = self.tracks_viewer.tracking_layers.seg_layer

        if layer is not None:
            layer.highlight_opacity = self.highlight_widget.opacity.value()
            layer.foreground_opacity = self.foreground_widget.opacity.value()
            layer.background_opacity = self.background_widget.opacity.value()
            layer.highlight_contour = not self.highlight_widget.contour.isChecked()
            layer.foreground_contour = not self.foreground_widget.contour.isChecked()
            self.tracks_viewer.update_selection(set_view=False)
