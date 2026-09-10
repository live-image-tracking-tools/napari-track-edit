from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.import_export.menus.geff_import_utils import (
    clear_layout,
)


class ScaleWidget(QWidget):
    """Widget to specify the spatial scaling of the graph in relation to its segmentation
    data."""

    def __init__(self) -> None:
        super().__init__()

        self.scale = None
        self.scale_layout = QVBoxLayout()
        box = QGroupBox("Scaling")
        box.setLayout(self.scale_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(box)
        main_layout.setAlignment(Qt.AlignTop)

        self.setLayout(main_layout)
        self.setToolTip(
            "<html><body><p style='white-space:pre-wrap; width: 300px;'>"
            "Specify the spatial scaling (pixel to world coordinate) in relation to "
            "the segmentation data, if provided."
        )
        self.setVisible(False)

    def update(
        self,
        metadata: dict | None = None,
        incl_z: bool = False,
        scale: list[float] | None = None,
    ) -> None:
        """
        Add widgets to the layout, prefilled from available information if possible

        Args:
            metadata (dict): geff metadata dictionary containing 'axes' key with scaling
                information.
            incl_z (bool): whether to include 'z' (provide this if metadata is not
                available)
            scale (list[float] | None): an already-resolved scale ([t, (z), y, x]) to
                prefill with, e.g. read from the scale columns of a CSV. Takes
                precedence over the geff metadata.
        """

        axes = metadata.get("axes") if metadata is not None else None

        # A scale whose dimensionality disagrees with the one the user picked is
        # not usable here, so fall through to the other sources.
        if scale is not None and len(scale) == (4 if incl_z else 3):
            self.scale = [float(s) for s in scale]

        elif axes:
            lookup = {a["name"].lower(): a.get("scale", 1) or 1 for a in axes}
            self.scale = [1.0] * len(axes)  # time + spatial dims
            self.scale[-1], self.scale[-2] = lookup.get("x", 1), lookup.get("y", 1)
            if len(self.scale) == 4:
                self.scale[-3] = lookup.get("z", 1)

        else:
            ndim = 4 if incl_z else 3
            self.scale = list([1.0] * ndim)

        clear_layout(self.scale_layout)
        self.scale_form_layout = QFormLayout()

        # Spinboxes for scaling in (z), y, x.
        self.z_label = QLabel("z")
        self.z_spin_box = self._scale_spin_box(self.scale[-3])
        self.z_label.setVisible(len(self.scale) == 4)
        self.z_spin_box.setVisible(len(self.scale) == 4)
        self.y_spin_box = self._scale_spin_box(self.scale[-2])
        self.x_spin_box = self._scale_spin_box(self.scale[-1])

        self.scale_form_layout.addRow(self.z_label, self.z_spin_box)
        self.scale_form_layout.addRow(QLabel("y"), self.y_spin_box)
        self.scale_form_layout.addRow(QLabel("x"), self.x_spin_box)

        self.scale_layout.addLayout(self.scale_form_layout)
        self.setVisible(True)

    def _scale_spin_box(self, value: float) -> QDoubleSpinBox:
        """Return a QDoubleSpinBox for scaling values"""

        spin_box = QDoubleSpinBox()
        spin_box.setDecimals(4)
        spin_box.setMinimum(0)
        spin_box.setMaximum(1e6)
        spin_box.setSingleStep(0.1)
        spin_box.setValue(value)
        return spin_box

    def get_scale(self) -> list[float] | None:
        """Return the scaling values in the spinboxes as a list of floats.

        Returns 1 for the time dimension, and then the spatial scales based on
        whether the data is 3D (time, y, x) or 4D (time, z, y, x).

        Returns None if the scale widget hasn't been initialized (no segmentation).
        """
        if self.scale is None:
            return None

        if len(self.scale) == 4:
            # 4D data
            scale = [
                1,
                self.z_spin_box.value(),
                self.y_spin_box.value(),
                self.x_spin_box.value(),
            ]
        else:
            # 3D data
            scale = [
                1,
                self.y_spin_box.value(),
                self.x_spin_box.value(),
            ]

        return scale
