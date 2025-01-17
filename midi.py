import mido
from mido import MidiFile, Message, open_input, open_output
from state import channels, global_buttons, note_to_action, adjust_frequency, adjust_volume, handle_button, handle_global_button

# List all available MIDI ports
print("Available MIDI ports:")
print(mido.get_input_names())
print(mido.get_output_names())

# Select the SMC-Mixer ports
input_name = 'SMC-Mixer Bluetooth'  # Replace with the actual input port name
output_name = 'SMC-Mixer Bluetooth'  # Replace with the actual output port name

# Open input and output ports
midi_in = open_input(input_name)
midi_out = open_output(output_name)

print(f"Connected to MIDI input: {input_name}")
print(f"Connected to MIDI output: {output_name}")

def handle_midi_message(message, midi_out):
    # print(f"Received MIDI message: {message}")
    # if message.type == 'note_on' or message.type == 'note_off':
    #     print(f"Note {message.note} {'on' if message.type == 'note_on' else 'off'} with velocity {message.velocity}")
    # elif message.type == 'pitchwheel':
    #     print(f"Pitchwheel change on channel {message.channel} with pitch {message.pitch}")

    # Check if the message is in the mapping
    if message.type == 'control_change':
        action = note_to_action.get(('control_change', message.control, message.value))
    elif message.type == 'note_on' or message.type == 'note_off':
        action = note_to_action.get(('note_on', message.note, message.velocity, message.channel))
    elif message.type == 'pitchwheel':
        action = note_to_action.get(('pitchwheel', message.channel))

    if action:
        action_type, channel, action_name = action
        # print(f"Action: {action_type}, Channel: {channel}, Name: {action_name}")
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
            handle_global_button(action_name)
    else:
        print(f"Unhandled MIDI message: {message}")