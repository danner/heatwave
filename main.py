import threading
import time
import pygame
from midi import midi_in, midi_out, handle_midi_message
from audio import update_volumes, update_pitches
from state import channels, set_lights_to_current_state, channel_log, load_channel_log, set_current_log_index
from web_server import start_web_server, broadcast_channel_update

# Function to update volumes and pitches based on channel states
def audio_thread():
    while True:
        update_volumes(channels)
        update_pitches(channels)

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

# Start the audio thread
threading.Thread(target=audio_thread, daemon=True).start()

# Start the web server
start_web_server(channels)
print("Web server started at http://localhost:6134")

# Main loop
try:
    print("Running... Press Ctrl+C to stop.")

    while True:
        # Read MIDI input
        for msg in midi_in.iter_pending():
            # print(f"MIDI Input: {msg}")
            handle_midi_message(msg, midi_out)
            # Broadcast channel updates to web clients
            broadcast_channel_update(0)  # For now, just update channel 0

except KeyboardInterrupt:
    print("Stopping...")

finally:
    # Clean up
    midi_in.close()
    midi_out.close()
    pygame.mixer.quit()
    print("Cleaned up resources.")