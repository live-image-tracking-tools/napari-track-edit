

# Napari Track Edit

[![tests](https://github.com/live-image-tracking-tools/napari-track-edit/workflows/tests/badge.svg)](https://github.com/live-image-tracking-tools/napari-track-edit/actions)
[![codecov](https://codecov.io/gh/live-image-tracking-tools/napari-track-edit/branch/main/graph/badge.svg)](https://codecov.io/gh/live-image-tracking-tools/napari-track-edit)
[![PyPI version](https://badge.fury.io/py/napari-track-edit.svg)](https://badge.fury.io/py/napari-track-edit)
[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<img src="docs/source/images/logo_transparent.png" align="right" width="180" alt="Napari Track Edit logo" />

A napari plugin for interactive visualization, navigation, and editing of object tracking results. You can open and edit existing tracking data, and manually create new tracking results.
The full documentation of the plugin can be found [here](https://liveimagetrackingtools.org/napari-track-edit/).

----------------------------------

## Installation

Users can download and install an executable application from the github release, or
install from `pypi` in the environment of their choice (e.g. `venv`, `conda`) with the command
`pip install napari-track-edit`.
Currently, napari-track-edit requires python >=3.11.

### Recommended extras

For better performance, you can install the optional `numba` extra, which napari uses
to speed up coloring large label layers:
```bash
pip install napari-track-edit[numba]
```

### For developers

Developers can clone the GitHub repository and then use `uv` to install and run the code.
See the developer guide in [`DEVELOPER.md`](DEVELOPER.md) for more information.

## Usage
Start napari and open all widgets via `Plugins` > `Napari Track Edit` > `Open all widgets`.

From here you can:
- load an image to [manually track objects](https://liveimagetrackingtools.org/napari-track-edit/tracking.html#tracking-from-scratch),
- or [load existing tracking data](https://liveimagetrackingtools.org/napari-track-edit/saving_loading.html#loading-tracks) to explore or edit.

If you would like to see an example first, go to `Plugins` > `Napari Track Edit` > `Widget - Getting started`, and click on one of the two examples, `Hela cells (2D)` or `Mouse embryo (3D)`, to download and view them:

- Fluo-N2DL-HeLa is a 2D dataset of images and segmentations of HeLa cells from the [`cell tracking challenge`](https://celltrackingchallenge.net/2d-datasets/).
- Mouse Embryo Membrane is a 3D dataset of images and segmentations of a membrane labeled developing early mouse embryo (4-26 cells)
from [`Fabrèges et al (2024)`](https://www.science.org/doi/10.1126/science.adh1145) available [`here`](https://zenodo.org/records/13903500).

For details, please read the [documentation](https://liveimagetrackingtools.org/napari-track-edit/).
If you are new to napari-track-edit, you can follow this [tutorial](https://liveimagetrackingtools.org/napari-track-edit/napari-track-edit_tutorial.html) to learn the basics.

https://github.com/user-attachments/assets/cd23271d-bbe6-40c2-80cb-8404136a564a

## Issues

If you encounter any problems, please
[file an issue](https://github.com/live-image-tracking-tools/napari-track-edit/issues)
along with a detailed description.
