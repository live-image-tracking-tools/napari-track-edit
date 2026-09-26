from collections.abc import Callable

from psygnal import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class RefreshingComboBox(QComboBox):
    """A QComboBox that calls a refresh function before showing its popup."""

    def __init__(self, refresh_func: Callable[[], None] | None = None):
        super().__init__()
        self.refresh_func = refresh_func

    def showPopup(self):
        if self.refresh_func is not None:
            self.refresh_func()
        super().showPopup()


class TreeViewFeatureWidget(QWidget):
    """Widget to switch between viewing all nodes versus nodes of one or more lineages in the tree widget"""

    change_plot_type = Signal(str)

    def __init__(
        self, features: list[str], get_features: Callable[[], list[str]] | None = None
    ):
        super().__init__()

        self.plot_type = "tree"
        self.get_features = get_features

        display_box = QGroupBox("Plot [W]")
        display_layout = QHBoxLayout()
        button_group = QButtonGroup()
        self.show_tree_radio = QRadioButton("Lineage Tree")
        self.show_tree_radio.setChecked(True)
        self.show_tree_radio.clicked.connect(lambda: self._set_plot_type("tree"))
        self.show_area_radio = QRadioButton("Feature")
        self.show_area_radio.clicked.connect(lambda: self._set_plot_type("feature"))
        button_group.addButton(self.show_tree_radio)
        button_group.addButton(self.show_area_radio)
        display_layout.addWidget(self.show_tree_radio)
        display_layout.addWidget(self.show_area_radio)

        self.feature_dropdown = RefreshingComboBox(self._refresh_features)
        for feature in features:
            self.feature_dropdown.addItem(feature)
        self.feature_dropdown.currentIndexChanged.connect(self._update_feature)
        if len(features) > 0:
            self.current_feature = features[0]
        else:
            self.current_feature = None
            self.show_area_radio.setEnabled(False)
        display_layout.addWidget(self.feature_dropdown)

        display_box.setLayout(display_layout)
        display_box.setMaximumWidth(400)
        display_box.setMaximumHeight(60)

        layout = QVBoxLayout()
        layout.addWidget(display_box)

        self.setLayout(layout)

    def _toggle_plot_type(self, event=None) -> None:
        """Toggle display mode"""

        if (
            self.show_area_radio.isEnabled
        ):  # if button is disabled, toggle is not allowed
            if self.plot_type == "feature":
                self._set_plot_type("tree")
                self.show_tree_radio.setChecked(True)
            else:
                self._set_plot_type("feature")
                self.show_area_radio.setChecked(True)

    def _set_plot_type(self, plot_type: str):
        """Emit signal to change the display mode"""

        self.plot_type = plot_type
        self.change_plot_type.emit(plot_type)

    def _update_feature(self) -> None:
        """Update the feature to be plotted if the plot_type == 'feature'"""

        self.current_feature = self.feature_dropdown.currentText()
        self.change_plot_type.emit(self.plot_type)

    def get_current_feature(self):
        """Return the current feature that is being plotted"""

        return self.current_feature

    def update_feature_dropdown(self, feature_list: list[str]) -> None:
        """Update the list of features in the dropdown"""

        self.feature_dropdown.currentIndexChanged.disconnect(self._update_feature)
        self.feature_dropdown.clear()
        self.show_area_radio.setEnabled(True)
        for feature in feature_list:
            self.feature_dropdown.addItem(feature)

        if self.current_feature not in feature_list:
            if len(feature_list) > 0:
                self.current_feature = feature_list[0]
                self.feature_dropdown.setCurrentIndex(0)
            else:
                self.current_feature = None
                self.show_area_radio.setEnabled(False)
        else:
            self.feature_dropdown.setCurrentIndex(
                self.feature_dropdown.findText(self.current_feature)
            )

        self.feature_dropdown.currentIndexChanged.connect(self._update_feature)

    def _refresh_features(self) -> None:
        """Refresh the feature dropdown from the get_features callable."""
        if self.get_features is not None:
            feature_list = self.get_features()
            self.update_feature_dropdown(feature_list)
