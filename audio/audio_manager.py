from .audio_core import AMPLITUDE, MASTER_VOLUME
from state import channels as state_channels, notify_channel_updated  # Add notification import

# Current audio source (can be 'synth', 'mic', or 'pressure')
current_source = 'synth'

# Track audio state
frequencies = [110 for _ in range(8)]  # Track the current frequency of each channel
volumes = [AMPLITUDE for _ in range(8)]  # Track the current volume of each channel

def set_audio_source(source, synth=None, mic_input=None, pressure_model=None):
    """Switch between audio sources"""
    global current_source
    
    if source == current_source:
        return  # No change needed
    
    if synth is None or mic_input is None or pressure_model is None:
        # If components aren't provided, import them here to avoid circular imports
        from . import synth, mic_input, pressure_model
        
    # Store previous source for cleanup logic
    previous_source = current_source
    
    # Stop all active sources first
    if current_source == 'synth' and synth.stream and synth.stream.active:
        synth.stream.stop()
    elif current_source == 'mic' and mic_input.active:
        mic_input.stop()
    elif current_source == 'pressure' and pressure_model.active:
        pressure_model.stop()
    
    # Start the requested source
    if source == 'synth':
        # If switching from pressure model, make sure we have the final frequencies
        if previous_source == 'pressure':
            # Make sure the synth has the latest channel settings
            update_pitches(channels, synth)
            update_volumes(channels, synth)
        
        synth.stream.start()
        current_source = 'synth'
        print("Switched to synthesizer")
    elif source == 'mic':
        mic_input.start()
        current_source = 'mic'
        print("Switched to microphone input")
    elif source == 'pressure':
        # Run the optimization algorithm to find optimal frequencies matching a target pressure
        print("Running pressure optimization algorithm with animated target...")
        # Use gaussian profile with 8 frequencies, with animation enabled
        pressure_model.optimize_and_apply(profile="gaussian", num_freqs=8, animated=True)
        
        # Start the pressure model with the optimized frequencies
        pressure_model.start()
        current_source = 'pressure'
        print("Switched to pressure model with animated optimization")
    else:
        print(f"Unknown audio source: {source}")
        # Default to synth if unknown source
        synth.stream.start()
        current_source = 'synth'
    
    return current_source

def get_audio_source_settings(mic_input=None, pressure_model=None):
    """Returns the current audio source and volume settings"""
    if mic_input is None or pressure_model is None:
        # If components aren't provided, import them here to avoid circular imports
        from . import mic_input, pressure_model
        
    return {
        'source': current_source,
        'mic_volume': mic_input.volume / MASTER_VOLUME,
        'pressure_volume': pressure_model.volume / MASTER_VOLUME
    }

def set_mic_volume(volume, mic_input=None):
    """Set the volume for microphone input"""
    if mic_input is None:
        # If mic_input isn't provided, import it here to avoid circular imports
        from . import mic_input
        
    mic_input.set_volume(volume)
    print(f"Microphone volume set to {volume}")

def set_mic_compression(enable=True, threshold=-40.0, ratio=6.0, makeup_gain=18.0, usb_boost=12.0, pre_amp=12.0, mic_input=None):
    """Configure microphone compressor settings"""
    if mic_input is None:
        # If mic_input isn't provided, import it here to avoid circular imports
        from . import mic_input
    
    mic_input.set_compression(enable, threshold, ratio, makeup_gain, usb_boost, pre_amp)

def set_pressure_model_volume(volume, pressure_model=None):
    """Set the volume for pressure model"""
    if pressure_model is None:
        # If pressure_model isn't provided, import it here to avoid circular imports
        from . import pressure_model
        
    pressure_model.set_volume(volume)
    print(f"Pressure model volume set to {volume}")

def update_volumes(updated_channels, synth=None):
    """Update the volume of each synth channel based on the mute state"""
    # Don't cache our own copy of channels, work directly with passed channels
    if synth is None:
        # If synth isn't provided, import it here to avoid circular imports
        from . import synth
    
    # Track if any changes were made
    changes_made = False
    
    for i, channel in updated_channels.items():
        volume = channel['volume'] if not channel['mute'] else 0
        muted = channel['mute']
        if i < len(volumes):  # Make sure we're not exceeding array bounds
            # Only update if the volume has changed
            if volume != volumes[i] or muted != (volumes[i] == 0):
                # Limit logging to reduce console spam and improve performance
                volumes[i] = volume
                # Update the synth volume
                synth.set_volume(i, volume, muted)
                
                # Make sure to update state module and notify listeners when coming from MIDI
                if updated_channels is not state_channels:
                    state_channels[i]['volume'] = channel['volume']
                    state_channels[i]['mute'] = channel['mute']
                    notify_channel_updated(i)
                
                changes_made = True
            
    # If pressure model is active and changes were made, update it
    if changes_made and current_source == 'pressure':
        from . import pressure_model
        pressure_model.update_from_synth_channels(updated_channels)

def update_pitches(updated_channels, synth=None):
    """Update the pitch of each synth channel based on the frequency"""
    # Don't cache our own copy of channels, work directly with passed channels
    if synth is None:
        # If synth isn't provided, import it here to avoid circular imports
        from . import synth
    
    # Track if any changes were made  
    changes_made = False
    
    for i, channel in updated_channels.items():
        freq = max(1, channel['frequency'])
        if i < len(frequencies):  # Make sure we're not exceeding array bounds
            if freq != frequencies[i]:  # Only update if the frequency has changed
                frequencies[i] = freq
                synth.set_frequency(i, freq)
                
                # Make sure to update state module and notify listeners when coming from MIDI
                if updated_channels is not state_channels:
                    state_channels[i]['frequency'] = freq
                    notify_channel_updated(i)
                
                changes_made = True
            
    # If pressure model is active and changes were made, update it
    if changes_made and current_source == 'pressure':
        from . import pressure_model
        pressure_model.update_from_synth_channels(updated_channels)