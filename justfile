# https://just.systems

test:
    uv run pytest .

start:
    uv run --extra gurobipy13 motile_tracker

[working-directory: 'docs']
@docs-build:
  uv run make html
