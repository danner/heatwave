"""
Main audio module that re-exports all components from the modular audio system.
This file maintains backward compatibility with the rest of the codebase.
"""
import gevent
import threading

# Import all modules
from audio_core import (
    RATE, AMPLITUDE, MASTER_VOLUME, INTERPOLATION_DURATION,
    find_mac_builtin_mic, soft_clip, list_audio_devices
)
from synth import ToneSynth
from mic_input import MicInput
from pressure_algorithm import PressureAlgorithmInput
from audio_manager import (
    current_source, frequencies, volumes,
    set_audio_source, get_audio_source_settings,
    set_mic_volume, set_pressure_model_volume,
    update_volumes, update_pitches
)

# Initialize instances
synth = ToneSynth(num_channels=8)
mic_input = MicInput()
pressure_model = PressureAlgorithmInput()

# Print available audio devices on startup
list_audio_devices()

# Compatibility function for backward compat
def play_all_sounds():
    """Legacy function kept for backwards compatibility"""
    # No action needed, the stream is already started
    pass

# Re-initialize audio_manager with our instances to avoid circular imports
import audio_manager
audio_manager.synth = synth
audio_manager.mic_input = mic_input
audio_manager.pressure_model = pressure_model
audio_manager.channels = {}  # Will be set from main.py