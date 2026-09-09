Rendered score analysis
=======================

Score analysis can be projected directly onto LilyPond output without
changing the score::

   score.show(analysis=True)

The Boolean option uses a readable composition-oriented preset.  For a
custom selection, or to derive harmony from only part of an ensemble, pass
an options object::

   from paeonia.annotations import AnalysisRenderOptions

   options = AnalysisRenderOptions(
       source_staves=("marimba_right", "marimba_left"),
       harmony=True,
       roman_numerals=True,
       non_chord_tones=True,
   )
   score.show(analysis=options)

Dense numerical analyses are opt-in.  The diagnostic preset enables every
available annotation lane::

   score.show(analysis=AnalysisRenderOptions.diagnostic())

Annotations are computed at render time, so edits made through a voice or
score window are reflected on the next call.  The same renderer-independent
objects can be inspected without invoking LilyPond::

   annotations = score.analysis_annotations(options)

API
---

.. automodule:: paeonia.annotations
   :members:
   :undoc-members:
   :show-inheritance:
