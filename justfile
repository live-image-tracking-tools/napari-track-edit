# https://just.systems

test:
    uv run pytest .

start:
    uv run --extra gurobi13 napari-track-edit

[working-directory: 'docs']
@docs-build:
  uv run make html
