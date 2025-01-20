base_control_numbers = {
    'frequency_up': 1,
    'frequency_down': 65,
    'set_volume': 0,
    'mute': 16,
    'select': 8,
    'r': 0,
    'box': 24,
}

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

def get_note_for_button(channel, button):
    button_to_note = {
        'mute': base_control_numbers['mute'] + channel,
        'select': base_control_numbers['select'] + channel,
        'r': base_control_numbers['r'] + channel,
        'box': base_control_numbers['box'] + channel,
    }
    return button_to_note[button]