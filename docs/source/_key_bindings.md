<!-- Key bindings and mouse functions, shown on the key_bindings page of the docs and
     included in the tutorial (napari-track-edit_tutorial.md). -->

Shortcuts work in the napari viewer (with a tracks layer selected), the Lineage View and the Table (click on it first to give it focus).
Nodes can be clicked as points or labels in the viewer, as nodes in the Lineage View, and as rows in the Table (drag to select a range).

### Selection

| Key / mouse | Action |
| ----------- | ------ |
| Click on a node | Select this node (centers the view on it if it is the only selected node) |
| `Shift` + click | Add/remove this node to/from the selection |
| `Ctrl`/`Cmd` + click | Center the view on this node, without changing the selection |
| `Alt`/`Option` + click | Make this node's tracklet ID the current one, without changing the selection or time point |
| Mouse drag | Select multiple nodes: 'select points' tool (Points layer), `Shift` + drag (Lineage View) |
| `Esc` | Clear the selection |
| `E` | Restore the last selection |
| `P` / mouse back | Select the previous node set from the selection history |
| `N` / mouse forward | Select the next node set from the selection history |

### Editing

| Key | Action |
| --- | ------ |
| `M` | Start a new track: assign a new track id, and a new segmentation label if necessary |
| `D` or `Del` | Delete the selected nodes |
| `S` | Swap the incoming edges of two nodes at the same time point |
| `C` | Connect the selected nodes into one track, keeping existing outgoing edges as divisions |
| `Shift` + `C` | Connect the selected nodes into one linear track, breaking existing outgoing edges |
| `B` | Break the edges between the selected nodes (edges to other nodes are kept) |
| `Y` | Make or break a division between a parent node and its two children |
| `H` | Merge each set of selected nodes that shares a time point into a single node |
| `Z` | Undo the last editing action |
| `R` | Redo the last undone editing action |

### View

| Key / mouse | Action |
| ----------- | ------ |
| `/` | Hide or show all currently active widgets |
| `Q` | Cycle the display mode: All → Lineage → Group (Group only when groups exist) |
| `T` | Center the orthogonal views on the mouse cursor |
| Click column header | Sort the Table by this column |

### Lineage view

| Key / mouse | Action |
| ----------- | ------ |
| `Q` | Switch between all lineages and the selected lineages |
| `W` | Switch the lineage view between the tree plot and a feature plot |
| `F` | Flip the axes of the lineage view |
| `←` / `→` | Select the node to the left / right |
| `↑` / `↓` | Select the parent / child node, or the next / previous lineage (selected lineages view) |
| Scroll (+ `X` / `Y`) | Zoom in or out (only along the x / y axis) |
| Right drag | Stretch or squeeze the axes (horizontally: x axis, vertically: y axis) |
| Mouse drag | Pan |
| Right click | Reset the view |
