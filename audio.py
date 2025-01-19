import numpy as np
import pygame

# Initialize pygame mixer
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=4096)

# Audio setup for sine wave generation
RATE = 44100  # Sampling rate
AMPLITUDE = 0.5  # Default volume

# Generate sine wave function
def generate_sine_wave(freq, amplitude, rate):
    duration = 1 / freq  # Ensure the wave completes one cycle
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    wave = amplitude * np.sin(2 * np.pi * freq * t)
    return wave.astype(np.float32)

# Function to create and return a pygame Sound object
def create_sound(freq, amplitude, rate):
    wave = generate_sine_wave(freq, amplitude, rate)
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
            sounds[i].set_volume(volume)

# Function to update the pitch of each sound based on the frequency
def update_pitches(channels):
    for i, channel in channels.items():
        freq = max(1, channel['frequency'])
        if freq != frequencies[i]:  # Only update if the frequency has changed
            print(f"Updating frequency for channel {i} to {freq}")
            frequencies[i] = freq
            wave = generate_sine_wave(freq, AMPLITUDE, RATE)
            sounds[i].stop()
            sounds[i] = pygame.sndarray.make_sound((wave * 32767).astype(np.int16))
            sounds[i].set_volume(volumes[i])  # Respect the previously set volume
            sounds[i].play(-1)

# Start playing all sounds
play_all_sounds()