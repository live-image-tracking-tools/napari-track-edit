import numpy as np
import pytest

from napari_track_edit.data_views.lazy_array_wrapper import (
    LazyArrayWrapper,
    _is_fancy_index,
)


class FakeLazyArray:
    """Minimal lazy array that mimics GraphArrayView behaviour.

    __getitem__ always returns another FakeLazyArray (never numpy values),
    so fancy indexing followed by == would fail without the wrapper.
    """

    def __init__(self, data: np.ndarray):
        self._data = data

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

    def __getitem__(self, index):
        if isinstance(index, int):
            return self._data[index]
        return FakeLazyArray(self._data[index])

    def __array__(self, dtype=None, copy=None):
        return np.array(self._data, dtype=dtype, copy=copy)


@pytest.fixture
def sample_data():
    """4D array: 3 timeframes, 2x4x4 spatial."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 10, size=(3, 2, 4, 4), dtype=np.int64)


@pytest.fixture
def lazy(sample_data):
    return FakeLazyArray(sample_data)


@pytest.fixture
def wrapped(lazy):
    return LazyArrayWrapper(lazy)


class TestIsFancyIndex:
    def test_tuple_of_arrays(self):
        idx = (np.array([0, 1]), np.array([2, 3]))
        assert _is_fancy_index(idx) is True

    def test_tuple_with_list(self):
        idx = ([0, 1], [2, 3])
        assert _is_fancy_index(idx) is True

    def test_scalar(self):
        assert _is_fancy_index(5) is False

    def test_slice(self):
        assert _is_fancy_index(slice(0, 3)) is False

    def test_tuple_of_scalars(self):
        assert _is_fancy_index((0, 1, 2)) is False

    def test_tuple_of_slices(self):
        assert _is_fancy_index((slice(0, 2), slice(1, 3))) is False

    def test_mixed_with_array(self):
        idx = (0, np.array([1, 2]))
        assert _is_fancy_index(idx) is True


class TestDelegation:
    def test_shape(self, wrapped, sample_data):
        assert wrapped.shape == sample_data.shape

    def test_dtype(self, wrapped, sample_data):
        assert wrapped.dtype == sample_data.dtype

    def test_ndim(self, wrapped, sample_data):
        assert wrapped.ndim == sample_data.ndim

    def test_size(self, wrapped, sample_data):
        assert wrapped.size == sample_data.size

    def test_len(self, wrapped, sample_data):
        assert len(wrapped) == len(sample_data)

    def test_asarray(self, wrapped, sample_data):
        result = np.asarray(wrapped)
        np.testing.assert_array_equal(result, sample_data)

    def test_wrapped_property(self, wrapped, lazy):
        assert wrapped.wrapped is lazy


class TestGetitem:
    def test_scalar_index_delegates(self, wrapped, sample_data):
        frame = wrapped[0]
        np.testing.assert_array_equal(np.asarray(frame), sample_data[0])

    def test_slice_index_delegates(self, wrapped, sample_data):
        result = wrapped[0:2]
        np.testing.assert_array_equal(np.asarray(result), sample_data[0:2])

    def test_fancy_index_returns_numpy(self, wrapped, sample_data):
        t = np.array([0, 0, 1, 2])
        z = np.array([0, 1, 0, 1])
        y = np.array([0, 1, 2, 3])
        x = np.array([0, 1, 2, 3])
        result = wrapped[(t, z, y, x)]
        expected = sample_data[t, z, y, x]
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, expected)

    def test_fancy_index_single_timeframe(self, wrapped, sample_data):
        t = np.array([1, 1, 1])
        z = np.array([0, 0, 1])
        y = np.array([0, 1, 2])
        x = np.array([0, 1, 3])
        result = wrapped[(t, z, y, x)]
        expected = sample_data[t, z, y, x]
        np.testing.assert_array_equal(result, expected)

    def test_fancy_index_empty_arrays(self, wrapped):
        empty = np.array([], dtype=np.int64)
        result = wrapped[(empty, empty, empty, empty)]
        assert isinstance(result, np.ndarray)
        assert len(result) == 0

    def test_fancy_index_with_lists(self, wrapped, sample_data):
        result = wrapped[([0, 1], [0, 1], [0, 1], [0, 1])]
        expected = sample_data[[0, 1], [0, 1], [0, 1], [0, 1]]
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, expected)

    def test_fancy_index_comparison_works(self, wrapped, sample_data):
        """The original bug: fancy_index then == should produce a boolean array."""
        t = np.array([0, 0, 1])
        z = np.array([0, 0, 0])
        y = np.array([0, 1, 2])
        x = np.array([0, 1, 3])
        result = wrapped[(t, z, y, x)] == 0
        expected = sample_data[t, z, y, x] == 0
        assert isinstance(result, np.ndarray)
        assert result.dtype == bool
        np.testing.assert_array_equal(result, expected)


class TestReadOnly:
    def test_no_setitem(self, wrapped):
        assert not hasattr(wrapped, "__setitem__")

    def test_no_double_wrap(self, wrapped):
        double = LazyArrayWrapper(wrapped)
        # wrapping a wrapper is allowed but not intended;
        # the data property setter on ContourLabels guards against it
        assert double.wrapped is wrapped


class TestGetattr:
    def test_forwards_unknown_attributes(self):
        """__getattr__ should forward to the underlying array."""

        class ArrayWithExtra:
            shape = (3, 4)
            dtype = np.int64
            ndim = 2
            size = 12
            custom_attr = "hello"

            def __len__(self):
                return 3

            def __getitem__(self, index):
                return self

            def __array__(self, dtype=None, copy=None):
                return np.zeros(self.shape, dtype=dtype)

        arr = ArrayWithExtra()
        wrapped = LazyArrayWrapper(arr)
        assert wrapped.custom_attr == "hello"
