import contextlib

import napari
import numpy as np
from psygnal import Signal
from qtpy.QtCore import QSignalBlocker, QSize, Qt
from qtpy.QtGui import QIcon, QImage, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledDoubleSlider

from napari_track_edit._nte_app import NTEApp
from napari_track_edit.data_views.colormap import (
    SAME_AS_NODES,
    colormap_choices,
    edge_color_feature_keys,
    feature_display_name,
    node_color_feature_keys,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


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


_PREVIEW_ROLE = Qt.UserRole + 1  # item data role holding a colormap's preview
_ARROW_WIDTH = 20  # room left for a combo box's drop-down arrow


def _preview_pixmap(colors: np.ndarray) -> QPixmap:
    """A strip showing `colors` (N, 3, floats in 0-1) side by side: a smooth
    gradient for many colors, swatches for a palette. Drawn stretched to
    whatever space it is given (see `_ColormapCombo`)."""
    width, height = 256, 1
    columns = np.floor(np.linspace(0, len(colors), width, endpoint=False)).astype(int)
    rgb = (np.clip(colors[columns], 0, 1) * 255).astype(np.uint8)
    pixels = np.ascontiguousarray(np.repeat(rgb[np.newaxis], height, axis=0))
    image = QImage(pixels.data, width, height, 3 * width, QImage.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class _PreviewDelegate(QStyledItemDelegate):
    """Draws a colormap preview across the whole row of the picker's list.

    A preview set as an item icon is squeezed into the small square icon area
    napari's style allows, so it is drawn here instead.
    """

    ROW_HEIGHT = 24

    def paint(self, painter, option, index) -> None:
        # the row background (hover, selection) without any text or icon
        self.initStyleOption(option, index)
        option.text = ""
        option.icon = QIcon()
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
        pixmap = index.data(_PREVIEW_ROLE)
        if pixmap is not None:
            painter.drawPixmap(option.rect.adjusted(8, 5, -8, -5), pixmap)

    def sizeHint(self, option, index) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), self.ROW_HEIGHT))


class _ColormapCombo(QComboBox):
    """A combo box showing colormap previews instead of names, both in its
    list and in the closed box."""

    def __init__(self):
        super().__init__()
        self.setItemDelegate(_PreviewDelegate(self))

    def add_preview(self, colors: np.ndarray, name: str) -> None:
        self.addItem("", name)
        self.setItemData(self.count() - 1, _preview_pixmap(colors), _PREVIEW_ROLE)

    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = ""
        option.currentIcon = QIcon()
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        pixmap = self.currentData(_PREVIEW_ROLE)
        if pixmap is not None:
            # everything left of the drop-down arrow. Not the style's edit
            # field or arrow rects: under napari's stylesheet those leave a
            # strip a fraction of the box wide.
            field = self.rect().adjusted(8, 7, -(8 + _ARROW_WIDTH), -7)
            painter.drawPixmap(field, pixmap)


class FeatureColorByWidget(QWidget):
    """A "Color ... by" label and the dropdown picking the feature to color by.

    Shared by `NodeColorByWidget` and `EdgeColorByWidget`, which say which
    features to offer (`_keys`), what to call them (`_display_name`), and how
    to read and set the one in use on the `TracksViewer` (`_current`,
    `_apply`).

    Next to it, a colormap picker (`colormap_combo`) lists the colormaps the
    current feature's colors can switch between (gradients for numbers,
    palettes for categories; see `colormap_choices`), and is hidden when there
    are none. napari's "shuffle colors" button steps through the same list
    for node colors, and the picker follows.
    """

    LABEL = ""
    TOOLTIP = ""

    def __init__(self, tracks_viewer: TracksViewer):
        super().__init__()

        self.tracks_viewer = tracks_viewer
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        # what the two combos currently list, so _populate can skip rebuilding
        self._shown_entries: list = []
        self._shown_colormaps: tuple[list, list] = ([], [])

        self.combo = QComboBox()
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.setToolTip(self.TOOLTIP)
        self.combo.currentIndexChanged.connect(self._on_selected)

        self.colormap_combo = _ColormapCombo()
        self.colormap_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.colormap_combo.currentIndexChanged.connect(self._on_colormap_selected)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)
        self.label = QLabel(self.LABEL)
        layout.addWidget(self.label)
        layout.addWidget(self.combo, stretch=2)
        layout.addWidget(self.colormap_combo, stretch=1)

        self.tracks_viewer.tracks_updated.connect(self._populate)
        self.tracks_viewer.colormap_updated.connect(self._populate)
        self._populate()

    def showEvent(self, event):
        # To ensure that the groups are up to date
        self._populate()
        super().showEvent(event)

    def _keys(self) -> list[str | None]:
        raise NotImplementedError

    def _display_name(self, key: str | None) -> str:
        return feature_display_name(self.tracks_viewer.tracks, key)

    def _current(self) -> str | None:
        raise NotImplementedError

    def _apply(self, key: str | None) -> None:
        raise NotImplementedError

    def _color_source(self):
        """The color source of the feature in use, or None."""
        raise NotImplementedError

    def _apply_colormap(self, name: str) -> None:
        raise NotImplementedError

    def _populate(self, *_args) -> None:
        """Rebuild the entries and show the feature currently in use."""

        keys = self._keys()
        entries = [(self._display_name(key), key) for key in keys]
        current = self._current()
        with QSignalBlocker(self.combo):
            # rebuilt only when the entries changed: this runs after every
            # edit, and clearing the combo would close it if it is open
            if entries != self._shown_entries:
                self.combo.clear()
                for name, key in entries:
                    self.combo.addItem(name, key)
                self._shown_entries = entries
            self.combo.setCurrentIndex(keys.index(current) if current in keys else 0)
        self.combo.setEnabled(self.tracks_viewer.tracks is not None)
        self._populate_colormaps()

    def _populate_colormaps(self) -> None:
        """List the current feature's colormaps and show the one in use."""
        source = self._color_source()
        choices = colormap_choices(source)
        previews = [np.asarray(source.preview(name)) for name in choices]
        with QSignalBlocker(self.colormap_combo):
            # as for the feature combo: only rebuilt when something changed
            # (a shuffle changes the "random" id preview, so compare colors)
            shown_names, shown_previews = self._shown_colormaps
            unchanged = list(choices) == shown_names and all(
                a.shape == b.shape and np.array_equal(a, b)
                for a, b in zip(previews, shown_previews, strict=True)
            )
            if not unchanged:
                self.colormap_combo.clear()
                for name, preview in zip(choices, previews, strict=True):
                    # the colors only, no name
                    self.colormap_combo.add_preview(preview, name)
                self._shown_colormaps = (list(choices), previews)
            if choices and source.choice in choices:
                self.colormap_combo.setCurrentIndex(choices.index(source.choice))
        self.colormap_combo.setVisible(
            bool(choices) and self.tracks_viewer.tracks is not None
        )

    def _on_colormap_selected(self, index: int) -> None:
        if index < 0:
            return
        name = self.colormap_combo.itemData(index)
        source = self._color_source()
        if source is not None and name != getattr(source, "choice", None):
            self._apply_colormap(name)

    def _on_selected(self, index: int) -> None:
        if index < 0:
            return
        feature_key = self.combo.itemData(index)
        if feature_key != self._current():
            self._apply(feature_key)

    def cleanup(self) -> None:
        """Stop following the TracksViewer, which outlives this widget."""
        for signal in (
            self.tracks_viewer.tracks_updated,
            self.tracks_viewer.colormap_updated,
        ):
            with contextlib.suppress(ValueError, KeyError, RuntimeError):
                signal.disconnect(self._populate)


class NodeColorByWidget(FeatureColorByWidget):
    """The "Color nodes by" dropdown: the node feature that colors the labels,
    points, tracks, tree and table (see `TracksViewer.set_node_color_feature`).

    Offers "None" (one flat color), then the categorical features and the
    numeric ones, shown as a gradient (see `node_color_feature_keys`).
    """

    LABEL = "Color nodes by"
    TOOLTIP = "Node feature used to color the labels, points, tracks, tree and table."

    def _keys(self) -> list[str | None]:
        return [None, *node_color_feature_keys(self.tracks_viewer.tracks)]

    def _current(self) -> str | None:
        return self.tracks_viewer.node_color_feature_key

    def _apply(self, key: str | None) -> None:
        self.tracks_viewer.set_node_color_feature(key)

    def _color_source(self):
        return self.tracks_viewer.node_colormap.color_source

    def _apply_colormap(self, name: str) -> None:
        self.tracks_viewer.set_node_colormap_choice(name)


class EdgeColorByWidget(FeatureColorByWidget):
    """The "Color edges by" dropdown: the edge feature that colors the edges in
    the lineage view (see `TracksViewer.set_edge_color_feature`).

    Offers "Same as nodes" (each edge in its child node's color, the default),
    "None" (one flat color), then the bool and numeric edge features (see
    `edge_color_feature_keys`).
    """

    LABEL = "Color edges by"
    TOOLTIP = (
        "Edge feature used to color the edges in the lineage view. The napari "
        "Tracks layer keeps the node colors."
    )

    def _keys(self) -> list[str | None]:
        return [
            SAME_AS_NODES,
            None,
            *edge_color_feature_keys(self.tracks_viewer.tracks),
        ]

    def _display_name(self, key: str | None) -> str:
        if key == SAME_AS_NODES:
            return "Same as nodes"
        return super()._display_name(key)

    def _current(self) -> str | None:
        return self.tracks_viewer.edge_color_feature_key

    def _apply(self, key: str | None) -> None:
        self.tracks_viewer.set_edge_color_feature(key)

    def _color_source(self):
        return self.tracks_viewer.edge_colormap.color_source

    def _apply_colormap(self, name: str) -> None:
        self.tracks_viewer.set_edge_colormap_choice(name)


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
        self.app = NTEApp.get_instance(viewer)
        self.tracks_viewer = self.app.tracks_viewer

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

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

        self.node_color_by_widget = NodeColorByWidget(self.tracks_viewer)
        self.edge_color_by_widget = EdgeColorByWidget(self.tracks_viewer)

        main_layout.addWidget(self.mode_widget)
        main_layout.addWidget(self.highlight_widget)
        main_layout.addWidget(self.foreground_widget)
        main_layout.addWidget(self.background_widget)

        main_layout.addWidget(self.node_color_by_widget)
        main_layout.addWidget(self.edge_color_by_widget)

        self.show_ortho_views = QCheckBox("Orthogonal views")
        self.show_ortho_views.toggled.connect(self.toggle_ortho_views)
        self.show_ortho_views.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # the ortho views outlive this widget, so pick them up again when it is reopened
        self.show_ortho_views.setChecked(self.app.config.orthoviews_enabled)

        self.show_viewer_overlay = QCheckBox("Display keybinds on canvas")
        self.show_viewer_overlay.setChecked(self.app.text_overlay_visible)
        self.show_viewer_overlay.toggled.connect(self.toggle_viewer_text_overlay)

        main_layout.addWidget(self.show_ortho_views)
        main_layout.addWidget(self.show_viewer_overlay)
        main_layout.addStretch(1)

    def cleanup(self) -> None:
        """Stop following the TracksViewer, which outlives this widget.

        Called by MenuManager when the dock is destroyed.
        """

        with contextlib.suppress(ValueError, KeyError, RuntimeError):
            self.tracks_viewer.mode_updated.disconnect(self._update_widget_availability)
        self.node_color_by_widget.cleanup()
        self.edge_color_by_widget.cleanup()

    def toggle_viewer_text_overlay(self, checked: bool):
        """Change the visibility of the text overlay"""

        self.app.text_overlay_visible = checked

    def toggle_ortho_views(self, checked: bool):
        """Show or hide the ortho views, creating them the first time."""

        if not checked and self.app.config.orthoviews_enabled is False:
            return  # never shown yet, nothing to hide

        if checked:
            self.app.ortho_views.show()
        else:
            self.app.ortho_views.hide()

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
        """Apply the values from the widget and send an update signal.

        Returns without touching the layer when the widgets already agree with
        it. This runs on every `mode_updated`, which includes pressing Q - and
        there only the *enabled* state of these widgets changes, never their
        values. Applying them anyway triggers a second `update_selection`, and
        each one re-slices the whole displayed volume: 6 s in 3D on a
        1.7e9-voxel timepoint, for a result identical to the refresh
        `set_display_mode` has already done.
        """

        layer = self.tracks_viewer.tracking_layers.seg_layer

        if layer is None:
            return

        wanted = (
            self.highlight_widget.opacity.value(),
            self.foreground_widget.opacity.value(),
            self.background_widget.opacity.value(),
            not self.highlight_widget.contour.isChecked(),
            not self.foreground_widget.contour.isChecked(),
        )
        current = (
            layer.highlight_opacity,
            layer.foreground_opacity,
            layer.background_opacity,
            layer.highlight_contour,
            layer.foreground_contour,
        )
        if wanted == current:
            return

        (
            layer.highlight_opacity,
            layer.foreground_opacity,
            layer.background_opacity,
            layer.highlight_contour,
            layer.foreground_contour,
        ) = wanted
        self.tracks_viewer.update_selection(set_view=False)
