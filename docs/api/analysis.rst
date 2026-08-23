Score analysis
==============

Vertical analysis begins with :meth:`paeonia.Score.verticalities`. It divides
an aligned bar at every onset and release while retaining sustained notes,
exact rational offsets, written pitch spelling, and staff ownership. The
remaining :class:`~paeonia.Score` methods derive their results from those time
frames and never modify the score.

For example::

   score.verticalities(0)
   score.sonority_at(0, Fraction(1, 2))
   score.harmonic_context(0)
   score.voice_leading_to(0)  # bar 0 to bar 1

Objective methods such as :meth:`paeonia.Score.pitch_class_set`,
:meth:`paeonia.Score.interval_matrix`, :meth:`paeonia.Score.density`, and
:meth:`paeonia.Score.register_analysis` do not require a tonality. Functional
methods use the effective score, voice, and bar tonal context. If selected
staves disagree, pass ``tonality=...`` explicitly or select compatible staves
with ``staves=[...]``.

Analysis result types
---------------------

.. automodule:: paeonia.analysis
   :members:
   :undoc-members:
   :show-inheritance:
