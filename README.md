

# Napari Track Edit

[![tests](https://github.com/live-image-tracking-tools/napari-track-edit/workflows/tests/badge.svg)](https://github.com/live-image-tracking-tools/napari-track-edit/actions)
[![codecov](https://codecov.io/gh/live-image-tracking-tools/napari-track-edit/branch/main/graph/badge.svg)](https://codecov.io/gh/live-image-tracking-tools/napari-track-edit)

<img src="docs/source/images/logo_transparent.png" align="right" width="180" alt="Napari Track Edit logo" />

A napari plugin for interactive visualization, navigation, and editing of object tracking results. You can open and edit existing tracking data, manually create new tracking results, or run automatic tracking with [motile](https://github.com/funkelab/motile).
The full documentation of the plugin can be found [here](https://live-image-tracking-tools.github.io/napari-track-edit/).

Motile is a library that makes it easy to solve tracking problems using optimization
by framing the task as an Integer Linear Program (ILP).
See the motile [documentation](https://funkelab.github.io/motile)
for more details on the concepts and method.

----------------------------------

## Installation

Users can download and install an executable application from the github release, or
install from `pypi` in the environment of their choice (e.g. `venv`, `conda`) with the command
`pip install napari-track-edit`.
Currently, napari-track-edit requires python >=3.11.

### Recommended extras

For better performance, you can install optional extras:

- **numba**: Speeds up candidate graph construction significantly.
  ```bash
  pip install napari-track-edit[numba]
  ```

- **gurobi**: Uses the Gurobi solver instead of the default open-source solver. Gurobi is
  much faster but requires a license (free for academics).
  ```bash
  pip install napari-track-edit[gurobi]
  ```

You can install multiple extras at once: `pip install napari-track-edit[numba,gurobi]`.

### Gurobi license version mismatch

If you have a Gurobi license and encounter an error about license version mismatch,
you may need to install a specific version of `gurobipy` that matches your license.
Use one of the version-specific extras:

```bash
pip install napari-track-edit[gurobi12]  # For Gurobi 12.x licenses
pip install napari-track-edit[gurobi13]  # For Gurobi 13.x licenses
```

### For developers

Developers can clone the GitHub repository and then use `uv` to install and run the code.
See the developer guide in [`DEVELOPER.md`](DEVELOPER.md) for more information.

## Usage
Start napari and open all widgets via `Plugins` > `Napari Track Edit` > `Open all widgets`.

From here you can:
- load your own Labels or Points data to [track with motile](https://live-image-tracking-tools.github.io/napari-track-edit/tracking.html#tracking-with-motile),
- load an image to [manually track objects](https://live-image-tracking-tools.github.io/napari-track-edit/tracking.html#tracking-from-scratch),
- or [load existing tracking data](https://live-image-tracking-tools.github.io/napari-track-edit/saving_loading.html#loading-tracks) to explore or edit.

If you would like to see an example first, go to `Plugins` > `Napari Track Edit` > `Widget - Getting started`, and click on one of the two examples, `Hela cells (2D)` or `Mouse embryo (3D)`, to download and view them:

- Fluo-N2DL-HeLa is a 2D dataset of images and segmentations of HeLa cells from the [`cell tracking challenge`](https://celltrackingchallenge.net/2d-datasets/).
- Mouse Embryo Membrane is a 3D dataset of images and segmentations of a membrane labeled developing early mouse embryo (4-26 cells)
from [`Fabrèges et al (2024)`](https://www.science.org/doi/10.1126/science.adh1145) available [`here`](https://zenodo.org/records/13903500).

For details, please read the [documentation](https://live-image-tracking-tools.github.io/napari-track-edit/).
If you are new to napari-track-edit, you can follow this [tutorial](https://live-image-tracking-tools.github.io/napari-track-edit/napari-track-edit_tutorial.html) to learn the basics.

https://github.com/user-attachments/assets/cd23271d-bbe6-40c2-80cb-8404136a564a

## Issues

If you encounter any problems, please
[file an issue](https://github.com/live-image-tracking-tools/napari-track-edit/issues)
along with a detailed description.
