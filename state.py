import json
import copy
from mido import Message
from constants import base_control_numbers, global_button_notes, get_note_for_button

# Initialize min and max volume variables
min_volume = float('inf')
max_volume = float('-inf')

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

channel_log = []
_current_log_index = -1  # Initialize the current log index

# Callback for channel updates - will be set by web_server.py
_update_callback = None

def register_update_callback(callback_function):
    """Register a function to be called when channel state changes"""
    global _update_callback
    _update_callback = callback_function

def get_current_log_index():
    return _current_log_index

def set_current_log_index(value):
    global _current_log_index
    _current_log_index = value

# Function to handle frequency adjustment 
def adjust_frequency(channel, value):
    adjustment = 0.1 if channels[channel]['select'] else 1.0
    channels[channel]['frequency'] += value * adjustment
    # Notify listeners about the update
    notify_channel_updated(channel)
    return channel

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
    # Notify listeners about the update
    notify_channel_updated(channel)
    return channel

# Function to handle mute state changes
def set_mute(channel, mute_state):
    channels[channel]['mute'] = mute_state
    notify_channel_updated(channel)
    return channel

# Function to mute all channels
def mute_all_channels():
    for channel in range(8):
        channels[channel]['mute'] = True
    notify_all_channels_updated()

# Function to notify that a channel was updated
def notify_channel_updated(channel):
    if _update_callback:
        _update_callback(channel)

# Function to notify that all channels were updated
def notify_all_channels_updated():
    if _update_callback:
        for i in range(8):
            _update_callback(i)

# Function to load the state log into an array
def load_channel_log():
    try:
        with open('channel_log.jsonl', 'r') as log_file:
            state_log = [{int(k): v for k, v in json.loads(line).items()} for line in log_file]
            return state_log
    except FileNotFoundError:
        print("Channel log file not found.")
        return [channels]

# Function to record current state
def record_current_state():
    # Append the current state to the channel_log
    channel_log.append(copy.deepcopy(channels))
    
    # Write the channel_log to a log file as multiple lines of JSON
    with open('channel_log.jsonl', 'w') as log_file:
        for entry in channel_log:
            log_file.write(json.dumps({int(k): v for k, v in entry.items()}) + '\n')
    
    print("Current state recorded")

# Navigate forward in channel log
def navigate_forward(midi_out):
    global _current_log_index
    if _current_log_index < len(channel_log) - 1:
        _current_log_index += 1
        channels.update(channel_log[_current_log_index])
        set_lights_to_current_state(midi_out)
        notify_all_channels_updated()
        print(f"Moved forward to log index {_current_log_index}")

# Navigate backward in channel log
def navigate_backward(midi_out):
    global _current_log_index
    if _current_log_index > 0:
        _current_log_index -= 1
        channels.update(channel_log[_current_log_index])
        set_lights_to_current_state(midi_out)
        notify_all_channels_updated()
        print(f"Moved back to log index {_current_log_index}")

# Function to handle global button actions
def handle_global_action(action_name, midi_out=None):
    if action_name == 'play':
        # Display all frequencies on one line
        print(f"Frequencies: {', '.join([str(channels[i]['frequency']) for i in range(8)])}")
    
    elif action_name == 'pause':
        # Mute all channels
        mute_all_channels()
        if midi_out:
            for channel in range(8):
                mute_note = get_note_for_button(channel, 'mute')
                midi_out.send(Message('note_on', note=mute_note, velocity=127))
        print("All channels muted")
    
    elif action_name == 'record':
        record_current_state()
    
    elif action_name == 'fast_forward':
        navigate_forward(midi_out)
    
    elif action_name == 'rewind':
        navigate_backward(midi_out)

# Function to set all lights to the current state of the channels
def set_lights_to_current_state(midi_out):
    for channel, states in channels.items():
        for button, state in states.items():
            if button in ['mute', 'select', 'r', 'box']:
                note = get_note_for_button(channel, button)
                velocity = 127 if state else 0
                midi_out.send(Message('note_on', note=note, velocity=velocity))

    log_length = len(channel_log)
    current_log_index = get_current_log_index()
    forward_velocity = 127 if current_log_index < len(channel_log) - 1 else 0
    back_velocity = 127 if current_log_index > 0 else 0
    midi_out.send(Message('note_on', note=global_button_notes['fast_forward'], velocity=forward_velocity))
    midi_out.send(Message('note_on', note=global_button_notes['rewind'], velocity=back_velocity))