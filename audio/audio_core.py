import numpy as np
import sounddevice as sd

# Audio setup constants
RATE = 44100  # Sampling rate
AMPLITUDE = 0.1  # Default volume
MASTER_VOLUME = 0.8  # Master volume to prevent clipping
INTERPOLATION_DURATION = 0.05  # Faster interpolation
BUFFER_SIZE = 2048  # Increased from 1024 to reduce underflows

def find_mac_builtin_mic():
    """Find the built-in microphone device"""
    devices = sd.query_devices()
    
    # First try to find USB PnP Sound Device for Raspberry Pi
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0 and 'USB PnP Sound Device' in device['name']:
            print(f"Found USB PnP Sound Device for microphone: {device['name']}")
            return i
    
    # Fall back to Mac built-in if not on Raspberry Pi
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0 and 'Built-in' in device['name'] and 'Microphone' in device['name']:
            print(f"Found Mac built-in microphone: {device['name']}")
            return i
            
    # If no device with "Built-in" and "Microphone" found, try to find any input device
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"Using default input device: {device['name']}")
            return i
    return None

def soft_clip(x, threshold=0.8):
    """
    Apply soft clipping to prevent harsh distortion.
    Values approaching ±threshold gradually compress, 
    and values beyond threshold are more aggressively compressed.
    """
    return np.tanh(x / threshold) * threshold

def list_audio_devices():
    """Print all available audio input and output devices"""
    devices = sd.query_devices()
    print("\nAVAILABLE AUDIO DEVICES:")
    print("-" * 50)
    for i, device in enumerate(devices):
        io_type = []
        if device['max_input_channels'] > 0:
            io_type.append("INPUT")
        if device['max_output_channels'] > 0:
            io_type.append("OUTPUT")
        print(f"Device {i}: {device['name']} ({', '.join(io_type)})")
    print("-" * 50)