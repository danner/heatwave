import mido
import gevent  # Change from threading and time to gevent
import time  # Keep for non-critical operations
from mido import MidiFile, Message, open_input, open_output
from state import channels
from midi_actions import note_to_action, adjust_frequency, adjust_volume, handle_button, handle_global_button

# Define a dummy MIDI input class
class DummyMidiInput:
    def __init__(self):
        self.name = "Dummy MIDI Input"
        self._closed = False
    
    def iter_pending(self):
        return []  # No messages when in dummy mode
    
    def close(self):
        self._closed = True
        
    @property
    def closed(self):
        return self._closed

# Define a dummy MIDI output class
class DummyMidiOutput:
    def __init__(self):
        self.name = "Dummy MIDI Output"
        self._closed = False
    
    def send(self, message):
        pass  # Just ignore messages in dummy mode
    
    def close(self):
        self._closed = True
        
    @property
    def closed(self):
        return self._closed

# Initialize with dummy MIDI devices
midi_in = DummyMidiInput()
midi_out = DummyMidiOutput()
midi_connected = False

# Target MIDI device names
target_input_name = 'SMC-Mixer Bluetooth'
target_output_name = 'SMC-Mixer Bluetooth'

def connect_midi_devices():
    """Try to connect to MIDI devices, return True if successful"""
    global midi_in, midi_out, midi_connected
    
    # Safely close existing connections if they're not already closed
    if hasattr(midi_in, 'close') and not getattr(midi_in, 'closed', True):
        midi_in.close()
    if hasattr(midi_out, 'close') and not getattr(midi_out, 'closed', True):
        midi_out.close()
    
    try:
        # Check if our target devices are available
        input_names = mido.get_input_names()
        output_names = mido.get_output_names()
        
        if target_input_name in input_names and target_output_name in output_names:
            print(f"Found MIDI devices. Connecting to {target_input_name}...")
            midi_in = open_input(target_input_name)
            midi_out = open_output(target_output_name)
            midi_connected = True
            print(f"Connected to MIDI input: {midi_in.name}")
            print(f"Connected to MIDI output: {midi_out.name}")
            from state import set_lights_to_current_state
            set_lights_to_current_state(midi_out)  # Update lights to current state
            return True
        else:
            midi_in = DummyMidiInput()
            midi_out = DummyMidiOutput()
            midi_connected = False
            # print("Target MIDI devices not found. Using dummy MIDI devices.")
            return False
    except Exception as e:
        midi_in = DummyMidiInput()
        midi_out = DummyMidiOutput()
        midi_connected = False
        print(f"Error connecting to MIDI devices: {e}")
        return False

# Function to periodically check for MIDI devices
def midi_device_monitor():
    while True:
        if not midi_connected:
            connect_midi_devices()
        gevent.sleep(5)  # Use gevent.sleep instead of time.sleep

def handle_midi_message(message, midi_out):
    # Skip processing if we're using dummy devices
    if not midi_connected:
        return
        
    # Process MIDI message as before
    if message.type == 'control_change':
        action = note_to_action.get(('control_change', message.control, message.value))
    elif message.type == 'note_on':
        action = note_to_action.get(('note_on', message.note, message.velocity, message.channel))
    elif message.type == 'pitchwheel':
        action = note_to_action.get(('pitchwheel', message.channel))
    elif message.type == 'note_off':
        return

    if action:
        action_type, channel, action_name = action
        if action_type == 'rotary':
            if action_name == 'frequency_down':
                adjust_frequency(channel, -1)
            elif action_name == 'frequency_up':
                adjust_frequency(channel, 1)
        elif action_type == 'volume':
            adjust_volume(channel, message.pitch)
        elif action_type == 'button':
            handle_button(channel, message.note, action_name, midi_out)
        elif action_type == 'global_button':
            handle_global_button(action_name, message.note, midi_out)
    else:
        print(f"Unhandled MIDI message: {message}")

# Start the MIDI device monitor as a greenlet instead of thread
midi_monitor_greenlet = gevent.spawn(midi_device_monitor)

# Try to connect to MIDI devices at startup
print("Looking for MIDI devices...")
connect_midi_devices()