"""Check that the remote datasets the app downloads are still reachable.

These hit the network; skip them with
``pytest --ignore=tests/test_download_urls.py``. A failure here means a download
source went stale (moved, unshared, quota exceeded) and users would hit a broken
button or a broken ``File > Open Sample``.
"""

import urllib.request

import pytest

from motile_tracker.application_menus.welcome_widget import EXAMPLE_GEFFS
from motile_tracker.example_data import (
    CTC_URL_TEMPLATE,
    ZENODO_LABELS_URL,
    ZENODO_RAW_URL,
)

DOWNLOAD_SOURCES = {
    "sample: Fluo-N2DL-HeLa (CTC)": CTC_URL_TEMPLATE.format(ds_name="Fluo-N2DL-HeLa"),
    "sample: Mouse_Embryo_Membrane raw (zenodo)": ZENODO_RAW_URL,
    "sample: Mouse_Embryo_Membrane labels (zenodo)": ZENODO_LABELS_URL,
    **{f"example geff: {label}": url for label, _, url in EXAMPLE_GEFFS},
}


@pytest.mark.parametrize("name", DOWNLOAD_SOURCES)
def test_download_source_is_reachable(name):
    """Fetch the first byte of each dataset and check we get the file itself."""
    request = urllib.request.Request(
        DOWNLOAD_SOURCES[name], headers={"Range": "bytes=0-0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.status in (200, 206), f"{name}: HTTP {response.status}"
        content_type = response.headers.get("Content-Type", "")
        # Google Drive and Zenodo answer with an html page rather than an error
        # status when a file is unshared, removed, or over its quota.
        assert "text/html" not in content_type, (
            f"{name}: served an html page instead of the file ({content_type})"
        )
        assert response.read(1), f"{name}: empty response body"
