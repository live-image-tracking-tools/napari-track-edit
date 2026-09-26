"""Tests for click_utils.py - click detection and value retrieval utilities."""

import time
from unittest.mock import MagicMock

from napari_track_edit.data_views.views.layers.click_utils import (
    detect_click,
    get_click_value,
)


class TestDetectClick:
    """Tests for detect_click function."""

    def test_detect_click_returns_true_for_simple_click(self):
        """Test detect_click returns True for a simple click without drag."""
        # Create mock event
        event = MagicMock()
        event.type = "mouse_press"

        # Create generator
        gen = detect_click(event)

        # First yield - initial press
        next(gen)

        # Change to mouse_release (no mouse_move)
        event.type = "mouse_release"

        # Get result
        try:
            next(gen)
        except StopIteration as e:
            result = e.value

        assert result is True

    def test_detect_click_returns_false_for_drag(self):
        """Test detect_click returns False for a drag."""
        # Create mock event
        event = MagicMock()
        event.type = "mouse_press"

        # Create generator
        gen = detect_click(event)

        # First yield - initial press
        next(gen)

        # Simulate drag with mouse_move events
        event.type = "mouse_move"
        next(gen)
        next(gen)
        next(gen)

        # Change to mouse_release after sufficient time
        time.sleep(0.6)  # More than 0.5s threshold
        event.type = "mouse_release"

        # Get result
        try:
            next(gen)
        except StopIteration as e:
            result = e.value

        assert result is False

    def test_detect_click_treats_micro_drag_as_click(self):
        """Test detect_click treats very short drags as clicks."""
        # Create mock event
        event = MagicMock()
        event.type = "mouse_press"

        # Create generator
        gen = detect_click(event)

        # First yield - initial press
        next(gen)

        # Simulate very short drag (< 0.5s)
        event.type = "mouse_move"
        next(gen)

        # Change to mouse_release quickly
        event.type = "mouse_release"

        # Get result
        try:
            next(gen)
        except StopIteration as e:
            result = e.value

        assert result is True

    def test_detect_click_yields_during_drag(self):
        """Test detect_click yields during mouse_move events."""
        # Create mock event
        event = MagicMock()
        event.type = "mouse_press"

        # Create generator
        gen = detect_click(event)

        # First yield - initial press
        next(gen)

        # Simulate multiple mouse_move events
        event.type = "mouse_move"
        for _ in range(5):
            result = next(gen)
            assert result is None  # Should yield None during drag


class TestGetClickValue:
    """Tests for get_click_value function."""

    def test_get_click_value_with_labels_layer(self):
        """Test get_click_value with Labels layer."""
        # Create mock layer
        layer = MagicMock()
        layer.get_value.return_value = 42

        # Create mock event
        event = MagicMock()
        event.position = (10, 20, 30)
        event.view_direction = (1, 0, 0)
        event.dims_displayed = (0, 1, 2)

        result = get_click_value(layer, event)

        # Verify get_value was called with correct parameters
        layer.get_value.assert_called_once_with(
            (10, 20, 30),
            view_direction=(1, 0, 0),
            dims_displayed=(0, 1, 2),
            world=True,
        )
        assert result == 42

    def test_get_click_value_with_points_layer(self):
        """Test get_click_value with Points layer."""
        # Create mock layer
        layer = MagicMock()
        layer.get_value.return_value = 7

        # Create mock event
        event = MagicMock()
        event.position = (5, 15, 25)
        event.view_direction = (0, 1, 0)
        event.dims_displayed = (1, 2, 3)

        result = get_click_value(layer, event)

        # Verify get_value was called with correct parameters
        layer.get_value.assert_called_once_with(
            (5, 15, 25),
            view_direction=(0, 1, 0),
            dims_displayed=(1, 2, 3),
            world=True,
        )
        assert result == 7

    def test_get_click_value_returns_zero_for_background(self):
        """Test get_click_value returns 0 for background clicks."""
        # Create mock layer
        layer = MagicMock()
        layer.get_value.return_value = 0  # Background

        # Create mock event
        event = MagicMock()
        event.position = (100, 200, 300)
        event.view_direction = (0, 0, 1)
        event.dims_displayed = (0, 1, 2)

        result = get_click_value(layer, event)

        assert result == 0

    def test_get_click_value_with_2d_position(self):
        """Test get_click_value with 2D position."""
        # Create mock layer
        layer = MagicMock()
        layer.get_value.return_value = 15

        # Create mock event with 2D position
        event = MagicMock()
        event.position = (50, 100)
        event.view_direction = (1, 0)
        event.dims_displayed = (0, 1)

        result = get_click_value(layer, event)

        # Verify get_value was called with correct parameters
        layer.get_value.assert_called_once_with(
            (50, 100),
            view_direction=(1, 0),
            dims_displayed=(0, 1),
            world=True,
        )
        assert result == 15
