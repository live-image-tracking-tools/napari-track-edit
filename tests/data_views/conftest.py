import napari
import pytest


@pytest.fixture(scope="module")
def viewer(qapp):
    """Module-scoped napari viewer shared across all tests in a module.

    Avoids the expensive viewer creation per test. Tests should use the
    per-file autouse ``clear_viewer_layers`` fixture (defined in each test
    module) to clean up layers between tests.

    Does NOT mix with napari's ``make_napari_viewer`` fixture. That fixture calls
    ``napari.plugins._initialize_plugins.cache_clear()`` for every test it runs,
    so a bare ``napari.Viewer()`` constructed afterwards re-runs plugin
    registration against the real app model and napari >= 0.7 raises
    ``ValueError: Command 'napari-track-edit.solve' already registered``. Within a
    pytest session, don't add tests using ``make_napari_viewer`` alongside tests
    using this fixture; prefer ``napari.components.ViewerModel`` where no Qt
    window is needed (also ~15x cheaper to construct).

    Switching this fixture to ``make_napari_viewer`` avoids the conflict but adds
    ~56s to the full suite (~2.2x on tests/data_views), because napari exposes no
    module- or session-scoped viewer fixture.
    """
    v = napari.Viewer(show=False)
    yield v
    v.close()
