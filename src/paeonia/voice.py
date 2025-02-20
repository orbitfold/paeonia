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
