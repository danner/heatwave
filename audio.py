import numpy as np
import pygame
import gevent

# Initialize pygame mixer
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=4096)

# Audio setup for sine wave generation
RATE = 44100  # Sampling rate
AMPLITUDE = 0.5  # Default volume
MASTER_VOLUME = 0.8  # Master volume to prevent clipping
INTERPOLATION_STEPS = 30  # Number of steps for frequency interpolation
INTERPOLATION_DURATION = 0.3  # Duration of interpolation in seconds

# Function to perform soft clipping using tanh
def soft_clip(x, threshold=0.8):
    """
    Apply soft clipping to prevent harsh distortion.
    Values approaching ±threshold gradually compress, 
    and values beyond threshold are more aggressively compressed.
    """
    return np.tanh(x / threshold) * threshold

# Generate sine wave function ensuring zero-crossings
def generate_sine_wave(freq, amplitude, rate, phase_offset=0):
    # Ensure we have a complete number of cycles for smooth looping
    cycles = max(1, int(rate / freq / 10))  # Use multiple cycles for better quality
    # Number of samples needed for complete cycles
    samples = int((cycles / freq) * rate)
    t = np.linspace(0, 2 * np.pi * cycles, samples, endpoint=False)
    # Apply phase offset to maintain continuity
    wave = amplitude * np.sin(t + phase_offset)
    # Apply soft clipping to prevent harsh distortion if amplitude is too high
    wave = soft_clip(wave)
    return wave.astype(np.float32), samples / rate  # Return wave and duration

# Generate interpolated sine wave between two frequencies
def generate_interpolated_wave(current_freq, target_freq, amplitude, rate, phase_offset=0):
    """
    Generate a waveform that smoothly transitions from current_freq to target_freq
    while maintaining phase continuity.
    """
    # Calculate number of samples for interpolation
    total_samples = int(INTERPOLATION_DURATION * rate)
    
    # Create time array for the entire duration
    t = np.arange(total_samples) / rate
    
    # Calculate instantaneous frequency at each sample (linear interpolation)
    freq_array = np.linspace(current_freq, target_freq, total_samples)
    
    # Calculate phase by integrating frequency over time
    # This ensures phase continuity during frequency transition
    phase = phase_offset + 2 * np.pi * np.cumsum(freq_array) / rate
    
    # Generate the waveform using the continuous phase
    wave = amplitude * np.sin(phase)
    
    # Apply soft clipping
    wave = soft_clip(wave)
    
    return wave.astype(np.float32), INTERPOLATION_DURATION

# Function to create and return a pygame Sound object
def create_sound(freq, amplitude, rate, phase_offset=0):
    # Scale amplitude by master volume to prevent clipping when multiple channels are played
    scaled_amplitude = amplitude * MASTER_VOLUME
    wave, _ = generate_sine_wave(freq, scaled_amplitude, rate, phase_offset)
    sound = pygame.sndarray.make_sound((wave * 32767).astype(np.int16))
    return sound

# Initialize sounds for each channel
sounds = [create_sound(110, AMPLITUDE, RATE) for _ in range(8)]
frequencies = [110 for _ in range(8)]  # Track the current frequency of each channel
target_frequencies = [110 for _ in range(8)]  # Target frequencies during interpolation
is_interpolating = [False for _ in range(8)]  # Track which channels are currently interpolating
volumes = [AMPLITUDE for _ in range(8)]  # Track the current volume of each channel
phase_positions = [0 for _ in range(8)]  # Track the current phase position to maintain continuity

# Global variables to track interpolation state and queue
interpolation_active = [False for _ in range(8)]
frequency_change_queue = [[] for _ in range(8)]

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
        
        # If target frequency is different from requested frequency
        if freq != target_frequencies[i]:
            print(f"Queuing frequency change for channel {i} from {frequencies[i]} to {freq}")
            
            # Add frequency change to queue or update last queued change
            if not frequency_change_queue[i]:
                frequency_change_queue[i].append(freq)
            else:
                # Replace the last queued frequency with the newest one
                frequency_change_queue[i][-1] = freq
            
            # Update target frequency
            target_frequencies[i] = freq
        
        # If we're not currently interpolating and there's a change in the queue
        if not interpolation_active[i] and frequency_change_queue[i]:
            next_freq = frequency_change_queue[i].pop(0)
            perform_frequency_transition(i, next_freq)

# Function to handle the actual frequency transition
def perform_frequency_transition(channel_index, target_freq):
    # Mark this channel as actively interpolating
    interpolation_active[channel_index] = True
    
    # Calculate current phase position to maintain continuity
    phase_offset = phase_positions[channel_index]
    
    # Generate the interpolated wave for transition
    wave, duration = generate_interpolated_wave(
        frequencies[channel_index], 
        target_freq, 
        AMPLITUDE * MASTER_VOLUME, 
        RATE, 
        phase_offset
    )
    
    # Stop the current sound
    sounds[channel_index].stop()
    
    # Create and play the interpolation sound (ONCE, not looped)
    transition_sound = pygame.sndarray.make_sound((wave * 32767).astype(np.int16))
    transition_sound.set_volume(volumes[channel_index] * MASTER_VOLUME)
    
    # Play transition sound only once (not looped)
    transition_sound.play(0)
    
    # Schedule the steady-state wave to play after interpolation finishes
    # We'll use a greenlet to handle this timing
    def transition_completed():
        # Wait for the interpolation to complete
        gevent.sleep(duration)
        
        # Update the current frequency to the target one
        frequencies[channel_index] = target_freq
        
        # Update phase position for smooth transition to steady state
        phase_positions[channel_index] = (phase_offset + 2 * np.pi * target_freq * duration) % (2 * np.pi)
        
        # Create steady-state wave at the target frequency
        steady_wave, _ = generate_sine_wave(
            target_freq, 
            AMPLITUDE * MASTER_VOLUME, 
            RATE, 
            phase_positions[channel_index]
        )
        
        # Stop the transition sound if it's still playing
        transition_sound.stop()
        
        # Create and play the steady-state sound (looped)
        sounds[channel_index] = pygame.sndarray.make_sound((steady_wave * 32767).astype(np.int16))
        sounds[channel_index].set_volume(volumes[channel_index] * MASTER_VOLUME)
        sounds[channel_index].play(-1)  # Play steady-state wave in a loop
        
        # Mark interpolation as complete
        interpolation_active[channel_index] = False
        
        # Check if there are more frequency changes in the queue
        if frequency_change_queue[channel_index]:
            next_freq = frequency_change_queue[channel_index].pop(0)
            perform_frequency_transition(channel_index, next_freq)
    
    # Launch the transition completion handler
    gevent.spawn(transition_completed)

# Start playing all sounds initially
play_all_sounds()

# Make update_pitches available at module level
__all__ = ['update_volumes', 'update_pitches', 'play_all_sounds']