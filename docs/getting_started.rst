Getting started
===============

Installation
------------

Install Paeonia directly from its GitHub repository:

.. code-block:: console

   pip install git+https://github.com/orbitfold/paeonia.git

Basic model
-----------

Construct a bar, place it in a voice, and attach that voice to a score:

.. code-block:: python

   from paeonia import Bar, Score, Tonality, Voice

   bar = Bar("C E G", tonality=Tonality("C", "major"))
   voice = Voice([bar], name="Melody")

   score = Score(title="First score")
   score["melody"] = voice

Pitches retain their written spelling, so enharmonic pitches can sound alike
without becoming structurally equal:

.. code-block:: python

   from paeonia import Pitch

   d_sharp = Pitch.parse("D#4")
   e_flat = Pitch.parse("Eb4")

   assert d_sharp != e_flat
   assert d_sharp.midi == e_flat.midi

Tonal transformations
---------------------

:meth:`paeonia.Bar.apply_tonality` reinterprets scale degrees in a target
tonality. :meth:`paeonia.Bar.quantize_to_tonality` instead moves pitches to
nearby members of a pitch collection by chromatic distance.

.. code-block:: python

   source = Bar("C E F# G", tonality=Tonality("C", "major"))

   transformed = source.apply_tonality(Tonality("D", "dorian"))
   quantized = source.quantize_to_tonality(Tonality("D", "major"))

Rendering and playback
----------------------

Model transformations and conversion to MIDI or LilyPond strings require no
external executables. Engraved display with ``show()`` requires LilyPond;
audio preview with ``play()`` requires FluidSynth.
