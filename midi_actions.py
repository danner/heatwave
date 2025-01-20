from mido import Message
from pprint import pprint
import json
import copy
from state import channels, adjust_frequency, adjust_volume, set_lights_to_current_state, channel_log, get_current_log_index, set_current_log_index
from constants import base_control_numbers, global_button_notes

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

# Function to handle button press
def handle_button(channel, note, button, midi_out):
    channels[channel][button] = not channels[channel][button]
    midi_out.send(Message('note_on', note=note, velocity=127 if channels[channel][button] else 0))
    print(f"Channel {channel} button {button} {'ON' if channels[channel][button] else 'OFF'}")

# Function to handle global button press
def handle_global_button(button_name, note, midi_out):
    current_log_index = get_current_log_index()

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
        with open('channel_log.jsonl', 'w') as log_file:
            for entry in channel_log:
                log_file.write(json.dumps({int(k): v for k, v in entry.items()}) + '\n')

    if button_name == 'fast_forward':
        # Move forward in the channel_log
        if current_log_index < len(channel_log) - 1:
            current_log_index += 1
            set_current_log_index(current_log_index)
            channels.update(channel_log[current_log_index])
            set_lights_to_current_state(midi_out)
            print(f"Moved forward to log index {current_log_index}")

    if button_name == 'rewind':
        # Move backward in the channel_log
        if current_log_index > 0:
            current_log_index -= 1
            set_current_log_index(current_log_index)
            channels.update(channel_log[current_log_index])
            set_lights_to_current_state(midi_out)
            print(f"Moved back to log index {current_log_index}")