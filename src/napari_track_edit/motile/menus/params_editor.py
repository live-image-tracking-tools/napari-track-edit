from functools import partial
from types import NoneType
from typing import get_args, get_origin

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from napari_track_edit.motile.backend import SolverParams

from .param_values import EditableParamValue


def _get_base_type(annotation: type) -> type:
    """Extract the base numeric type from a type annotation.

    For example:
        int -> int
        float -> float
        int | None -> int
        float | None -> float
    """
    # Check if it's a Union type (e.g., int | None)
    if get_origin(annotation) is not None:
        args = get_args(annotation)
        # Filter out NoneType and return the first remaining type
        for arg in args:
            if arg is not NoneType:
                return arg
    return annotation


class EditableParam(QWidget):
    def __init__(
        self,
        param_name: str,
        solver_params: SolverParams,
        negative: bool = False,
    ):
        """A widget for editing a parameter. Can be updated from
        the backend by calling update_from_params with a new SolverParams
        object. If changed in the UI, will emit a send_value signal which can
        be used to keep a SolverParams object in sync.

        Args:
            param_name (str): The name of the parameter to view in this UI row.
                Must correspond to one of the attributes of SolverParams.
            solver_params (SolverParams): The SolverParams object to use to
                initialize the view. Provides the title to display and the
                initial value.
            negative (bool, optional): Whether to allow negative values for
                this parameter. Defaults to False.
        """
        super().__init__()
        self.param_name = param_name
        field = type(solver_params).model_fields[param_name]
        self.dtype = _get_base_type(field.annotation)
        self.title = field.title
        self.negative = negative
        self.param_label = self._param_label_widget()
        self.param_label.setToolTip(field.description)
        self.param_value = EditableParamValue(self.dtype, self.negative)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.param_label)
        layout.addWidget(self.param_value)
        self.setLayout(layout)
        self.setMinimumHeight(32)

        self.update_from_params(solver_params)

    def _param_label_widget(self) -> QLabel:
        return QLabel(self.title)

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            raise ValueError("Got None for required field {self.param_name}")
        else:
            self.param_value.update_value(param_val)


class OptionalEditableParam(EditableParam):
    def __init__(
        self,
        param_name: str,
        solver_params: SolverParams,
        negative: bool = False,
    ):
        """A widget for holding optional editable parameters. Adds a checkbox
        to the label, which toggles None-ness of the value.

        Args:
            param_name (str): _description_
            solver_params (SolverParams): _description_
            negative (bool, optional): _description_. Defaults to False.
        """
        # Get ui_default before calling super().__init__ (which calls update_from_params)
        field = type(solver_params).model_fields[param_name]
        extra = field.json_schema_extra or {}
        self.ui_default = extra.get("ui_default", 0)

        super().__init__(param_name, solver_params, negative)
        self.param_label.toggled.connect(self.toggle_enable)

    def _param_label_widget(self) -> QCheckBox:
        qlabel = QCheckBox(self.title)
        qlabel.setMinimumHeight(32)
        return qlabel

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            self.param_label.setChecked(False)
            self.param_value.setEnabled(False)
            # Show ui_default in the disabled spinbox
            self.param_value.update_value(self.ui_default)
        else:
            self.param_label.setChecked(True)
            self.param_value.setEnabled(True)
            self.param_value.update_value(param_val)

    def toggle_enable(self, checked: bool):
        self.param_value.setEnabled(checked)
        value = self.param_value.get_value() if checked else None
        # force the parameter to say that the value has changed when we toggle
        self.param_value.valueChanged.emit(value)

    def toggle_visible(self, visible: bool):
        self.setVisible(visible)
        if visible and self.param_label.isChecked():
            value = self.param_value.get_value()
        else:
            value = None
        self.param_value.valueChanged.emit(value)


class SolverParamsEditor(QWidget):
    """Widget for editing SolverParams.
    Spinboxes will be created for each parameter in SolverParams and linked such that
    editing the value in the spinbox will change the corresponding parameter.
    Checkboxes will also  be created for each optional parameter (group) and linked such
    that unchecking the box will update the parameter value to None, and checking will
    update the parameter to the current spinbox value.
    To update for a backend change to SolverParams, emit the new_params signal,
    which the spinboxes and checkboxes will connect to and use to update the
    UI and thus the stored solver params.
    """

    new_params = Signal(SolverParams)

    def __init__(self):
        super().__init__()
        self.solver_params = SolverParams()
        self.param_categories = {
            "hyperparams": ["max_edge_distance", "max_children"],
            "constant_costs": [
                "edge_selection_cost",
                "appear_cost",
                "division_cost",
            ],
            "attribute_costs": [
                "distance_cost",
                "iou_cost",
            ],
            "chunking": [
                "window_size",
                "overlap_size",
                "single_window_start",
            ],
        }
        self.iou_row: OptionalEditableParam
        self.window_size_row: OptionalEditableParam
        self.overlap_size_row: OptionalEditableParam
        self.single_window_start_row: OptionalEditableParam

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(
            self._params_group("Hyperparameters", "hyperparams", negative=False)
        )
        main_layout.addWidget(
            self._params_group("Constant Costs", "constant_costs", negative=True)
        )
        main_layout.addWidget(
            self._params_group("Attribute Weights", "attribute_costs", negative=True)
        )
        main_layout.addWidget(
            self._params_group("Chunked Solving", "chunking", negative=False)
        )
        self.setLayout(main_layout)

        # Set up cross-field validation for chunking parameters
        self._setup_chunking_constraints()

    def _params_group(self, title: str, param_category: str, negative: bool) -> QWidget:
        widget = QGroupBox(title)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        # layout.addWidget(QLabel(title))
        for param_name in self.param_categories[param_category]:
            field = type(self.solver_params).model_fields[param_name]
            param_cls = (
                OptionalEditableParam
                if issubclass(NoneType, field.annotation)
                else EditableParam
            )
            param_row = param_cls(param_name, self.solver_params, negative=negative)
            param_row.param_value.valueChanged.connect(
                partial(self.solver_params.__setattr__, param_name)
            )
            self.new_params.connect(param_row.update_from_params)
            if param_name == "iou_cost":
                self.iou_row = param_row
            elif param_name == "window_size":
                self.window_size_row = param_row
            elif param_name == "overlap_size":
                self.overlap_size_row = param_row
            elif param_name == "single_window_start":
                self.single_window_start_row = param_row
            layout.addWidget(param_row)
        widget.setLayout(layout)
        return widget

    def _setup_chunking_constraints(self) -> None:
        """Set up validation constraints for chunking fields."""
        # Track which chunking mode was last used (overlap=chunked, single_window_start=single)
        # Default to overlap (chunked solving)
        self._last_chunking_mode = "overlap"

        # Set window_size minimum to 2
        self.window_size_row.param_value.setMinimum(2)

        # Set overlap_size minimum to 1
        self.overlap_size_row.param_value.setMinimum(1)

        # When window_size value changes, update overlap_size max
        self.window_size_row.param_value.valueChanged.connect(
            self._update_overlap_constraints
        )

        # When window_size checkbox toggles, enable/disable dependent fields
        self.window_size_row.param_label.toggled.connect(self._toggle_chunking_fields)

        # Mutual exclusion: overlap_size and single_window_start
        self.overlap_size_row.param_label.toggled.connect(self._on_overlap_toggled)
        self.single_window_start_row.param_label.toggled.connect(
            self._on_single_window_toggled
        )

        # Initialize state: disable dependent fields if window_size is unchecked
        if not self.window_size_row.param_label.isChecked():
            self.overlap_size_row.setEnabled(False)
            self.single_window_start_row.setEnabled(False)

    def _update_overlap_constraints(self, window_size: int | None) -> None:
        """Update overlap_size spinbox maximum based on window_size."""
        if window_size is not None and window_size > 1:
            self.overlap_size_row.param_value.setMaximum(window_size - 1)
            # Clamp current value if needed
            if self.overlap_size_row.param_value.value() >= window_size:
                self.overlap_size_row.param_value.setValue(window_size - 1)

    def _toggle_chunking_fields(self, enabled: bool) -> None:
        """Enable/disable overlap_size and single_window_start based on window_size."""
        self.overlap_size_row.setEnabled(enabled)
        self.single_window_start_row.setEnabled(enabled)
        if enabled:
            # Auto-check the last used chunking mode
            if self._last_chunking_mode == "overlap":
                self.overlap_size_row.param_label.setChecked(True)
            else:
                self.single_window_start_row.param_label.setChecked(True)
        else:
            # Uncheck dependent fields so they emit None
            self.overlap_size_row.param_label.setChecked(False)
            self.single_window_start_row.param_label.setChecked(False)

    def _on_overlap_toggled(self, checked: bool) -> None:
        """When overlap_size is checked, uncheck single_window_start and remember choice."""
        if checked:
            self._last_chunking_mode = "overlap"
            self.single_window_start_row.param_label.setChecked(False)

    def _on_single_window_toggled(self, checked: bool) -> None:
        """When single_window_start is checked, uncheck overlap_size and remember choice."""
        if checked:
            self._last_chunking_mode = "single_window"
            self.overlap_size_row.param_label.setChecked(False)

    def set_max_frames(self, max_frame: int) -> None:
        """Set the maximum frame index for single_window_start.

        Args:
            max_frame: The maximum valid frame index (typically num_frames - 1).
        """
        # single_window_start can be at most max_frame - 1 (need at least 2 frames)
        max_start = max(0, max_frame - 1)
        self.single_window_start_row.param_value.setMaximum(max_start)
        # Clamp current value if needed
        if self.single_window_start_row.param_value.value() > max_start:
            self.single_window_start_row.param_value.setValue(max_start)
