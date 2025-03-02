class Voice:
    def __init__(self):
        self.bars = []

    def add_bar(self, bar):
        """Add a new bar to this voice.

        Parameters
        ----------
        bar: Bar
            A Bar object
        """
        self.bars.append(bar)

    def to_midi(self, tpb=480):
        """Return MIDI messages corresponding to this voice.
        """
        message_stream = []
        offset = 0
        for bar in self.bars:
            messages, offset = bar.to_midi(offset, tpb)
            message_stream += messages
        return message_stream

    def preview(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi_file = message_list_to_midi_file(messages, tpb)
        sf_file = download_sf2()
        subprocess.run(['fluidsynth', '-i', sf_file, midi_file])
        os.remove(midi_file)
