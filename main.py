import threading
import time
import pygame
from midi import midi_in, midi_out, handle_midi_message
from audio import update_volumes, update_pitches
from state import channels

# Function to update volumes and pitches based on channel states
def audio_thread():
    while True:
        update_volumes(channels)
        update_pitches(channels)

# Start the audio thread
threading.Thread(target=audio_thread, daemon=True).start()

# Main loop
try:
    print("Running... Press Ctrl+C to stop.")
    while True:
        # Read MIDI input
        for msg in midi_in.iter_pending():
            # print(f"MIDI Input: {msg}")
            handle_midi_message(msg, midi_out)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    # Clean up
    midi_in.close()
    midi_out.close()
    pygame.mixer.quit()
    print("Cleaned up resources.")