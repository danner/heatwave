import sounddevice as sd
import threading
import numpy as np
import scipy.signal as signal
import subprocess
import os
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
            # Check if this is a USB microphone
            self.is_usb_mic = ('USB' in device_info['name'] or 
                              'usb' in device_info['name'] or 
                              'PnP' in device_info['name'])
            if self.is_usb_mic:
                print("USB microphone detected - applying additional gain boost")
                # Check Raspberry Pi specific settings if available
                self.check_raspi_alsa_settings()
            
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
        
        # Add high-pass filter to remove hum (cutoff at 100Hz)
        hp_cutoff = 100 / nyquist
        self.hp_b, self.hp_a = signal.butter(2, hp_cutoff, 'high')
        self.hp_zi = signal.lfilter_zi(self.hp_b, self.hp_a)
        
        # Pre-amplification before compression (higher for USB mics)
        self.pre_amp_gain = 12.0  # dB of gain before compression
        
        # Compressor parameters - increase default values for USB mics
        self.enable_compression = True
        self.threshold = -40.0  # Lower threshold for more aggressive compression
        self.ratio = 6.0        # Higher ratio for more compression
        self.attack = 0.005     # Fast attack for quick response
        self.release = 0.100    # seconds - how fast compression releases
        self.makeup_gain = 18.0 # Higher makeup gain (increased from 12dB)
        self.knee = 6.0         # dB - smoothing around threshold
        
        # Additional gain boost specifically for USB mics - increased for Raspberry Pi
        self.usb_boost = 12.0   # Additional 12dB boost for USB mics (doubled from 6dB)
        
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
        
        # Processing history for dropout prevention
        self.prev_output = np.zeros(BUFFER_SIZE // 2)  # Store half a buffer of previous output
        self.process_count = 0
        
    def check_raspi_alsa_settings(self):
        """Check ALSA settings on Raspberry Pi and print helpful information"""
        try:
            # Check if we're on a Raspberry Pi
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    if 'raspbian' in f.read().lower():
                        print("\n=== RASPBERRY PI USB MICROPHONE INFORMATION ===")
                        print("If your USB mic is too quiet, try these commands:")
                        print("  1. Check input devices: 'arecord -l'")
                        print("  2. Check volume settings: 'alsamixer'")
                        print("  3. Set max USB input gain: 'amixer -c 1 sset Mic 100%'")
                        print("     (You may need to replace '-c 1' with your device number)")
                        print("=================================================\n")
                        
                        # Try to get current volume settings
                        try:
                            result = subprocess.run(['amixer', 'sget', 'Mic'], 
                                                  stdout=subprocess.PIPE, 
                                                  stderr=subprocess.PIPE, 
                                                  text=True)
                            if result.returncode == 0:
                                print("Current Mic Settings:", result.stdout.strip())
                        except:
                            pass
        except:
            pass  # Silently ignore errors in this diagnostic function
        
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
    
    def set_compression(self, enable=True, threshold=None, ratio=None, makeup_gain=None, usb_boost=None, pre_amp=None):
        """Configure the compressor settings"""
        with self.lock:
            self.enable_compression = enable
            
            if threshold is not None:
                self.threshold = float(threshold)
            
            if ratio is not None:
                self.ratio = max(1.0, float(ratio))
                
            if makeup_gain is not None:
                self.makeup_gain = float(makeup_gain)
                
            if usb_boost is not None and self.is_usb_mic:
                self.usb_boost = float(usb_boost)
                
            if pre_amp is not None:
                self.pre_amp_gain = float(pre_amp)
                
            print(f"Compressor: {'enabled' if enable else 'disabled'}, "
                  f"pre-amp: {self.pre_amp_gain}dB, "
                  f"threshold: {self.threshold}dB, ratio: {self.ratio}:1, "
                  f"makeup: {self.makeup_gain}dB, "
                  f"USB boost: {self.usb_boost if self.is_usb_mic else 0}dB")
    
    def _apply_compression(self, audio_buffer):
        """Apply dynamic range compression to the audio buffer"""
        # Skip if compression is disabled
        if not self.enable_compression:
            return audio_buffer
            
        # Apply pre-amplification before compression - using vectorized operation
        pre_amp_linear = 10.0 ** (self.pre_amp_gain / 20.0)
        pre_amped_buffer = audio_buffer * pre_amp_linear
            
        # Calculate additional gain for USB microphones
        total_makeup_gain = self.makeup_gain
        if hasattr(self, 'is_usb_mic') and self.is_usb_mic:
            total_makeup_gain += self.usb_boost
        
        # Convert threshold and makeup gain from dB to linear
        threshold_lin = 10.0 ** (self.threshold / 20.0)
        makeup_gain_lin = 10.0 ** (total_makeup_gain / 20.0)
        
        # Optimize compression by using vectorized operations where possible
        # Process buffer in chunks for better performance
        output = np.zeros_like(audio_buffer)
        chunk_size = 32  # Process 32 samples at a time
        
        for chunk_start in range(0, len(pre_amped_buffer), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(pre_amped_buffer))
            chunk = pre_amped_buffer[chunk_start:chunk_end]
            
            # Get max absolute value for this chunk
            chunk_abs_max = np.max(np.abs(chunk))
            
            # Update level detection (envelope follower)
            if chunk_abs_max > self.env:
                # Attack phase - fast rise
                self.env = self.attack_coef * self.env + (1.0 - self.attack_coef) * chunk_abs_max
            else:
                # Release phase - slow decay
                self.env = self.release_coef * self.env + (1.0 - self.release_coef) * chunk_abs_max
            
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
            
            # Apply gain to original samples (not pre-amplified)
            output[chunk_start:chunk_end] = audio_buffer[chunk_start:chunk_end] * smooth_gain
            
            # Update RMS buffer for metering (just use the first sample of each chunk)
            self.rms_buffer[self.rms_pos] = output[chunk_start]
            self.rms_pos = (self.rms_pos + 1) % self.rms_buffer_size
        
        # Update level meter occasionally
        if np.random.random() < len(audio_buffer) / (self.rate * 0.5):  # Less frequent updates
            rms = np.sqrt(np.mean(self.rms_buffer**2) + 1e-10)
            self.level_meter = 20.0 * np.log10(rms)
            
        return output
            
    def callback(self, indata, outdata, frames, time_info, status):
        """Process audio data from microphone to output"""
        if status:
            print(f"Mic input callback status: {status}")
        
        try:
            with self.lock:
                # Get input data from the microphone
                input_data = indata[:, 0]
                
                # Apply high-pass filter to remove low-frequency hum
                hp_filtered, self.hp_zi = signal.lfilter(self.hp_b, self.hp_a, input_data, zi=self.hp_zi)
                
                # Apply the low-pass filter to remove high frequencies
                filtered_data, self.zi = signal.lfilter(self.b, self.a, hp_filtered, zi=self.zi)
                
                # Apply compression
                compressed_data = self._apply_compression(filtered_data)
                
                # Apply volume to microphone input
                processed = compressed_data * self.volume
                
                # Apply soft clipping to prevent distortion
                processed = soft_clip(processed)
                
                # Smooth transitions between buffers to prevent clicks
                if self.process_count > 0:
                    # Cross-fade between previous buffer tail and current buffer head
                    crossfade_len = min(len(self.prev_output), len(processed) // 4)
                    if crossfade_len > 0:
                        fade_in = np.linspace(0, 1, crossfade_len)
                        fade_out = np.linspace(1, 0, crossfade_len)
                        processed[:crossfade_len] = (
                            processed[:crossfade_len] * fade_in + 
                            self.prev_output[-crossfade_len:] * fade_out
                        )
                
                # Store the end of the current buffer for next time
                self.prev_output = processed[-min(len(processed) // 2, len(self.prev_output)):]
                self.process_count += 1
                
                # Copy to output
                outdata[:, 0] = processed.astype(np.float32)
                
        except Exception as e:
            # Handle errors gracefully - fill with zeros and log
            print(f"Error in mic processing: {e}")
            outdata.fill(0)