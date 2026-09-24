# https://just.systems

test:
    uv run pytest .

start:
    uv run --extra gurobipy13 napari-track-edit

[working-directory: 'docs']
@docs-build:
  uv run make html
