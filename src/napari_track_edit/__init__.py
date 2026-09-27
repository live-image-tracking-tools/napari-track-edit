import logging

from ._wgpu_setup import configure_wgpu_backend

# must run before fastplotlib/pygfx create a wgpu instance
configure_wgpu_backend()

# fastplotlib looks up ambiguous colormap names (e.g. 'coolwarm') on import, which makes
# cmap log a harmless warning
logging.getLogger("cmap").setLevel(logging.ERROR)

from .application_menus.main_app import StartupWidget  # noqa: E402, F401
