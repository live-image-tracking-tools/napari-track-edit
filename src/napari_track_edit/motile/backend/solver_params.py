from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SolverParams(BaseModel):
    """The set of solver parameters supported in the motile tracker.
    Used to build the UI as well as store parameters for runs.
    """

    model_config = ConfigDict(validate_assignment=True)

    max_edge_distance: float = Field(
        50.0,
        title="Max Move Distance",
        description=r"""The maximum distance an object center can move between time frames.
Objects further than this cannot be matched, but making this value larger will increase solving time.""",
    )
    max_children: int = Field(
        2,
        title="Max Children",
        description="The maximum number of object in time t+1 that can be linked to an item in time t.\nIf no division, set to 1.",
    )
    edge_selection_cost: float | None = Field(
        -20.0,
        title="Edge Selection",
        description=r"""Cost for selecting an edge. The more negative the value, the more edges will be selected.""",
    )
    appear_cost: float | None = Field(
        30,
        title="Appear",
        description=r"""Cost for starting a new track. A higher value means fewer and longer selected tracks.""",
    )
    division_cost: float | None = Field(
        20,
        title="Division",
        description=r"""Cost for a track dividing. A higher value means fewer divisions.
If this cost is higher than the appear cost, tracks will likely never divide.""",
    )
    distance_cost: float | None = Field(
        1,
        title="Distance",
        description=r"""Use the distance between objects as a feature for selecting edges.
The value is multiplied by the edge distance to create a cost for selecting that edge.""",
    )
    iou_cost: float | None = Field(
        -5,
        title="IoU",
        description=r"""Use the intersection over union between objects as a feature for selecting tracks.
The value is multiplied by the IOU between two cells to create a cost for selecting the edge
between them. Recommended to be negative, since bigger IoU is better.""",
    )
    window_size: int | None = Field(
        None,
        title="Window Size",
        description=r"""Number of time frames to solve at once when using chunked solving.
If None, solve all frames at once. If set, the problem will be solved in windows
of this size, with overlapping regions pinned to maintain consistency.""",
        json_schema_extra={"ui_default": 50},
    )
    overlap_size: int | None = Field(
        None,
        title="Overlap Size",
        description=r"""Number of time frames to overlap between windows when using chunked solving.
Only used if window_size is set. The overlap region from the previous window will
be pinned when solving the next window. Must be less than window_size.""",
        json_schema_extra={"ui_default": 5},
    )
    single_window_start: int | None = Field(
        None,
        title="Single Window Start",
        description=r"""If set along with window_size, only solve a single window starting at this
frame index. Useful for interactively testing parameters on a small portion of the data
before running on the full dataset.""",
        json_schema_extra={"ui_default": 0},
    )

    @field_validator("window_size")
    @classmethod
    def window_size_must_be_at_least_two(cls, v: int | None) -> int | None:
        if v is not None and v < 2:
            raise ValueError("window_size must be at least 2")
        return v

    @field_validator("overlap_size")
    @classmethod
    def overlap_size_must_be_positive(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("overlap_size must be at least 1")
        return v
