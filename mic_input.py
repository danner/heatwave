import sounddevice as sd
import threading
import numpy as np
import scipy.signal as signal
from audio_core import RATE, AMPLITUDE, MASTER_VOLUME, find_mac_builtin_mic, soft_clip

class MicInput:
    """Class for handling microphone input"""
    def __init__(self, rate=RATE, input_device=None):
        self.rate = rate
        # Use built-in mic if no specific device is provided
        self.input_device = input_device if input_device is not None else find_mac_builtin_mic()
        if self.input_device is None:
            print("Warning: No input device found. Microphone input will not work.")
        else:
            device_info = sd.query_devices(self.input_device)
            print(f"Using microphone: {device_info['name']}")
            
        self.lock = threading.Lock()
        self.volume = AMPLITUDE * MASTER_VOLUME
        self.active = False
        self.stream = None
        
        # Design a low-pass filter to remove high frequencies 
        nyquist = self.rate / 2
        cutoff = 1000 / nyquist
        self.b, self.a = signal.butter(4, cutoff, 'low')
        # Initialize filter state
        self.zi = signal.lfilter_zi(self.b, self.a)
        
    def start(self):
        """Start capturing from the microphone and routing to output"""
        if self.stream is not None and self.stream.active:
            return
        
        if self.input_device is None:
            print("Error: Cannot start microphone input - no input device available")
            return
            
        try:
            self.stream = sd.Stream(
                samplerate=self.rate,
                blocksize=256,
                dtype='float32',
                channels=1,
                callback=self.callback,
                device=(self.input_device, None),  # (input, output)
                latency='low'
            )
            self.active = True
            self.stream.start()
            print("Microphone input started")
        except Exception as e:
            print(f"Error starting microphone stream: {e}")
            self.active = False
            self.stream = None
            
    def stop(self):
        """Stop capturing from the microphone"""
        if self.stream is not None and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.active = False
            print("Microphone input stopped")
            
    def set_volume(self, volume):
        """Set the volume of the microphone input"""
        with self.lock:
            self.volume = volume * MASTER_VOLUME
            
    def callback(self, indata, outdata, frames, time_info, status):
        """Process audio data from microphone to output"""
        if status:
            print(f"Mic input callback status: {status}")
            
        with self.lock:
            # Apply the low-pass filter to remove frequencies above 3000Hz
            filtered_data, self.zi = signal.lfilter(self.b, self.a, indata[:, 0], zi=self.zi)
            
            # Apply volume to microphone input
            processed = filtered_data * self.volume
            
            # Apply soft clipping to prevent distortion
            processed = soft_clip(processed)
            
            # Copy to output
            outdata[:, 0] = processed.astype(np.float32)
