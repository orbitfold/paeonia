import mido
import time

class MidiOutput:
  def __init__(self):
    pass

  def list_devices(self):
    print(mido.get_output_names())

  def set_device(self, name):
    self.device = name
    self.outport = mido.open_output(name)

  def send(self, msg):
    pass
