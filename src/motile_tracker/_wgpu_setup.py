"""wgpu instance configuration, applied before fastplotlib/pygfx create an instance."""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def configure_wgpu_backend() -> None:
    """Restrict the wgpu instance to Vulkan on Linux.

    wgpu probes every backend when requesting an adapter. On Linux the GLES/EGL probe
    calls eglMakeCurrent, which returns BadAccess once napari's Qt/vispy OpenGL context
    is current; wgpu-native then panics in non-unwinding FFI code and aborts the whole
    process. Mesa ships the lavapipe ICD as a software fallback, so Vulkan-only is safe.

    Set MOTILE_TRACKER_WGPU_BACKENDS (comma-separated, e.g. "All") to override.
    """
    if sys.platform != "linux":
        return
    backends = [
        b.strip()
        for b in os.environ.get("MOTILE_TRACKER_WGPU_BACKENDS", "Vulkan").split(",")
        if b.strip()
    ]
    try:
        from wgpu.backends.wgpu_native.extras import set_instance_extras

        set_instance_extras(backends=backends)
    except (ImportError, KeyError, AttributeError):
        logger.warning("Could not restrict the wgpu backend to %s", backends)
