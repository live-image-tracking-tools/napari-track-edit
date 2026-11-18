import gc
from unittest.mock import patch

import napari
import pytest
from app_model import Application
from napari._app_model._app import NapariApplication, _napari_names
from napari._qt._qapp_model.qactions import init_qactions
from napari.components import ViewerModel
from napari.plugins import _initialize_plugins
from qtpy.QtCore import QEvent


@pytest.fixture(scope="module")
def viewer(qapp, request):
    """Module-scoped napari viewer shared across all tests in a module.

    By default a ``ViewerModel``: layers and events, but no Qt viewer. Creating
    one takes ~0.002 s instead of ~0.2 s, and layer changes are not drawn on a
    canvas, which on CI is done by a CPU-only software renderer. That made most
    of these test files 2-5x faster. ``qapp`` is still needed: TracksViewer
    creates Qt widgets such as TracksList.

    A module whose tests need napari's Qt side (the Qt window, canvas, dock
    widgets, ortho views) gets a real ``napari.Viewer`` by marking itself::

        pytestmark = pytest.mark.qt_viewer

    Tests should use the per-file autouse ``clear_viewer_layers`` fixture
    (defined in each test module) to clean up layers between tests.
    """
    if request.node.get_closest_marker("qt_viewer") is None:
        yield ViewerModel()
        return
    yield from _qt_viewer(qapp, request)


def _qt_viewer(qapp, request):
    """A real napari.Viewer for one module, see ``viewer``.

    The viewer gets its own app model for the module, the same way napari's
    ``make_napari_viewer`` uses ``mock_app_model`` for each test. Without that,
    the viewer registers this plugin's commands in napari's real app model, and
    once ``make_napari_viewer`` has cleared the plugin cache, the next viewer
    registers them a second time and napari >= 0.7 raises ``ValueError: Command
    'napari-track-edit.solve' already registered``. That depends on which test
    files ran before in the same process, so it only showed up under
    pytest-xdist.

    Switching this fixture to ``make_napari_viewer`` also avoids the conflict but
    adds ~56s to the full suite (~2.2x on tests/data_views), because napari
    exposes no module- or session-scoped viewer fixture.
    """
    app_name = f"test_app_{request.module.__name__}"
    app = NapariApplication(app_name)
    app.injection_store.namespace = _napari_names
    _initialize_plugins.cache_clear()
    init_qactions.cache_clear()
    with patch.object(NapariApplication, "get_app_model", return_value=app):
        v = napari.Viewer(show=False)
        yield v
        v.close()
    del v
    # Free the closed viewer now. make_napari_viewer fails a test if any QtViewer
    # is still alive when it starts, but only runs a partial gc.collect(1), which
    # misses a viewer that lived through a whole module. Under pytest-xdist the
    # next file on this worker can be one that uses make_napari_viewer.
    # Closing the viewer leaves part of its cleanup to deleteLater, which only runs
    # in the event loop, and no event loop runs between test modules.
    # processEvents() does not run those deletes; since PyQt 6.12 they are no
    # longer run along the way either, so flush them explicitly.
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    Application.destroy(app_name)
    _initialize_plugins.cache_clear()
    init_qactions.cache_clear()
