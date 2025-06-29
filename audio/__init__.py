"""
Audio package for HeatWave project.
"""
import threading

# Import all core components
from .audio_core import (
    RATE, AMPLITUDE, MASTER_VOLUME, INTERPOLATION_DURATION,
    find_mac_builtin_mic, soft_clip, list_audio_devices, BUFFER_SIZE
)

# Import classes
from .synth import ToneSynth
from .mic_input import MicInput
from .pressure_algorithm import PressureAlgorithmInput
from .audio_manager import (
    current_source, frequencies, volumes,
    set_audio_source, get_audio_source_settings,
    set_mic_volume, set_pressure_model_volume,
    update_volumes, update_pitches, set_mic_compression, set_mic_noise_gate
)

# Initialize instances
synth = ToneSynth(num_channels=8)
mic_input = MicInput()
pressure_model = PressureAlgorithmInput()

# Print available audio devices on startup
list_audio_devices()

# Initialize audio_manager with our instances - FIXED
import sys
from . import audio_manager
audio_manager.synth = synth
audio_manager.mic_input = mic_input
audio_manager.pressure_model = pressure_model
# Don't set a separate channels reference - use state.channels directly

# Export all public components
__all__ = [
    # Classes
    'ToneSynth', 'MicInput', 'PressureAlgorithmInput',
    # Instances
    'synth', 'mic_input', 'pressure_model',
    # Functions
    'update_volumes', 'update_pitches', 'set_audio_source',
    'get_audio_source_settings', 'set_mic_volume', 'set_pressure_model_volume',
    'find_mac_builtin_mic', 'soft_clip', 'list_audio_devices', 'set_mic_compression',
    'set_mic_noise_gate',
    # Constants
    'RATE', 'AMPLITUDE', 'MASTER_VOLUME', 'INTERPOLATION_DURATION', 'BUFFER_SIZE',
    # State
    'current_source', 'frequencies', 'volumes'
]
