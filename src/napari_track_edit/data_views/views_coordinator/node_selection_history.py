from __future__ import annotations

from psygnal import Signal


class NodeSelectionHistory:
    """History-aware selection list for nodes with signals on updates.

    Records sets of selected nodes and allows navigating backwards/forwards through the
    selection history. Consecutive duplicates or empty selections are skipped when
    navigating.

    Deleted nodes are never returned in the _current selection list, but they are allowed
    to exist in the history, so that they can be 'reactivated' if placed back. When
    selecting next/previous node sets, sets that are empty after filtering are skipped
    automatically.

    The last selection is stored on _last_shown_set, and can be restored with the restore
    function, irrespective of the pointer in history.

    For convenience, there are helper properties to check if a next or previous node set
    is available for selection, and whether a valid prev_set exists (used to enable/
    disable buttons).
    """

    selection_updated = Signal()

    def __init__(self):
        super().__init__()

        self._history: list[set[int]] = []  # History of selection states
        self._last_shown_set: set[int] = (
            set()
        )  # Previous selection, for restore functionality
        self.deleted_items: set[int] = set()  # set of invalid (deleted) nodes

        self._pointer = 0  # Track position in history for sets of nodes
        self._iter_index = 0  # index for "next/previous node" (within selection)

    @property
    def _current(self) -> set[int]:
        """Get the current selection set, minus deleted items."""

        selection = self._history[self._pointer] if self._history_size > 0 else set()
        return selection - self.deleted_items

    @property
    def as_list(self) -> list[int]:
        """Return the selected nodes as a list (arbitrary order)."""
        return list(self._current)

    @property
    def _history_size(self) -> int:
        return len(self._history)

    @property
    def _is_at_start(self) -> bool:
        """Return True if the pointer is 0, the history is not empty."""

        return self._pointer == 0 and self._history_size > 0

    @property
    def _is_at_end(self) -> bool:
        """Return True if the pointer is at the last possible index of the history, if
        it is not empty"""

        return self._pointer == (self._history_size - 1) and self._history_size > 0

    @property
    def has_next_set(self) -> bool:
        """Return True if a next set is available for selection (non-empty after filtering)."""

        return self._find_next_valid_index(self._pointer, +1) is not None

    @property
    def has_previous_set(self) -> bool:
        """Return True if a previous set is available for selection (non-empty after filtering)."""

        return self._find_next_valid_index(self._pointer, -1) is not None

    @property
    def has_valid_last_shown_set(self) -> bool:
        """Return True if previous selection contains at least one valid item."""

        if not self._last_shown_set:
            return False

        if not self.deleted_items:
            return True

        return bool(self._last_shown_set - self.deleted_items)

    def _reset_iterator(self) -> None:
        """Reset iteration pointer whenever selection changes."""
        self._iter_index = 0

    def _add_to_history(self, new_set: set[int]) -> None:
        """Add a new selection state to history if it is different from current.

        Args:
            new_set: The new selection set to potentially add to history.
        """

        if self._history_size > 0 and self._history[self._pointer] == new_set:
            # skip duplicates
            return

        # If not at the end of history, truncate the redo stack
        if not self._is_at_end:
            self._history = self._history[: self._pointer + 1]

        # Add the new set to history and update pointer
        self._history.append(new_set.copy())
        self._pointer = self._history_size - 1

    def _find_next_valid_index(self, start: int, step: int) -> int | None:
        """Find next index (forward/backward) with non-empty filtered set.

        Skips indices that:
        - Have empty sets after filtering deleted items
        - Have the same filtered set as the current selection (consecutive duplicates)

        Args:
            start (int): starting index, e.g. the current pointer
            step (int): the value by which to increment (can be negative)

        Returns:
            The next index in the history that contains at least one existing node
            and differs from the current selection, or None if there is no such index.

        """

        i = start + step
        current_filtered = self._current

        if not self.deleted_items:
            while 0 <= i < self._history_size:
                if self._history[i] and self._history[i] != current_filtered:
                    return i
                i += step
        else:
            while 0 <= i < self._history_size:
                filtered_set = self._history[i] - self.deleted_items
                if filtered_set and filtered_set != current_filtered:
                    return i
                i += step

        return None

    def add(self, item: int, append: bool = False) -> None:
        """Append or replace an item in the selection.

        Args:
            item: The node ID to add or toggle.
            append: If True, toggle item in existing selection (add if absent, remove if present).
                If False, replace selection with just this item.
        """
        current = self._current.copy()
        if current:  # Only store non-empty previous selections
            self._last_shown_set = current
        new_set = current.copy()
        if append:
            if item in new_set:
                new_set.remove(item)
            else:
                new_set.add(item)
        else:
            new_set = {item}

        self._add_to_history(new_set)
        self._reset_iterator()
        self.selection_updated.emit()

    def add_list(self, items: list[int], append: bool = False) -> None:
        """Add multiple items to the selection.

        Args:
            items: List of node IDs to add.
            append: If True, toggle items in existing selection.
                If False, replace selection with these items.
        """
        current = self._current.copy()
        if current:  # Only store non-empty previous selections
            self._last_shown_set = current
        new_set = current.copy()
        items_set = set(items)
        if append:
            new_set.symmetric_difference_update(items_set)
        else:
            new_set = items_set.copy()

        self._add_to_history(new_set)
        self._reset_iterator()
        self.selection_updated.emit()

    def reset(self) -> None:
        """Clear all elements from the selection and update history."""

        current = self._current.copy()
        if current:  # Only store non-empty previous selections
            self._last_shown_set = current

        self._add_to_history(set())  # add empty set as the new selection
        self._reset_iterator()
        self.selection_updated.emit()

    def clear(self) -> None:
        """Forget the selection and its history.

        Unlike reset, which records an empty selection as a new history entry,
        this drops the history itself: the node ids in it belong to a tracks
        object that is no longer loaded, so restoring them is meaningless.
        """

        self._history = []
        self._pointer = 0
        self._last_shown_set = set()
        self.deleted_items.clear()
        self._reset_iterator()
        self.selection_updated.emit()

    def restore(self) -> None:
        """Restore the previous selection, independent of where you are in history."""

        if not self.has_valid_last_shown_set:
            return

        prev_set = self._current.copy()
        self._add_to_history(self._last_shown_set.copy())

        if prev_set:
            self._last_shown_set = prev_set

        self._reset_iterator()
        self.selection_updated.emit()

    def select_node_set_from_history(self, previous: bool) -> None:
        """Move forwards or backwards in selection history, skipping invalid selections."""

        step = -1 if previous else +1
        next_index = self._find_next_valid_index(self._pointer, step)

        if next_index is None:
            return

        prev_set = self._current.copy()

        self._pointer = next_index
        self._last_shown_set = prev_set if prev_set else self._history[self._pointer]

        self._reset_iterator()
        self.selection_updated.emit()

    def __contains__(self, item: int) -> bool:
        return item in self._current

    def __len__(self) -> int:
        return len(self._current)

    def __iter__(self):
        return iter(self._current)

    def __getitem__(self, index: int) -> int:
        """Convert to list on demand for indexing."""
        return list(self._current)[index]

    def next_node(self, forward: bool = True) -> int | None:
        """Advance/regress the pointer and return the next/previous node.

        Args:
            forward: If True, move to next node; if False, move to previous.

        Returns:
            The node ID, or None if selection is empty.
        """
        nodes = sorted(self._current)
        if not nodes:
            return None
        if forward:
            self._iter_index = (self._iter_index + 1) % len(nodes)
        else:
            self._iter_index = (self._iter_index - 1) % len(nodes)
        return nodes[self._iter_index]
