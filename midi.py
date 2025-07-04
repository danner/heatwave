import mido
import gevent  # Change from threading and time to gevent
from mido import MidiFile, Message, open_input, open_output
from state import channels, register_update_callback
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

# Enable debugging
MIDI_DEBUG = False

# Target MIDI device names - these should match what's shown in mido.get_input/output_names()
target_input_names = ['SMC-Mixer Bluetooth', 'SMC-Mixer', 'SMC-Mixer:SMC-Mixer Bluetooth 128:0']
target_output_names = ['SMC-Mixer Bluetooth', 'SMC-Mixer', 'SMC-Mixer:SMC-Mixer Bluetooth 128:0']

# Function to update MIDI controller when channel state changes
def update_midi_controller(channel):
    """Updates MIDI controller lights and faders when channel state changes"""
    global midi_out, midi_connected
    
    if not midi_connected or not hasattr(midi_out, 'send'):
        return
        
    try:
        # Update mute button light
        from constants import get_note_for_button
        mute_note = get_note_for_button(channel, 'mute')
        midi_out.send(Message('note_on', note=mute_note, 
                             velocity=127 if channels[channel]['mute'] else 0))
        
        # Update select button light
        select_note = get_note_for_button(channel, 'select')
        midi_out.send(Message('note_on', note=select_note, 
                             velocity=127 if channels[channel]['select'] else 0))
        
        # Update r button light
        r_note = get_note_for_button(channel, 'r')
        midi_out.send(Message('note_on', note=r_note, 
                             velocity=127 if channels[channel]['r'] else 0))
        
        # Update box button light
        box_note = get_note_for_button(channel, 'box')
        midi_out.send(Message('note_on', note=box_note, 
                             velocity=127 if channels[channel]['box'] else 0))
        
        # Update fader position with pitch wheel message
        # Convert volume (0.0-1.0) to pitch wheel range (-8192 to 8191)
        volume = channels[channel]['volume']
        pitch_value = int(-8192 + (volume * 16383))
        midi_out.send(Message('pitchwheel', channel=channel, pitch=pitch_value))
        
        if MIDI_DEBUG:
            print(f"MIDI controller updated for channel {channel}")
    except Exception as e:
        print(f"Error updating MIDI controller: {e}")

def connect_midi_devices():
    """Try to connect to MIDI devices, return True if successful"""
    global midi_in, midi_out, midi_connected
    
    # Safely close existing connections if they're not already closed
    if hasattr(midi_in, 'close') and not getattr(midi_in, 'closed', True):
        midi_in.close()
    if hasattr(midi_out, 'close') and not getattr(midi_out, 'closed', True):
        midi_out.close()
    
    # Add a small delay to allow MIDI resources to be properly released
    gevent.sleep(0.5)
    
    try:
        # Check if our target devices are available
        input_names = mido.get_input_names()
        output_names = mido.get_output_names()
        
        if MIDI_DEBUG:
            print("\n----- MIDI Device Debug Info -----")
            print(f"Available MIDI inputs ({len(input_names)}):")
            for i, name in enumerate(input_names):
                print(f"  {i}: '{name}'")
            
            print(f"\nAvailable MIDI outputs ({len(output_names)}):")
            for i, name in enumerate(output_names):
                print(f"  {i}: '{name}'")
            
            print("\nTarget input names we're looking for:")
            for name in target_input_names:
                status = "✓" if name in input_names else "✗"
                print(f"  {status} '{name}'")
            
            print("\nTarget output names we're looking for:")
            for name in target_output_names:
                status = "✓" if name in output_names else "✗"
                print(f"  {status} '{name}'")
            print("---------------------------------\n")
        
        # Try exact matching first
        matching_input = None
        matching_output = None
        
        # Try exact match
        for target in target_input_names:
            if target in input_names:
                matching_input = target
                break
                
        for target in target_output_names:
            if target in output_names:
                matching_output = target
                break
        
        # If exact match fails, try substring matching
        if not matching_input or not matching_output:
            if MIDI_DEBUG:
                print("Exact match failed, trying substring matching...")
            
            for name in input_names:
                for target in target_input_names:
                    if target in name or name in target:
                        matching_input = name
                        if MIDI_DEBUG:
                            print(f"Found input via substring match: '{matching_input}'")
                        break
                if matching_input:
                    break
                    
            for name in output_names:
                for target in target_output_names:
                    if target in name or name in target:
                        matching_output = name
                        if MIDI_DEBUG:
                            print(f"Found output via substring match: '{matching_output}'")
                        break
                if matching_output:
                    break
        
        if matching_input and matching_output:
            print(f"Found MIDI devices. Connecting to {matching_input}...")
            try:
                # Add retry logic for opening MIDI input
                retry_count = 0
                while retry_count < 3:
                    try:
                        midi_in = open_input(matching_input)
                        print(f"Successfully opened input device: {matching_input}")
                        break
                    except Exception as e:
                        retry_count += 1
                        print(f"Retry {retry_count}/3: Error opening input device '{matching_input}': {e}")
                        gevent.sleep(1)  # Wait a second before retrying
                
                if retry_count == 3:
                    print(f"Failed to open MIDI input after 3 attempts")
                    return False
            except Exception as e:
                print(f"Error opening input device '{matching_input}': {e}")
                return False
                
            try:
                # Add retry logic for opening MIDI output
                retry_count = 0
                while retry_count < 3:
                    try:
                        midi_out = open_output(matching_output)
                        print(f"Successfully opened output device: {matching_output}")
                        break
                    except Exception as e:
                        retry_count += 1
                        print(f"Retry {retry_count}/3: Error opening output device '{matching_output}': {e}")
                        gevent.sleep(1)  # Wait a second before retrying
                
                if retry_count == 3:
                    print(f"Failed to open MIDI output after 3 attempts")
                    if hasattr(midi_in, 'close'):
                        midi_in.close()
                    return False
            except Exception as e:
                print(f"Error opening output device '{matching_output}': {e}")
                if hasattr(midi_in, 'close'):
                    midi_in.close()
                return False
                
            midi_connected = True
            print(f"Connected to MIDI input: {midi_in.name}")
            print(f"Connected to MIDI output: {midi_out.name}")
            
            # Register the MIDI controller update callback
            register_update_callback(update_midi_controller)
            print("Registered MIDI controller update callback")
            
            # Add error handling for initial MIDI test
            try:
                # Wait before sending the initial test message
                gevent.sleep(0.5)
                # Send a silent test message - Control Change for channel 15 (usually unused)
                test_msg = Message('control_change', channel=15, control=127, value=0)
                midi_out.send(test_msg)
                print("Test message sent successfully!")
                
                from state import set_lights_to_current_state
                set_lights_to_current_state(midi_out)  # Update lights to current state
                return True
            except Exception as e:
                print(f"Error during initial MIDI handshake: {e}")
                print("Try running fix_bluetooth_midi.sh to repair the Bluetooth MIDI profile")
                if hasattr(midi_in, 'close'):
                    midi_in.close()
                if hasattr(midi_out, 'close'):
                    midi_out.close()
                return False
        else:
            if MIDI_DEBUG:
                if not matching_input:
                    print("No matching input device found!")
                if not matching_output:
                    print("No matching output device found!")
                    
            midi_in = DummyMidiInput()
            midi_out = DummyMidiOutput()
            midi_connected = False
            return False
    except Exception as e:
        print(f"General error in connect_midi_devices: {e}")
        midi_in = DummyMidiInput()
        midi_out = DummyMidiOutput()
        midi_connected = False
        return False

# Function to periodically check for MIDI devices
def midi_device_monitor():
    while True:
        if not midi_connected:
            connect_midi_devices()
        gevent.sleep(5)

def handle_midi_message(message, midi_out):
    """Process incoming MIDI messages and update system state"""
    # Skip processing if we're using dummy devices
    if not midi_connected:
        return
        
    try:
        if MIDI_DEBUG:
            print(f"Processing MIDI message: {message}")
            
        # Process MIDI message types
        if message.type == 'control_change':
            action = note_to_action.get(('control_change', message.control, message.value))
        elif message.type == 'note_on':
            action = note_to_action.get(('note_on', message.note, message.velocity, message.channel))
        elif message.type == 'pitchwheel':
            action = note_to_action.get(('pitchwheel', message.channel))
        elif message.type == 'note_off':
            return  # No action for note_off
        else:
            # Log unknown MIDI message types if debugging
            if MIDI_DEBUG:
                print(f"Unrecognized MIDI message type: {message.type}")
            return
            
        if action:
            action_type, channel, action_name = action
            if MIDI_DEBUG:
                print(f"Action: {action_type}, Channel: {channel}, Name: {action_name}")
                
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
            # Only log unhandled messages if debugging is enabled
            if MIDI_DEBUG:
                print(f"Unhandled MIDI message: {message}")
    except Exception as e:
        print(f"Error handling MIDI message: {e}")

# Create a more reliable MIDI processing loop
def midi_input_processor():
    """Process MIDI input messages from the controller"""
    global midi_in, midi_connected
    
    while True:
        # Only process if we have a valid MIDI input connection
        if midi_connected and hasattr(midi_in, 'iter_pending'):
            try:
                for message in midi_in.iter_pending():
                    handle_midi_message(message, midi_out)
            except Exception as e:
                print(f"Error in MIDI input processing: {e}")
        
        # Sleep briefly to prevent CPU overuse
        gevent.sleep(0.001)

# Start the MIDI device monitor as a greenlet instead of thread
midi_monitor_greenlet = gevent.spawn(midi_device_monitor)

# Start the MIDI input processor as a greenlet
midi_input_greenlet = gevent.spawn(midi_input_processor)

# Try to connect to MIDI devices at startup
print("Looking for MIDI devices...")
connect_midi_devices()