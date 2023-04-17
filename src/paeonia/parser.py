DURATIONS = ['w', 'h', 'q', 's', 't', 'x', 'u', 'y']
PITCHES = ['c', 'd', 'e', 'f', 'g', 'a', 'b']

def parse(string):
    lst = string.split(" ")
    duration = 0.25
    for token in lst:
        if token[0] == '-':
            pass

