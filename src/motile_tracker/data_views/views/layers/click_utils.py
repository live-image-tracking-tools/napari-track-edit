import time
from collections.abc import Generator

from napari.layers import Labels, Points
from napari.utils.events import Event
from qtpy.QtCore import Qt
from qtpy.QtGui import QMouseEvent

QT_BUTTON_TO_INT = {
    Qt.BackButton: 4,
    Qt.ForwardButton: 5,
}


def detect_side_button(event: Event | QMouseEvent) -> int | None:
    """Detect if a mouse side button (back/forward) was pressed.

    Args:
        event: The napari mouse event or a Qt QMouseEvent

    Returns:
        MouseButton integer (4: back, 5: forward), or None if not a side button
    """

    # check if the event is a QMouseEvent (button is a callable method)
    button_attr = getattr(event, "button", None)
    if callable(button_attr):
        return QT_BUTTON_TO_INT.get(button_attr())

    # event is a napari Event: button is already an int
    button = button_attr
    return button if button in (4, 5) else None


def detect_click(event: Event) -> Generator[None, None, bool]:
    """Yield during drag, then return True if this was a click."""

    mouse_press_time = time.time()
    dragged = False
    yield  # initial press
    while event.type == "mouse_move":
        dragged = True
        yield
    if dragged and time.time() - mouse_press_time < 0.5:
        dragged = False  # micro drag: treat as click
    return not dragged


def get_click_value(layer: Labels | Points, event: Event) -> int:
    """Return the value (label, point index) at the click location"""

    return layer.get_value(
        event.position,
        view_direction=event.view_direction,
        dims_displayed=event.dims_displayed,
        world=True,
    )
