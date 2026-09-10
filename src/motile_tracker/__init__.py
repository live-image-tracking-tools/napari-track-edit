from ._wgpu_setup import configure_wgpu_backend

# must run before fastplotlib/pygfx create a wgpu instance
configure_wgpu_backend()

from .application_menus.main_app import StartupWidget  # noqa: E402, F401
