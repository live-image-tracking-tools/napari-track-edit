# Napari Track Edit

[![tests](https://github.com/live-image-tracking-tools/napari-track-edit/workflows/tests/badge.svg)](https://github.com/live-image-tracking-tools/napari-track-edit/actions)
[![codecov](https://codecov.io/gh/live-image-tracking-tools/napari-track-edit/branch/main/graph/badge.svg)](https://codecov.io/gh/live-image-tracking-tools/napari-track-edit)


An application for interactive tracking with [motile](https://github.com/funkelab/motile).
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

You can install multiple extras at once: `pip install napari-track-edit[numba,gurobi]`

### Gurobi license version mismatch

If you have a Gurobi license and encounter an error about license version mismatch,
you may need to install a specific version of `gurobipy` that matches your license.
Use one of the version-specific extras:

```bash
pip install napari-track-edit[gurobi12]  # For Gurobi 12.x licenses
pip install napari-track-edit[gurobi13]  # For Gurobi 13.x licenses
```

Developers can clone the GitHub repository and then  use `uv` to install and run the code.
See the developer guide in `DEVELOPER.md` for more information.

## Usage

Start napari and call the main widget via Plugins > Napari Track Edit > Open all widgets.
2D+time and 3D+time sample data can be loaded via File > Open Sample > Napari Track Edit. You can
track objects in napari Labels or Points layers. For details, please read the
[documentation](https://live-image-tracking-tools.github.io/napari-track-edit/).

![napari_track_edit_quick_demo](https://github.com/user-attachments/assets/07a4a954-3d2d-4d67-8f75-aec11ee14697)

If you are new to using napari-track-edit, you can follow this [tutorial](./assets/napari-track-edit_tutorial.pdf) to learn the basics.

## Package the application into an executable and create the installer

Tagging any branch will automatically trigger the deploy.yml workflow,
which pushes the tagged version to PyPi and creates a github release; draft release if the tag contains "-dev", pre-release if the tag contains "-rc' or a full release otherwise. In case of a draft or pre release, when the user updates the release notes and promotes it to a published release, github will trigger `make_bundle_app.yml` workflow which will create the Linux, Mac and Windows installer and will upload them as release artifacts to github.

## Issues

If you encounter any problems, please
[file an issue](https://github.com/live-image-tracking-tools/napari-track-edit/issues)
along with a detailed description.
