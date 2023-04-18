class Bar:
    def __init__(self, string, time_sig=(4, 4), key_sig=[]):
        pass
    
    def parse(self, string):
        dur_regexp = r'[whqestxuy]'
        note_regexp = r'[cdefgab][0-9]'
        
    def to_midi(self, channel):
        pass
