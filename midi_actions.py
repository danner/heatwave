from mido import Message
from pprint import pprint
from constants import base_control_numbers, global_button_notes
# Import only from state.py - no circular dependencies
from state import (
    channels, handle_global_action, adjust_frequency as state_adjust_frequency,
    adjust_volume as state_adjust_volume, set_mute
)

# Function to build note_to_action dictionary
def build_note_to_action():
    note_to_action = {}
    
    for channel in range(8):
        # Rotary encoders (control changes)
        note_to_action[('control_change', 16 + channel, base_control_numbers['frequency_up'])] = ('rotary', channel, 'frequency_up')
        note_to_action[('control_change', 16 + channel, base_control_numbers['frequency_down'])] = ('rotary', channel, 'frequency_down')
        
        # Channel buttons (note_on)
        note_to_action[('note_on', base_control_numbers['mute'] + channel, 127, 0)] = ('button', channel, 'mute')
        note_to_action[('note_on', base_control_numbers['select'] + channel, 127, 0)] = ('button', channel, 'select')
        note_to_action[('note_on', base_control_numbers['r'] + channel, 127, 0)] = ('button', channel, 'r')
        note_to_action[('note_on', base_control_numbers['box'] + channel, 127, 0)] = ('button', channel, 'box')
        
        # Volume control (pitchwheel)
        note_to_action[('pitchwheel', channel)] = ('volume', channel, 'set_volume')
    
    # Add global buttons
    for button_name, note in global_button_notes.items():
        note_to_action[('note_on', note, 127, 0)] = ('global_button', None, button_name)
    
    return note_to_action

# Build the note_to_action dictionary
note_to_action = build_note_to_action()

# Function to handle button press
def handle_button(channel, note, button, midi_out):
    channels[channel][button] = not channels[channel][button]
    midi_out.send(Message('note_on', note=note, velocity=127 if channels[channel][button] else 0))
    print(f"Channel {channel} button {button} {'ON' if channels[channel][button] else 'OFF'}")
    
    # For mute button, call set_mute which will notify listeners
    if button == 'mute':
        set_mute(channel, channels[channel][button])
    return channel

# Function to handle global button press
def handle_global_button(button_name, note, midi_out):
    handle_global_action(button_name, midi_out)

# Function to adjust frequency (wraps state function)
def adjust_frequency(channel, value):
    return state_adjust_frequency(channel, value)

# Function to adjust volume (wraps state function)
def adjust_volume(channel, pitch_value):
    return state_adjust_volume(channel, pitch_value)