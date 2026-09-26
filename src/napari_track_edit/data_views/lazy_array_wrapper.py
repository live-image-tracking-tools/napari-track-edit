from __future__ import annotations

import numpy as np


def _is_fancy_index(index):
    """Return True if index is a fancy index (tuple containing array-likes)."""
    if not isinstance(index, tuple):
        return False
    return any(isinstance(i, (np.ndarray, list)) for i in index)


class LazyArrayWrapper:
    """Wrapper around lazy/read-only arrays that materializes fancy indexing.

    Lazy array backends like tracksdata's GraphArrayView return view objects
    from __getitem__ rather than numpy values. This breaks napari code that
    does fancy indexing (e.g. ``data[tuple_of_arrays] == value``).

    This wrapper intercepts fancy indexing and materializes one
    first-dimension slice at a time, returning numpy values. All other
    indexing patterns and attribute access are delegated to the underlying
    array.

    The wrapper intentionally does not implement __setitem__, preserving the
    read-only nature of the underlying array for detection via
    ``hasattr(data, "__setitem__")``.
    """

    def __init__(self, data):
        self._data = data

    @property
    def wrapped(self):
        """The underlying array object."""
        return self._data

    @property
    def shape(self):
        return self._data.shape

    @property
    def dtype(self):
        return self._data.dtype

    @property
    def ndim(self):
        return self._data.ndim

    @property
    def size(self):
        return self._data.size

    def __len__(self):
        return len(self._data)

    def __array__(self, dtype=None, copy=None):
        return np.array(self._data, dtype=dtype, copy=copy)

    def __getitem__(self, index):
        if _is_fancy_index(index):
            return self._materialize_fancy(index)
        return self._data[index]

    def _materialize_fancy(self, index):
        """Materialize fancy indexing by reading individual coordinates.

        Each coordinate tuple is looked up via scalar indexing on the
        underlying array, which is fast when the array has an internal
        cache (e.g. GraphArrayView's NDChunkCache).
        """
        # O(n) Python loop of scalar lookups: fine for brush strokes (few
        # pixels), but a large preserve_labels op (e.g. a bucket-fill over a
        # big region) iterates over every candidate pixel and may be slow.
        arrays = tuple(np.asarray(i) for i in index)
        n = len(arrays[0])
        result = np.empty(n, dtype=self._data.dtype)
        for i in range(n):
            coord = tuple(int(a[i]) for a in arrays)
            result[i] = np.asarray(self._data[coord])
        return result

    def __getattr__(self, name):
        # Guard against infinite recursion if _data is missing (e.g. during
        # copy/pickle, which build the instance without calling __init__).
        # (only matters if in the future we make the segLayer copyable/picklable/deepcopyable,
        # which we currently don't, but this is a good safeguard in case we do)
        if name == "_data":
            raise AttributeError(name)
        return getattr(self._data, name)

    def __repr__(self):
        return f"LazyArrayWrapper({self._data!r})"
