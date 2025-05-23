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

# Generate sine wave with envelope to prevent clicks
def generate_sine_wave(freq, amplitude, rate, fade_ms=10):
    # Ensure we have a complete number of cycles for smooth looping
    cycles = max(1, int(rate / freq / 10))  # Use multiple cycles for better quality
    # Number of samples needed for complete cycles
    samples = int((cycles / freq) * rate)
    t = np.linspace(0, 2 * np.pi * cycles, samples, endpoint=False)
    wave = amplitude * np.sin(t)
    
    # Apply fade in/out envelopes to prevent clicks
    fade_samples = int(rate * fade_ms / 1000)
    if samples > fade_samples * 2:  # Only if we have enough samples
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        wave[:fade_samples] *= fade_in
        wave[-fade_samples:] *= fade_out
    
    # Apply soft clipping to prevent harsh distortion if amplitude is too high
    wave = soft_clip(wave)
    return wave.astype(np.float32)

# Find zero-crossings in a waveform
def find_zero_crossings(wave):
    """Find indices where the waveform crosses from negative to positive (rising edge)"""
    zero_crossings = []
    for i in range(len(wave) - 1):
        if wave[i] <= 0 and wave[i+1] > 0:
            zero_crossings.append(i + 1)
    return zero_crossings

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
            
            # Create new sound with zero-crossing optimization and envelope
            new_wave = generate_sine_wave(freq, AMPLITUDE * MASTER_VOLUME, RATE, fade_ms=15)
            
            # Find zero crossings in the new wave
            zero_crossings = find_zero_crossings(new_wave)
            
            # If we found zero crossings, start playback from one near the middle
            # This creates a smoother phase transition
            if zero_crossings:
                middle_idx = len(zero_crossings) // 2
                zero_point = zero_crossings[middle_idx]
                # Rotate the wave to start at the zero crossing
                new_wave = np.concatenate((new_wave[zero_point:], new_wave[:zero_point]))
            
            # Create new sound with the phase-optimized wave
            new_sound = pygame.sndarray.make_sound((new_wave * 32767).astype(np.int16))
            
            # Extended crossfade to eliminate clicks
            crossfade_steps = 30
            crossfade_duration = 0.03  # 30ms total (1ms per step)
            
            # Start the new sound at zero volume
            new_sound.set_volume(0)
            new_sound.play(-1)
            
            # Perform smooth crossfade
            for step in range(crossfade_steps + 1):
                ratio = step / crossfade_steps
                # Use curves instead of linear fades for smoother transition
                # Sine curve for fade in/out (smoother than linear)
                old_vol = volumes[i] * MASTER_VOLUME * np.cos(ratio * np.pi/2)
                new_vol = volumes[i] * MASTER_VOLUME * np.sin(ratio * np.pi/2)
                
                sounds[i].set_volume(old_vol)
                new_sound.set_volume(new_vol)
                gevent.sleep(crossfade_duration / crossfade_steps)
            
            # Stop old sound and update to new sound
            sounds[i].stop()
            sounds[i] = new_sound
            sounds[i].set_volume(volumes[i] * MASTER_VOLUME)

# Start playing all sounds
play_all_sounds()