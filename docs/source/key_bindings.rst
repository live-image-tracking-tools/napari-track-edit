Key bindings and Mouse Functions
================================

Configurable key bindings
*************************

These are the Napari Track Edit actions you can rebind. The table lists the
**defaults**; to change them, open the Napari Track Edit keybindings panel with
*Configure keybindings…* in the Getting Started or Editing & Selection menu.
Your choices are stored in a ``shortcuts.json`` file in the Napari Track Edit
user config directory, so they survive a restart, and *Restore defaults* in
that panel puts these back.

Modifier names are as napari spells them: on macOS ``Meta`` is the Command key
and ``Alt`` is Option. Where two bindings are listed, either one works.

While a tracking layer is selected, these shortcuts take priority over
napari's own bindings for the same key — so, for example, ``Z`` undoes a track
edit rather than switching the layer to pan/zoom mode. The keybindings panel
shows which napari actions each shortcut shadows.

.. include:: _generated/keybinding_defaults.rst

Fixed key bindings and mouse functions
**************************************

These are not rebindable.

Napari viewer and layer mouse functions
---------------------------------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - Click on a point or label
     - Select this node (centers view if only one node selected)
   * - SHIFT + click on point or label
     - Add/remove this node to/from selection (does not center view)
   * - CTRL/CMD + click on point or label
     - Center view on this node (does not change selection)
   * - ALT/OPTION + click on point or label
     - | Make this node's tracklet id the current one tool (does not change the selection or the time point)
   * - Mouse drag with point layer selection tool active
     - Select multiple nodes at once
   * - Mouse button 4 (Back)
     - Select previous node set
   * - Mouse button 5 (Forward)
     - Select next node set

Tree view key and mouse functions
---------------------------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - Click on a node
     - Select this node (centers view if only one node selected)
   * - SHIFT + click on a node
     - Add/remove this node to/from selection (does not center view)
   * - CTRL/CMD + click on a node
     - Center view on this node (does not change selection)
   * - ALT/OPTION + click on a node
     - | Make this node's tracklet id the current one (does not change the selection or the time point)
   * - Scroll
     - Zoom in or out
   * - Scroll + X
     - Restrict zoom to the x-axis of the tree view
   * - Scroll + Y
     - Restrict zoom to the y-axis of the tree view
   * - Mouse drag
     - Pan
   * - Right mouse drag
     - | Squeeze/zoom the axes: drag horizontally to scale the
       | x-axis, vertically to scale the y-axis
   * - SHIFT + Mouse drag
     - Rectangular selection of nodes
   * - Right mouse click
     - Reset view
   * - Mouse button 4 (Back)
     - Select previous node set
   * - Mouse button 5 (Forward)
     - Select next node set
   * - Left arrow
     - Select the node to the left
   * - Right arrow
     - Select the node to the right
   * - Up arrow
     - | Select the parent node (vertical view of all
       | lineages) or the next adjacent lineage
       | (horizontal view of selected lineage)
   * - Down arrow
     - | Select the child node (vertical view of all
       | lineages) or the previous adjacent lineage
       | (horizontal view of selected lineage)
