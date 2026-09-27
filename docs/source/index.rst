Napari Track Edit
=================

|source code| |tests|

.. |source code| image:: https://img.shields.io/badge/GitHub-100000?logo=github&logoColor=white
   :target: https://github.com/live-image-tracking-tools/napari-track-edit

.. |tests| image:: https://github.com/live-image-tracking-tools/napari-track-edit/workflows/tests/badge.svg
   :target: https://github.com/live-image-tracking-tools/napari-track-edit/actions

.. image:: images/logo_transparent.png
   :align: right
   :width: 180px
   :alt: Napari Track Edit logo

Napari Track Edit is a napari plugin for interactive visualization, navigation, and
editing of object tracking results. You can open and edit existing tracking data,
manually create new tracking results, or run automatic tracking with `motile`_.
Motile is a library that makes it easy to solve tracking problems using optimization
by framing the task as an Integer Linear Program (ILP).
See the `motile documentation`_ for more details on the concepts and method.

.. video:: images/results_demo_720p.mp4
   :width: 720

.. toctree::
   :maxdepth: 2
   :caption: User guide

   getting_started
   viewing
   tracking
   features
   groups
   editing
   saving_loading
   key_bindings
   Tutorial <napari-track-edit_tutorial>

.. toctree::
   :maxdepth: 1
   :caption: Reference

   API reference <autoapi/napari_track_edit/index>

.. _motile: https://github.com/funkelab/motile
.. _motile documentation: https://funkelab.github.io/motile
