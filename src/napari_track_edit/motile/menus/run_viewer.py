from __future__ import annotations

from functools import partial

import pyqtgraph as pg
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible, ensure_main_thread

from napari_track_edit.motile.backend import MotileRun

from .params_viewer import SolverParamsViewer


class RunViewer(QGroupBox):
    """A widget for viewing in progress or completed runs, including
    the progress of the solver and the parameters.
    Output tracks and segmentation are visualized separately in napari layers.
    """

    edit_run = Signal(object)

    def __init__(self):
        super().__init__(title="Run Viewer")

        # define attributes
        self.run: MotileRun | None = None
        self.params_widget = SolverParamsViewer()
        self.solver_label: QLabel
        self.gap_plot: pg.PlotWidget

        # Create layout and add subwidgets
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._progress_widget())
        main_layout.addWidget(self.params_widget)
        main_layout.addWidget(self._back_to_edit_widget())
        self.setLayout(main_layout)

    def update_run(self, run: MotileRun):
        """Update the run being viewed. Changes the title, solver status and
        gap plot, and parameters being displayed.

        Args:
            run (MotileRun): The new run to display
        """
        self.run = run
        run_time = run.time.strftime("%m/%d/%y, %H:%M:%S")
        run_name_view = f"{run.run_name} ({run_time})"
        self.setTitle("Run Viewer: " + run_name_view)
        self.solver_event_update()
        # A run loaded from a directory with no params file has no
        # solver_params — hide the params display rather than emit None into
        # widgets that can't render it.
        if run.solver_params is None:
            self.params_widget.hide()
        else:
            self.params_widget.show()
            self.params_widget.new_params.emit(run.solver_params)

    def _back_to_edit_widget(self) -> QWidget:
        """Create a widget for navigating back to the run editor with different
        parameters.

        Returns:
            QWidget: A widget with two buttons: one for navigating back to the
                previous run editor state, and one for populating the run
                editor with the currently viewed run's parameters.
        """
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # create back to editing button
        edit_run_button = QPushButton("Back to editing")
        edit_run_button.clicked.connect(partial(self.edit_run.emit, None))
        layout.addWidget(edit_run_button)

        # new run from this config button
        run_from_config_button = QPushButton("Edit this run")
        run_from_config_button.clicked.connect(self._emit_run)
        layout.addWidget(run_from_config_button)

        widget.setLayout(layout)
        return widget

    def _emit_run(self):
        """Emit the edit_run signal with the current run. Used to populate
        the run editor with the current run's parameters.
        """
        self.edit_run.emit(self.run)  # Note: this may cause memory leak
        # Can use weakref if that happens
        # https://github.com/Carreau/napari/commit/cd079e9dcb62de115833ea1b6bb1b7a0ab4b78d1

    def _progress_widget(self) -> QWidget:
        """Create a widget containing solver progress and status.

        Returns:
            QWidget: A widget with a label indicating solver status and
                a collapsible graph of the solver gap.
        """
        widget = QWidget()
        layout = QVBoxLayout()

        self.solver_label = QLabel("")
        self.gap_plot = self._plot_widget()
        collapsable_plot = QCollapsible("Graph of solver gap")
        collapsable_plot.layout().setContentsMargins(0, 0, 0, 0)
        collapsable_plot.addWidget(self.gap_plot)
        collapsable_plot.collapse(animate=False)

        layout.addWidget(self.solver_label)
        layout.addWidget(collapsable_plot)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        return widget

    def _plot_widget(self) -> pg.PlotWidget:
        """
        Returns:
            pg.PlotWidget: a widget containg an (empty) plot of the solver gap
        """
        gap_plot = pg.PlotWidget()
        gap_plot.setBackground((37, 41, 49))
        styles = {
            "color": "white",
        }
        gap_plot.plotItem.setLogMode(x=False, y=True)
        gap_plot.plotItem.setLabel("left", "Gap", **styles)
        gap_plot.plotItem.setLabel("bottom", "Solver round", **styles)
        return gap_plot

    def _set_solver_label(self, status: str):
        message = "Solver status: " + status
        self.solver_label.setText(message)

    @ensure_main_thread
    def solver_event_update(self):
        self._set_solver_label(self.run.status)
        self.gap_plot.getPlotItem().clear()
        gaps = self.run.gaps
        if gaps is not None and len(gaps) > 0:
            try:
                self.gap_plot.getPlotItem().plot(range(len(gaps)), gaps)
            # note: catching pyqt graph exception about range(len(gaps))
            # and gaps being different lengths. Pyqtgraph uses a generic
            # Exception :( so we check the string
            except Exception as e:
                if "X and Y arrays" not in str(e):
                    raise e

    def reset_progress(self):
        self._set_solver_label("not running")
        self.gap_plot.getPlotItem().clear()
