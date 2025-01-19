from mido import Message
from pprint import pprint
import json
import copy

min_volume = float('inf')
max_volume = float('-inf')
channel_log = []

# State tracking for channels and global buttons
channels = {
    0: {'frequency': 110, 'volume': 1.0, 'mute': False, 'select': False, 'r': False, 'box': False},
    1: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
    2: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
    3: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
    4: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
    5: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
    6: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
    7: {'frequency': 110, 'volume': 1.0, 'mute': True, 'select': False, 'r': False, 'box': False},
}

# Base control numbers for each action
base_control_numbers = {
    'frequency_up': 1,
    'frequency_down': 65,
    'set_volume': 0,
    'mute': 16,
    'select': 8,
    'r': 0,
    'box': 24,
}

# Add global buttons
global_button_notes = {
    'play': 94,
    'pause': 93,
    'record': 95,
    'rewind': 91,
    'fast_forward': 92,
    'back': 46,
    'forward': 47,
    'up': 96,
    'down': 97,
    'left': 98,
    'right': 99,
}

# Function to build note_to_action dictionary
def build_note_to_action():
    note_to_action = {}
    for channel in range(8):
        note_to_action[('control_change', 16 + channel, base_control_numbers['frequency_up'])] = ('rotary', channel, 'frequency_up')
        note_to_action[('control_change', 16 + channel, base_control_numbers['frequency_down'])] = ('rotary', channel, 'frequency_down')
        note_to_action[('pitchwheel', channel)] = ('volume', channel, 'set_volume')
        note_to_action[('note_on', base_control_numbers['mute'] + channel, 127, 0)] = ('button', channel, 'mute')
        note_to_action[('note_on', base_control_numbers['select'] + channel, 127, 0)] = ('button', channel, 'select')
        note_to_action[('note_on', base_control_numbers['r'] + channel, 127, 0)] = ('button', channel, 'r')
        note_to_action[('note_on', base_control_numbers['box'] + channel, 127, 0)] = ('button', channel, 'box')


    for button, note in global_button_notes.items():
        note_to_action[('note_on', note, 127, 0)] = ('global_button', 0, button)

    return note_to_action

# Build the note_to_action dictionary
note_to_action = build_note_to_action()
# pprint(note_to_action)

# Function to handle frequency adjustment 
def adjust_frequency(channel, value):
    adjustment = 0.1 if channels[channel]['select'] else 1.0
    channels[channel]['frequency'] += value * adjustment


# Function to handle volume adjustment
def adjust_volume(channel, value):
    global min_volume, max_volume

    # Update min and max volume values
    if value < min_volume:
        min_volume = value
    if value > max_volume:
        max_volume = value

    # Calculate the volume ratio between 0.0 and 1.0
    if max_volume != min_volume:
        volume_ratio = (value - min_volume) / (max_volume - min_volume)
    else:
        volume_ratio = 0.0

    channels[channel]['volume'] = volume_ratio

# Function to handle button press
def handle_button(channel, note, button, midi_out):
    channels[channel][button] = not channels[channel][button]
    midi_out.send(Message('note_on', note=note, velocity=127 if channels[channel][button] else 0))
    print(f"Channel {channel} button {button} {'ON' if channels[channel][button] else 'OFF'}")

# Function to handle global button press
def handle_global_button(button_name, note, midi_out):
    print(f"Global button {button_name} pressed")

    if button_name == 'play':
        # display all frequencies on one line
        print(f"Frequencies: {', '.join([str(channels[i]['frequency']) for i in range(8)])}")

    if button_name == 'pause':
        # Mute all channels
        for channel in channels:
            channels[channel]['mute'] = True
            mute_note = base_control_numbers['mute'] + channel
            midi_out.send(Message('note_on', note=mute_note, velocity=127))
        print(f"Channels muted")

    if button_name == 'record':
        # Print the channels' state
        pprint(channels)
        
        # Append the current state to the channel_log
        channel_log.append(copy.deepcopy(channels))
        
        # Write the channel_log to a log file as multiple lines of JSON
        with open('channel_log.json', 'w') as log_file:
            for entry in channel_log:
                log_file.write(json.dumps({int(k): v for k, v in entry.items()}) + '\n')

# Function to load the state log into an array
def load_channel_log():
    try:
        with open('channel_log.json', 'r') as log_file:
            state_log = [{int(k): v for k, v in json.loads(line).items()} for line in log_file]
            return state_log
    except FileNotFoundError:
        print("Channel log file not found.")
        return [channels]

# Function to set all lights to the current state of the channels
def set_lights_to_current_state(midi_out):
    for channel, states in channels.items():
        for button, state in states.items():
            if button in ['mute', 'select', 'r', 'box']:
                note = get_note_for_button(channel, button)
                velocity = 127 if state else 0
                midi_out.send(Message('note_on', note=note, velocity=velocity))
                # print(f"Channel {channel} button {button} {'ON' if state else 'OFF'}")

def get_note_for_button(channel, button):
    # Mapping of buttons to their corresponding MIDI notes
    button_to_note = {
        'mute': base_control_numbers['mute'] + channel,
        'select': base_control_numbers['select'] + channel,
        'r': base_control_numbers['r'] + channel,
        'box': base_control_numbers['box'] + channel,
    }
    return button_to_note[button]


