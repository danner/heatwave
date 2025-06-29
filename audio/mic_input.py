import sounddevice as sd
import threading
import numpy as np
import scipy.signal as signal
from .audio_core import RATE, AMPLITUDE, MASTER_VOLUME, find_mac_builtin_mic, soft_clip, BUFFER_SIZE

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
        
        # Compressor parameters
        self.enable_compression = True
        self.threshold = -30.0  # dB - lower means more signal gets compressed
        self.ratio = 4.0        # compression ratio (higher means more compression)
        self.attack = 0.005     # seconds - how fast compression kicks in
        self.release = 0.100    # seconds - how fast compression releases
        self.makeup_gain = 12.0 # dB - boost after compression
        self.knee = 6.0         # dB - smoothing around threshold
        
        # Compressor state variables
        self.env = 0.0          # envelope follower
        self.gain_reduction = 0.0
        self.attack_coef = np.exp(-1.0 / (self.rate * self.attack))
        self.release_coef = np.exp(-1.0 / (self.rate * self.release))
        self.prev_gain = 1.0
        self.rms_buffer_size = 512  # Samples to use for RMS calculation
        self.rms_buffer = np.zeros(self.rms_buffer_size)
        self.rms_pos = 0
        self.level_meter = -60.0  # Current level meter in dB
        
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
                blocksize=BUFFER_SIZE,
                dtype='float32',
                channels=1,
                callback=self.callback,
                device=(self.input_device, None),  # (input, output)
                latency='low'  # Changed to low latency
            )
            self.active = True
            self.stream.start()
            print(f"Microphone input started using device index {self.input_device} with low latency")
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
    
    def set_compression(self, enable=True, threshold=None, ratio=None, makeup_gain=None):
        """Configure the compressor settings"""
        with self.lock:
            self.enable_compression = enable
            
            if threshold is not None:
                self.threshold = float(threshold)
            
            if ratio is not None:
                self.ratio = max(1.0, float(ratio))
                
            if makeup_gain is not None:
                self.makeup_gain = float(makeup_gain)
                
            print(f"Compressor: {'enabled' if enable else 'disabled'}, "
                  f"threshold: {self.threshold}dB, ratio: {self.ratio}:1, "
                  f"makeup: {self.makeup_gain}dB")
    
    def _apply_compression(self, audio_buffer):
        """Apply dynamic range compression to the audio buffer"""
        # Skip if compression is disabled
        if not self.enable_compression:
            return audio_buffer
            
        output = np.zeros_like(audio_buffer)
        
        # Convert threshold and makeup gain from dB to linear
        threshold_lin = 10.0 ** (self.threshold / 20.0)
        makeup_gain_lin = 10.0 ** (self.makeup_gain / 20.0)
        
        # Process each sample
        for i in range(len(audio_buffer)):
            # Get absolute value of sample
            input_sample = audio_buffer[i]
            abs_sample = abs(input_sample)
            
            # Update level detection (envelope follower)
            if abs_sample > self.env:
                # Attack phase - fast rise
                self.env = self.attack_coef * self.env + (1.0 - self.attack_coef) * abs_sample
            else:
                # Release phase - slow decay
                self.env = self.release_coef * self.env + (1.0 - self.release_coef) * abs_sample
            
            # Determine gain reduction amount with soft knee
            env_db = 20.0 * np.log10(self.env + 1e-10)
            threshold_db = self.threshold
            
            # Apply soft knee
            if 2.0 * (env_db - threshold_db) < -self.knee:
                # Below knee
                gain_reduction_db = 0.0
            elif 2.0 * (env_db - threshold_db) > self.knee:
                # Above knee
                gain_reduction_db = (env_db - threshold_db) / self.ratio
            else:
                # In knee region - smooth transition
                gain_reduction_db = ((env_db - threshold_db + self.knee/2.0)**2) / (2.0 * self.knee) / self.ratio
                
            # Convert gain reduction to linear
            gain_reduction_lin = 10.0 ** (-gain_reduction_db / 20.0)
            
            # Apply gain reduction with smoothing
            gain = gain_reduction_lin * makeup_gain_lin
            
            # Smooth gain changes to avoid clicks
            smooth_gain = 0.9 * self.prev_gain + 0.1 * gain
            self.prev_gain = smooth_gain
            
            # Apply gain to sample
            output[i] = input_sample * smooth_gain
            
            # Update RMS buffer for metering
            self.rms_buffer[self.rms_pos] = input_sample * smooth_gain
            self.rms_pos = (self.rms_pos + 1) % self.rms_buffer_size
            
        # Update level meter (every 100ms)
        if np.random.random() < len(audio_buffer) / (self.rate * 0.1):
            rms = np.sqrt(np.mean(self.rms_buffer**2))
            self.level_meter = 20.0 * np.log10(rms + 1e-10)
            
        return output
            
    def callback(self, indata, outdata, frames, time_info, status):
        """Process audio data from microphone to output"""
        if status:
            print(f"Mic input callback status: {status}")
            
        with self.lock:
            # Apply the low-pass filter to remove frequencies above 1000Hz
            filtered_data, self.zi = signal.lfilter(self.b, self.a, indata[:, 0], zi=self.zi)
            
            # Apply compression
            compressed_data = self._apply_compression(filtered_data)
            
            # Apply volume to microphone input
            processed = compressed_data * self.volume
            
            # Apply soft clipping to prevent distortion
            processed = soft_clip(processed)
            
            # Copy to output
            outdata[:, 0] = processed.astype(np.float32)