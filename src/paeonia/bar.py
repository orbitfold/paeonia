import re

class Bar:
    def __init__(self, string, time_sig=(4, 4), key_sig=[]):
        pass
    
    def parse(self, string):
        dur_regexp = re.compile(r'-?[whqestxuy].?.?.?')
        note_regexp = re.compile(r'[CDEFGAB](s?|b?)[0-9]')
        tokens = string.split(" ")
        for token in tokens:
            if dur_regexp.match(token):
                pass
            elif note_regexp.match(token):
                pass
            else:
                raise RuntimeError(f"Invalid token! ({token})")
        
    def to_midi(self, channel):
        pass
