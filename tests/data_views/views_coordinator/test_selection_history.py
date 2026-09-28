"""Tests for NodeSelectionHistory

Tests cover:
- Basic selection history navigation
- Duplicate skipping (consecutive identical selections)
- Deleted node filtering (deleted nodes hidden but kept in history)
- History pointer management
- Previous selection restoration
"""

from napari_track_edit.data_views.views_coordinator.node_selection_history import (
    NodeSelectionHistory,
)


class TestBasicHistory:
    """Test basic history operations."""

    def test_initialization(self):
        """Test NodeSelectionHistory initializes empty."""
        history = NodeSelectionHistory()

        assert len(history) == 0
        assert history.as_list == []
        assert not history.has_next_set
        assert not history.has_previous_set

    def test_add_single_node(self):
        """Test adding a single node to empty selection."""
        history = NodeSelectionHistory()

        history.add(1)
        assert len(history) == 1
        assert 1 in history
        assert history.as_list == [1]

    def test_add_list(self):
        """Test adding multiple nodes at once."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)
        assert len(history) == 3
        assert {1, 2, 3} == set(history)

    def test_reset_clears_selection(self):
        """Test reset clears the current selection."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)
        assert len(history) > 0

        history.reset()
        assert len(history) == 0

    def test_restore_previous(self):
        """Test restoring previous selection."""
        history = NodeSelectionHistory()

        history.add_list([1, 2], append=False)
        first_sel = set(history)

        history.add_list([3, 4], append=False)
        second_sel = set(history)

        assert first_sel != second_sel

        history.restore()
        assert set(history) == first_sel


class TestHistoryNavigation:
    """Test navigating through selection history."""

    def test_no_navigation_with_single_entry(self):
        """Test that navigation is disabled with only one entry."""
        history = NodeSelectionHistory()

        history.add_list([1, 2], append=False)

        assert not history.has_previous_set
        assert not history.has_next_set

    def test_navigation_forward(self):
        """Test navigating forward through history."""
        history = NodeSelectionHistory()

        history.add_list([1], append=False)
        history.add_list([2], append=False)
        history.add_list([3], append=False)

        # We're at [3], should be able to go backward but not forward
        assert history.has_previous_set
        assert not history.has_next_set

        history.select_node_set_from_history(previous=False)
        # Should not move if at end
        assert set(history) == {3}

    def test_navigation_backward(self):
        """Test navigating backward through history."""
        history = NodeSelectionHistory()

        history.add_list([1], append=False)
        history.add_list([2], append=False)
        history.add_list([3], append=False)

        history.select_node_set_from_history(previous=True)
        assert set(history) == {2}

        history.select_node_set_from_history(previous=True)
        assert set(history) == {1}

        # At start, can't go further back
        history.select_node_set_from_history(previous=True)
        assert set(history) == {1}

    def test_navigate_then_forward(self):
        """Test navigating backward then forward."""
        history = NodeSelectionHistory()

        history.add_list([1], append=False)
        history.add_list([2], append=False)
        history.add_list([3], append=False)

        # Go back twice
        history.select_node_set_from_history(previous=True)
        history.select_node_set_from_history(previous=True)
        assert set(history) == {1}

        # Go forward
        history.select_node_set_from_history(previous=False)
        assert set(history) == {2}


class TestDuplicateSkipping:
    """Test that consecutive duplicate selections are skipped."""

    def test_duplicate_not_added_to_history(self):
        """Test that adding the same selection twice doesn't create history."""
        history = NodeSelectionHistory()

        history.add_list([1, 2], append=False)
        history.add_list([1, 2], append=False)  # Same selection

        # History should only have one entry
        assert not history.has_previous_set

    def test_duplicate_skipped_when_navigating(self):
        """Test that navigation skips over sets that are identical after filtering."""
        history = NodeSelectionHistory()

        history.add_list([3, 4], append=False)
        history.add_list([1, 2], append=False)
        history.add_list([1, 2], append=False)  # same selection

        # Try to go backward - should skip the duplicate and go to [3, 4]
        history.select_node_set_from_history(previous=True)
        assert set(history) == {3, 4}


class TestDeletedItemFiltering:
    """Test that deleted nodes are filtered from display but kept in history."""

    def test_deleted_items_masking(self):
        """Test that deleted items don't appear in current selection."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)
        assert len(history) == 3

        # Mark node 2 as deleted
        history.deleted_items.add(2)

        # Current should only show non-deleted
        assert len(history) == 2
        assert 2 not in history
        assert {1, 3} == set(history)

        # deleted node is still present in the stored history
        assert {1, 2, 3} == history._history[0]

        # Remove node 2 from the deleted items list
        history.deleted_items.discard(2)
        assert len(history) == 3
        assert 2 in history
        assert {1, 2, 3} == set(history)

    def test_deleted_items_skipped_in_navigation(self):
        """Test that selections containing only deleted items are skipped."""
        history = NodeSelectionHistory()

        history.add_list([1, 2], append=False)
        history.add_list([3, 4], append=False)
        history.add_list([2, 5], append=False)

        # Delete nodes 2 and 4
        history.deleted_items.add(2)
        history.deleted_items.add(4)

        # Current is [2, 5], filtered to [5]
        assert set(history) == {5}

        # Navigate backward first goes to [3, 4], filtered to [3]
        history.select_node_set_from_history(previous=True)
        assert set(history) == {3}

        # Navigate backward again, now skips [3, 4] (now different from current [3])
        # and goes to [1, 2] (now [1] after filtering)
        history.select_node_set_from_history(previous=True)
        assert set(history) == {1}


class TestPreviousSetTracking:
    """Test tracking of previous selection for restore functionality."""

    def test_prev_set_updates_on_add(self):
        """Test that _prev_set is updated when adding to history."""
        history = NodeSelectionHistory()

        history.add_list([1, 2], append=False)
        history.add_list([3, 4], append=False)

        # _prev_set should track second-to-last state
        history.reset()

        # Restoring should go back to [3, 4]
        history.restore()
        assert set(history) == {3, 4}

    def test_has_valid_last_shown_set(self):
        """Test has_valid_last_shown_set property."""
        history = NodeSelectionHistory()

        # No previous set initially
        assert not history.has_valid_last_shown_set

        history.add_list([1, 2], append=False)
        assert not history.has_valid_last_shown_set

        history.add_list([3, 4], append=False)
        assert history.has_valid_last_shown_set

        # With deleted items, may not be valid
        history.deleted_items.add(1)
        history.deleted_items.add(2)

        # _prev_set was [1, 2], all deleted, so not valid
        assert not history.has_valid_last_shown_set

    def test_restore_with_deleted_items(self):
        """Test restore functionality with deleted items."""
        history = NodeSelectionHistory()

        history.add_list([1, 2], append=False)
        history.add_list([3, 4], append=False)

        # Delete some items
        history.deleted_items.add(1)

        # Restore should bring back [1, 2] but show as [2]
        history.restore()
        assert set(history) == {2}


class TestContainerMethods:
    """Test container protocol methods."""

    def test_contains(self):
        """Test __contains__ method."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)

        assert 1 in history
        assert 2 in history
        assert 4 not in history

    def test_len(self):
        """Test __len__ method."""
        history = NodeSelectionHistory()

        assert len(history) == 0

        history.add_list([1, 2, 3], append=False)
        assert len(history) == 3

    def test_iter(self):
        """Test __iter__ method."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)

        items = list(history)
        assert set(items) == {1, 2, 3}

    def test_getitem(self):
        """Test __getitem__ method."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)

        # Can access items by index (order may vary)
        item = history[0]
        assert item in {1, 2, 3}


class TestNextNode:
    """Test next_node method for iterating within selection."""

    def test_next_node_traversal(self):
        """Test traversing through selected nodes."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)

        nodes = []
        for _ in range(6):  # Get 6 nodes (should cycle)
            node = history.next_node(forward=True)
            if node:
                nodes.append(node)

        # Should cycle through the 3 nodes twice
        assert len(nodes) == 6
        # Count of each node should be 2 (due to cycling)
        for node_id in [1, 2, 3]:
            assert nodes.count(node_id) == 2

    def test_next_node_backward(self):
        """Test traversing backward through selected nodes."""
        history = NodeSelectionHistory()

        history.add_list([1, 2, 3], append=False)

        # Get node forward first time
        node1 = history.next_node(forward=True)

        # Then go backward twice
        node2 = history.next_node(forward=False)
        node3 = history.next_node(forward=False)

        # Should form a cycle
        assert node1 == 2
        assert node2 == 1
        assert node3 == 3

    def test_next_node_empty_selection(self):
        """Test next_node with empty selection returns None."""
        history = NodeSelectionHistory()

        node = history.next_node(forward=True)
        assert node is None
