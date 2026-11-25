# https://just.systems

test:
    uv run pytest .

start:
    uv run napari-track-edit

[working-directory: 'docs']
@docs-build:
  uv run make html
