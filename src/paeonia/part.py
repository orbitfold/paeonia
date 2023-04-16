class Part:
    def __init__(self):
        pass

    def to_midi(self):
        """Convert this Part to a list with MIDI data.

        Returns
        -------
        A list of lists where each sublist contains midi events for that pulse. We use 64 PPQN resolution.
        """
        midi = None
        for voice in self.voices:
            if midi is None:
                midi = voice.to_midi()
            else:
                voice_midi = voice.to_midi()
                midi = [lst1 + lst2 for (lst1, lst2) in zip(midi, voice_midi)]
        return midi
