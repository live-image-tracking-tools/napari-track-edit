"""Tests for NavigationWidget - controls for navigating the tree view."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from qtpy.QtWidgets import QPushButton

from napari_track_edit.data_views.views.tree_view.navigation_widget import (
    NavigationWidget,
)


@pytest.fixture
def track_df():
    """Sample track dataframe."""
    return pd.DataFrame(
        {
            "node_id": ["1", "2", "3", "4", "5", "6", "7"],
            "parent_id": [None, "1", "1", "2", "3", "4", "5"],
            "t": [0, 1, 1, 2, 2, 3, 3],
            "x_axis_pos": [0, 0, 5, 0, 5, 0, 5],
        }
    )


@pytest.fixture
def lineage_df():
    """Sample lineage dataframe (subset of track_df)."""
    return pd.DataFrame(
        {
            "node_id": ["1", "2", "4", "6"],
            "parent_id": [None, "1", "2", "4"],
            "t": [0, 1, 2, 3],
            "x_axis_pos": [0, 0, 0, 0],
        }
    )


@pytest.fixture
def mock_selected_nodes():
    """Mock NodeSelectionList."""
    mock = MagicMock()
    mock.__len__ = MagicMock(return_value=1)
    mock.__getitem__ = MagicMock(return_value="2")
    return mock


class TestNavigationWidgetInitialization:
    """Test NavigationWidget initialization."""

    def test_initialization(self, qtbot, track_df, lineage_df, mock_selected_nodes):
        """Test widget creates all components."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        assert widget.track_df is track_df
        assert widget.lineage_df is lineage_df
        assert widget.view_direction == "horizontal"
        assert widget.selected_nodes is mock_selected_nodes
        assert widget.plot_type == "tree"
        assert widget.feature is None

    def test_initialization_creates_buttons(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test widget creates navigation buttons."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Find all buttons
        buttons = widget.findChildren(QPushButton)
        assert len(buttons) == 4

        # Check button text (arrows)
        button_texts = [btn.text() for btn in buttons]
        assert "⬅" in button_texts
        assert "➡" in button_texts
        assert "⬆" in button_texts
        assert "⬇" in button_texts


class TestMoveMethod:
    """Test move method for navigation."""

    def test_move_returns_early_if_no_selected_nodes(self, qtbot, track_df, lineage_df):
        """Test move does nothing when no nodes selected."""
        empty_selection = MagicMock()
        empty_selection.__len__ = MagicMock(return_value=0)

        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=empty_selection,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Should not raise error
        widget.move("left")

        # Verify add was never called
        empty_selection.add.assert_not_called()

    def test_move_left_horizontal_gets_predecessor(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move left in horizontal view gets predecessor."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2's predecessor is node 1
        widget.move("left")

        mock_selected_nodes.add.assert_called_once_with("1")

    def test_move_right_horizontal_gets_successor(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move right in horizontal view gets successor."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2's successor is node 4
        widget.move("right")

        mock_selected_nodes.add.assert_called_once_with("4")

    def test_move_up_horizontal_gets_next_track(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move up in horizontal view gets next track node."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Should look in lineage_df first (node 2 is at x_axis_pos 0)
        # No node with higher x_axis_pos in lineage at same time
        # Should fall back to track_df
        widget.move("up")

        # Node 3 is at t=1, x_axis_pos=5 (higher than node 2's 0)
        mock_selected_nodes.add.assert_called_once_with("3")

    def test_move_down_horizontal_gets_previous_track(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move down in horizontal view gets previous track node."""
        # Select node 3 instead
        mock_selected = MagicMock()
        mock_selected.__len__ = MagicMock(return_value=1)
        mock_selected.__getitem__ = MagicMock(return_value="3")

        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 3 is at t=1, x_axis_pos=5
        # Should find node 2 at t=1, x_axis_pos=0 (lower)
        widget.move("down")

        mock_selected.add.assert_called_once_with("2")

    def test_move_left_vertical_gets_previous_track(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move left in vertical view gets previous track."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="vertical",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # In vertical view, left should get next_track_node with forward=False
        # Node 2 is at t=1, x_axis_pos=0
        # No nodes at t=1 with lower x_axis_pos
        widget.move("left")

        # Should not find anything and not call add
        # Actually, it might return None
        # Let me check the logic again...
        mock_selected_nodes.add.assert_not_called()

    def test_move_right_vertical_gets_next_track(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move right in vertical view gets next track."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="vertical",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2 is at t=1, x_axis_pos=0
        # Node 3 is at t=1, x_axis_pos=5 (higher)
        widget.move("right")

        mock_selected_nodes.add.assert_called_once_with("3")

    def test_move_up_vertical_gets_predecessor(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move up in vertical view gets predecessor."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="vertical",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2's predecessor is node 1
        widget.move("up")

        mock_selected_nodes.add.assert_called_once_with("1")

    def test_move_down_vertical_gets_successor(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move down in vertical view gets successor."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="vertical",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2's successor is node 4
        widget.move("down")

        mock_selected_nodes.add.assert_called_once_with("4")

    def test_move_invalid_direction_raises_error(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test move raises ValueError for invalid direction."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        with pytest.raises(ValueError, match="Direction must be one of"):
            widget.move("invalid")


class TestGetNextTrackNode:
    """Test get_next_track_node method."""

    def test_get_next_track_node_forward(self, qtbot, track_df, lineage_df):
        """Test get_next_track_node finds next track forward."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2 is at t=1, x_axis_pos=0
        # Node 3 is at t=1, x_axis_pos=5 (next track)
        result = widget.get_next_track_node(track_df, "2", forward=True)

        assert result == "3"

    def test_get_next_track_node_backward(self, qtbot, track_df, lineage_df):
        """Test get_next_track_node finds previous track."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 3 is at t=1, x_axis_pos=5
        # Node 2 is at t=1, x_axis_pos=0 (previous track)
        result = widget.get_next_track_node(track_df, "3", forward=False)

        assert result == "2"

    def test_get_next_track_node_with_empty_df(self, qtbot, lineage_df):
        """Test get_next_track_node returns None for empty dataframe."""
        mock_selected = MagicMock()
        empty_df = pd.DataFrame()

        widget = NavigationWidget(
            track_df=empty_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        result = widget.get_next_track_node(empty_df, "2", forward=True)

        assert result is None

    def test_get_next_track_node_with_missing_node(self, qtbot, track_df, lineage_df):
        """Test get_next_track_node returns None when node not found."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        result = widget.get_next_track_node(track_df, "999", forward=True)

        assert result is None

    def test_get_next_track_node_no_neighbors(self, qtbot, track_df, lineage_df):
        """Test get_next_track_node returns None when no neighbors found."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2 is at t=1, x_axis_pos=0 - no nodes with lower x_axis_pos
        result = widget.get_next_track_node(track_df, "2", forward=False)

        assert result is None

    def test_get_next_track_node_uses_feature_in_feature_mode(self, qtbot, lineage_df):
        """Test get_next_track_node uses feature column in feature plot mode."""
        # Create dataframe with feature column
        track_df = pd.DataFrame(
            {
                "node_id": ["1", "2", "3"],
                "parent_id": [None, "1", "1"],
                "t": [0, 1, 1],
                "x_axis_pos": [0, 0, 5],
                "area": [10, 20, 30],
            }
        )

        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="feature",
        )
        qtbot.addWidget(widget)

        # Set feature
        widget.feature = "area"

        # Should use 'area' instead of 'x_axis_pos'
        # Node 2 has area=20, node 3 has area=30
        result = widget.get_next_track_node(track_df, "2", forward=True)

        assert result == "3"


class TestGetPredecessor:
    """Test get_predecessor method."""

    def test_get_predecessor_returns_parent(self, qtbot, track_df, lineage_df):
        """Test get_predecessor returns parent node."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2's parent is node 1
        result = widget.get_predecessor("2")

        assert result == "1"

    def test_get_predecessor_returns_none_for_root(self, qtbot, track_df, lineage_df):
        """Test get_predecessor returns None for root node."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 1 has no parent
        result = widget.get_predecessor("1")

        assert result is None


class TestGetSuccessor:
    """Test get_successor method."""

    def test_get_successor_returns_child(self, qtbot, track_df, lineage_df):
        """Test get_successor returns child node."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 2's successor is node 4
        result = widget.get_successor("2")

        assert result == "4"

    def test_get_successor_picks_first_child_when_multiple(
        self, qtbot, track_df, lineage_df
    ):
        """Test get_successor picks first child when node has multiple children."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 1 has two children (nodes 2 and 3)
        result = widget.get_successor("1")

        # Should return one of them (first in dataframe)
        assert result == "2"

    def test_get_successor_returns_none_for_leaf(self, qtbot, track_df, lineage_df):
        """Test get_successor returns None for leaf node."""
        mock_selected = MagicMock()
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Node 7 has no children
        result = widget.get_successor("7")

        assert result is None


class TestButtonClicks:
    """Test button click interactions."""

    def test_left_button_calls_move_left(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test left button click calls move with 'left'."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Find left button
        buttons = widget.findChildren(QPushButton)
        left_button = [btn for btn in buttons if btn.text() == "⬅"][0]

        # Click it
        left_button.click()

        # Should have called add (moving to predecessor)
        mock_selected_nodes.add.assert_called_once()

    def test_right_button_calls_move_right(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test right button click calls move with 'right'."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="horizontal",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Find right button
        buttons = widget.findChildren(QPushButton)
        right_button = [btn for btn in buttons if btn.text() == "➡"][0]

        # Click it
        right_button.click()

        # Should have called add (moving to successor)
        mock_selected_nodes.add.assert_called_once()

    def test_up_button_calls_move_up(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test up button click calls move with 'up'."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="vertical",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Find up button
        buttons = widget.findChildren(QPushButton)
        up_button = [btn for btn in buttons if btn.text() == "⬆"][0]

        # Click it
        up_button.click()

        # Should have called add (moving to predecessor in vertical)
        mock_selected_nodes.add.assert_called_once()

    def test_down_button_calls_move_down(
        self, qtbot, track_df, lineage_df, mock_selected_nodes
    ):
        """Test down button click calls move with 'down'."""
        widget = NavigationWidget(
            track_df=track_df,
            lineage_df=lineage_df,
            view_direction="vertical",
            selected_nodes=mock_selected_nodes,
            plot_type="tree",
        )
        qtbot.addWidget(widget)

        # Find down button
        buttons = widget.findChildren(QPushButton)
        down_button = [btn for btn in buttons if btn.text() == "⬇"][0]

        # Click it
        down_button.click()

        # Should have called add (moving to successor in vertical)
        mock_selected_nodes.add.assert_called_once()
