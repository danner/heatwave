from mido import Message

# State tracking for channels and global buttons
channels = {
    0: {'frequency': 440, 'volume': 1.0, 'mute': False, 's': False, 'r': False, 'box': False},
    1: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
    2: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
    3: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
    4: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
    5: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
    6: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
    7: {'frequency': 440, 'volume': 1.0, 'mute': True, 's': False, 'r': False, 'box': False},
}
global_buttons = {'button1': False, 'button2': False, 'button3': False}

# Mapping of MIDI notes to actions
note_to_action = {
    # Channel 0
    ('control_change', 16, 1): ('rotary', 0, 'frequency_up'),
    ('control_change', 16, 65): ('rotary', 0, 'frequency_down'),
    ('pitchwheel', 0): ('volume', 0, 'set_volume'),
    ('note_on', 16, 127, 0): ('button', 0, 'mute'),
    ('note_on', 8, 127, 0): ('button', 0, 's'),
    ('note_on', 0, 127, 0): ('button', 0, 'r'),
    ('note_on', 24, 127, 0): ('button', 0, 'box'),
    # Channel 1
    ('control_change', 17, 1): ('rotary', 1, 'frequency_up'),
    ('control_change', 17, 65): ('rotary', 1, 'frequency_down'),
    ('pitchwheel', 1): ('volume', 1, 'set_volume'),
    ('note_on', 17, 127, 0): ('button', 1, 'mute'),
    ('note_on', 9, 127, 0): ('button', 1, 's'),
    ('note_on', 1, 127, 0): ('button', 1, 'r'),
    ('note_on', 25, 127, 0): ('button', 1, 'box'),
    # Channel 2
    ('control_change', 18, 1): ('rotary', 2, 'frequency_up'),
    ('control_change', 18, 65): ('rotary', 2, 'frequency_down'),
    ('pitchwheel', 2): ('volume', 2, 'set_volume'),
    ('note_on', 18, 127, 0): ('button', 2, 'mute'),
    ('note_on', 10, 127, 0): ('button', 2, 's'),
    ('note_on', 2, 127, 0): ('button', 2, 'r'),
    ('note_on', 26, 127, 0): ('button', 2, 'box'),
    # Channel 3
    ('control_change', 19, 1): ('rotary', 3, 'frequency_up'),
    ('control_change', 19, 65): ('rotary', 3, 'frequency_down'),
    ('pitchwheel', 3): ('volume', 3, 'set_volume'),
    ('note_on', 19, 127, 0): ('button', 3, 'mute'),
    ('note_on', 11, 127, 0): ('button', 3, 's'),
    ('note_on', 3, 127, 0): ('button', 3, 'r'),
    ('note_on', 27, 127, 0): ('button', 3, 'box'),
    # Channel 4
    ('control_change', 20, 1): ('rotary', 4, 'frequency_up'),
    ('control_change', 20, 65): ('rotary', 4, 'frequency_down'),
    ('pitchwheel', 4): ('volume', 4, 'set_volume'),
    ('note_on', 20, 127, 0): ('button', 4, 'mute'),
    ('note_on', 12, 127, 0): ('button', 4, 's'),
    ('note_on', 4, 127, 0): ('button', 4, 'r'),
    ('note_on', 28, 127, 0): ('button', 4, 'box'),
    # Channel 5
    ('control_change', 21, 1): ('rotary', 5, 'frequency_up'),
    ('control_change', 21, 65): ('rotary', 5, 'frequency_down'),
    ('pitchwheel', 5): ('volume', 5, 'set_volume'),
    ('note_on', 21, 127, 0): ('button', 5, 'mute'),
    ('note_on', 13, 127, 0): ('button', 5, 's'),
    ('note_on', 5, 127, 0): ('button', 5, 'r'),
    ('note_on', 29, 127, 0): ('button', 5, 'box'),
    # Channel 6
    ('control_change', 22, 1): ('rotary', 6, 'frequency_up'),
    ('control_change', 22, 65): ('rotary', 6, 'frequency_down'),
    ('pitchwheel', 6): ('volume', 6, 'set_volume'),
    ('note_on', 22, 127, 0): ('button', 6, 'mute'),
    ('note_on', 14, 127, 0): ('button', 6, 's'),
    ('note_on', 6, 127, 0): ('button', 6, 'r'),
    ('note_on', 30, 127, 0): ('button', 6, 'box'),
    # Channel 7
    ('control_change', 23, 1): ('rotary', 7, 'frequency_up'),
    ('control_change', 23, 65): ('rotary', 7, 'frequency_down'),
    ('pitchwheel', 7): ('volume', 7, 'set_volume'),
    ('note_on', 23, 127, 0): ('button', 7, 'mute'),
    ('note_on', 15, 127, 0): ('button', 7, 's'),
    ('note_on', 7, 127, 0): ('button', 7, 'r'),
    ('note_on', 31, 127, 0): ('button', 7, 'box'),
}

# Function to handle frequency adjustment
def adjust_frequency(channel, value):
    channels[channel]['frequency'] += value
    # print(f"Channel {channel} frequency set to {channels[channel]['frequency']} Hz")

# Function to handle volume adjustment
def adjust_volume(channel, value):
    channels[channel]['volume'] = (value + 8192) / 16384
    print(f"Channel {channel} volume set to {channels[channel]['volume']}")

# Function to handle button press
def handle_button(channel, note, button, midi_out):
    channels[channel][button] = not channels[channel][button]
    midi_out.send(Message('note_on', note=note, velocity=127 if channels[channel][button] else 0))
    print(f"Channel {channel} button {button} {'ON' if channels[channel][button] else 'OFF'}")

# Function to handle global button press
def handle_global_button(button_name):
    global_buttons[button_name] = not global_buttons[button_name]
    print(f"Global button {button_name} {'ON' if global_buttons[button_name] else 'OFF'}")