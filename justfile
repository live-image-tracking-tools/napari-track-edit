# https://just.systems

test:
    uv run pytest .

start:
    uv run --extra gurobi13 motile_tracker

[working-directory: 'docs']
@docs-build:
  uv run make html
