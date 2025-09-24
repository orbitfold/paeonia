# Paeonia

Paeonia is a computer assisted music composition software. It draws a lot of inspiration from Opusmodus but is designed from the ground up to not make you want to jam a fork in your eye. It is also designed to be run in a Jupyter notebook. Which makes more sense then you would initially think actually.

# Basic Use

Here is how to install and use it Google Colab (or any other Jupyter notebook).

It relies on fluidsynth for preview and lilypond for score rendering. So run these commands first inside the Jupyter notebook cell.

```
%%capture
!apt install fluidsynth
!apt install lilypond
```

Then install paeonia.

```
%%capture
!pip install git+https://github.com/orbitfold/paeonia.git
```

After this we can test it by playing a couple of notes and rendering the score.

```
from paeonia import Bar
b = Bar("C' Eb G Bb")
b.show().play()
```
