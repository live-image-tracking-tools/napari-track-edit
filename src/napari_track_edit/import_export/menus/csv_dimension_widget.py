from psygnal import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class DimensionWidget(QWidget):
    """Widget to specify whether to import 2D+time or 3D+time data."""

    update_dims = Signal()

    def __init__(self):
        super().__init__()

        self.incl_z = False

        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)

        self.radio_2D = QRadioButton("2D + Time")
        self.radio_2D.setChecked(True)
        self.radio_3D = QRadioButton("3D + Time")
        self.button_group.addButton(self.radio_2D)
        self.button_group.addButton(self.radio_3D)
        self.radio_2D.toggled.connect(self._toggle_dims)
        self.radio_3D.toggled.connect(self._toggle_dims)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.radio_2D)
        radio_layout.addWidget(self.radio_3D)

        box_layout = QVBoxLayout()
        box_layout.addLayout(radio_layout)
        box = QGroupBox("Dimensions")
        box.setLayout(box_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(box)
        self.setLayout(main_layout)

    def _toggle_dims(self) -> None:
        """Check the dimensions indicated by the user and set self.incl_z to True or False"""

        if self.radio_2D.isChecked():
            self.incl_z = False
        else:
            self.incl_z = True

        self.update_dims.emit()
