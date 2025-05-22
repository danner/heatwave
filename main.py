import threading
import time
import pygame
import signal
import sys
from midi import midi_in, midi_out, handle_midi_message
from audio import update_volumes, update_pitches
from state import channels, set_lights_to_current_state, channel_log, load_channel_log, set_current_log_index
import web_server

# Flag to control thread execution
running = True

# Function to update volumes and pitches based on channel states
def audio_thread():
    while running:
        update_volumes(channels)
        update_pitches(channels)
        time.sleep(0.01)  # Small sleep to reduce CPU usage

# MIDI processing thread
def midi_thread():
    try:
        while running:
            # Read MIDI input
            for msg in midi_in.iter_pending():
                handle_midi_message(msg, midi_out)
            time.sleep(0.001)  # Small sleep to reduce CPU usage
    except Exception as e:
        print(f"MIDI thread error: {e}")

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    global running
    print("Shutting down gracefully...")
    running = False
    
    # Clean up resources
    pygame.mixer.quit()
    if hasattr(midi_in, 'close'):
        midi_in.close()
    if hasattr(midi_out, 'close'):
        midi_out.close()
    
    # Exit after a short delay to allow threads to finish
    time.sleep(0.5)
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Load the channel log
channel_log.extend(load_channel_log())
# Set the current log index to the last entry
current_log_index = len(channel_log) - 1
set_current_log_index(current_log_index)
# Load the last item of channel_log into channels
if current_log_index >= 0:
    channels.update(channel_log[current_log_index])
print("loaded ", len(channel_log), " entries")
set_lights_to_current_state(midi_out)

# Print IP address information to help with connection
try:
    import socket
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f"Hostname: {hostname}")
    print(f"IP address: {ip_address}")
    print(f"Web server will be available at: http://{ip_address}:6134")
except Exception as e:
    print(f"Could not determine IP address: {e}")
    print("Please check your network connection and use 'hostname -I' to find your IP")

# Start the audio thread
audio_thread_instance = threading.Thread(target=audio_thread, daemon=True)
audio_thread_instance.start()

# Start the MIDI thread
midi_thread_instance = threading.Thread(target=midi_thread, daemon=True)
midi_thread_instance.start()

# Start the web server in the main thread
print("Web server starting at http://localhost:6134")
web_server.start_web_server(channels)