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

# Generate sine wave function ensuring zero-crossings
def generate_sine_wave(freq, amplitude, rate):
    # Ensure we have a complete number of cycles for smooth looping
    cycles = max(1, int(rate / freq / 10))  # Use multiple cycles for better quality
    # Number of samples needed for complete cycles
    samples = int((cycles / freq) * rate)
    t = np.linspace(0, 2 * np.pi * cycles, samples, endpoint=False)
    wave = amplitude * np.sin(t)
    # Apply soft clipping to prevent harsh distortion if amplitude is too high
    wave = soft_clip(wave)
    return wave.astype(np.float32)

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

# Function to play all sounds continuously
def play_all_sounds():
    for sound in sounds:
        sound.play(-1)

# Function to update the volume of each sound based on the mute state
def update_volumes(channels):
    for i, channel in channels.items():
        volume = channel['volume'] if not channel['mute'] else 0
        if volume != volumes[i]:  # Only update if the volume has changed
            print(f"Updating volume for channel {i} to {volume}")
            volumes[i] = volume
            # Apply master volume to individual channel volume
            sounds[i].set_volume(volume * MASTER_VOLUME)

# Function to update the pitch of each sound based on the frequency
def update_pitches(channels):
    for i, channel in channels.items():
        freq = max(1, channel['frequency'])
        if freq != frequencies[i]:  # Only update if the frequency has changed
            print(f"Updating frequency for channel {i} to {freq}")
            frequencies[i] = freq
            # Create new sound with zero-crossings at both ends
            wave = generate_sine_wave(freq, AMPLITUDE * MASTER_VOLUME, RATE)
            # Fade out current sound before stopping it
            sounds[i].fadeout(50)  # Short 50ms fadeout
            
            # Use gevent.sleep instead of pygame.time.wait
            gevent.sleep(0.05)  # Wait for fadeout to complete
            
            sounds[i].stop()
            sounds[i] = pygame.sndarray.make_sound((wave * 32767).astype(np.int16))
            sounds[i].set_volume(volumes[i] * MASTER_VOLUME)  # Respect the previously set volume
            sounds[i].play(-1)

# Start playing all sounds
play_all_sounds()