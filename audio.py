import numpy as np
import pygame
import gevent

# Initialize pygame mixer
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=4096)

# Audio setup for sine wave generation
RATE = 44100  # Sampling rate
AMPLITUDE = 0.5  # Default volume
MASTER_VOLUME = 0.8  # Master volume to prevent clipping

# Function to perform soft clipping using tanh
def soft_clip(x, threshold=0.8):
    """
    Apply soft clipping to prevent harsh distortion.
    Values approaching ±threshold gradually compress, 
    and values beyond threshold are more aggressively compressed.
    """
    return np.tanh(x / threshold) * threshold

# Generate sine wave ensuring it starts and ends at zero-crossings
def generate_sine_wave(freq, amplitude, rate):
    # Calculate exact number of samples for complete cycles
    # This ensures the waveform starts and ends at zero
    cycle_length = rate / freq  # Samples per cycle
    num_cycles = max(1, int(rate / freq / 10))  # Use multiple cycles for better quality
    samples = int(num_cycles * cycle_length)
    
    # Ensure we have a complete number of cycles (ends at zero)
    t = np.linspace(0, 2 * np.pi * num_cycles, samples, endpoint=False)
    wave = amplitude * np.sin(t)
    
    # Apply soft clipping to prevent harsh distortion if amplitude is too high
    wave = soft_clip(wave)
    return wave.astype(np.float32)

# Function to find a zero-crossing point in a wave (from negative to positive)
def find_zero_crossing(wave):
    for i in range(len(wave) - 1):
        if wave[i] <= 0 and wave[i + 1] > 0:
            return i + 1
    return 0  # Default to start if no zero crossing found

# Function to create and return a pygame Sound object
def create_sound(freq, amplitude, rate):
    # Scale amplitude by master volume to prevent clipping when multiple channels are played
    scaled_amplitude = amplitude * MASTER_VOLUME
    wave = generate_sine_wave(freq, scaled_amplitude, rate)
    sound = pygame.sndarray.make_sound((wave * 32767).astype(np.int16))
    return sound

# Initialize sounds for each channel
sounds = [create_sound(110, AMPLITUDE, RATE) for _ in range(8)]
frequencies = [110 for _ in range(8)]  # Track the current frequency of each channel
volumes = [AMPLITUDE for _ in range(8)]  # Track the current volume of each channel

# Track pending changes for each channel
pending_changes = [None for _ in range(8)]

# Function to play all sounds continuously
def play_all_sounds():
    for sound in sounds:
        sound.play(-1)

# Function to update the volume of each sound based on the mute state
def update_volumes(channels):
    for i, channel in channels.items():
        volume = channel['volume'] if not channel['mute'] else 0
        if volume != volumes[i]:  # Only update if the volume has changed
            print(f"Queuing volume update for channel {i} to {volume}")
            
            # We can update volume directly as it's less prone to clicks
            volumes[i] = volume
            sounds[i].set_volume(volume * MASTER_VOLUME)

# Function to queue up a frequency change for a channel
def update_pitches(channels):
    for i, channel in channels.items():
        freq = max(1, channel['frequency'])
        if freq != frequencies[i]:  # Only update if the frequency has changed
            print(f"Queuing frequency update for channel {i} to {freq}")
            # Queue the change instead of applying immediately
            pending_changes[i] = freq

# Function to monitor and apply pending changes at zero-crossings
def monitor_and_apply_changes():
    """
    Monitor pending changes and apply them at zero-crossings.
    This should be called regularly from your main loop.
    """
    for i, change in enumerate(pending_changes):
        if change is not None:
            # Generate the new wave
            new_freq = change
            wave = generate_sine_wave(new_freq, AMPLITUDE * MASTER_VOLUME, RATE)
            
            # Find a zero crossing in the new wave where we'll start playback
            start_idx = find_zero_crossing(wave)
            
            # Rearrange the wave to start at the zero crossing
            if start_idx > 0:
                wave = np.concatenate((wave[start_idx:], wave[:start_idx]))
            
            # Create new sound
            new_sound = pygame.sndarray.make_sound((wave * 32767).astype(np.int16))
            
            # Get the raw data from the current sound to examine its state
            current_sound_buffer = pygame.sndarray.array(sounds[i])
            
            # Find zero crossing in the current sound buffer
            # We'll use this to time our switch
            zero_idx = find_zero_crossing(current_sound_buffer)
            
            if zero_idx > 0:
                # We found a zero crossing - good time to switch
                sounds[i].stop()
                sounds[i] = new_sound
                sounds[i].set_volume(volumes[i] * MASTER_VOLUME)
                sounds[i].play(-1)
                frequencies[i] = new_freq
                pending_changes[i] = None
                print(f"Applied frequency change for channel {i} at zero-crossing")
            # If we couldn't find a zero crossing, we'll try again next cycle

# Start playing all sounds
play_all_sounds()
