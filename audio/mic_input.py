import sounddevice as sd
import threading
import numpy as np
import subprocess
import os
import time
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
        
        # Additional gain boost specifically for USB mics - increased for Raspberry Pi
        self.usb_boost = 18.0   # Additional boost for USB mics
        
        # Processing history for dropout prevention
        self.prev_output = np.zeros(BUFFER_SIZE // 2)  # Store half a buffer of previous output
        self.process_count = 0
        
        # New underflow tracking
        self.underflow_count = 0
        self.last_underflow_time = 0
    
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
            # Use larger buffer and increase latency for more stability
            self.stream = sd.Stream(
                samplerate=self.rate,
                blocksize=BUFFER_SIZE,
                dtype='float32',
                channels=1,
                callback=self.callback,
                device=(self.input_device, None),  # (input, output)
                latency='high'  # Increased latency to prevent underflows
            )
            self.active = True
            self.stream.start()
            self.underflow_count = 0  # Reset counter on start
            print(f"Microphone input started using device index {self.input_device} with high latency")
            print(f"Buffer size: {BUFFER_SIZE} samples ({BUFFER_SIZE/self.rate*1000:.1f}ms)")
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
        # Check for underflow issues
        if status and status.input_underflow:
            self.underflow_count += 1
            current_time = time.time()
            # Only log every few seconds to avoid spamming
            if current_time - self.last_underflow_time > 5.0:
                print(f"⚠️ Mic input underflow detected ({self.underflow_count} times)")
                self.last_underflow_time = current_time
        
        try:
            with self.lock:
                # Fill output with zeros in case of empty input
                if indata is None or len(indata) == 0:
                    outdata.fill(0)
                    return
                
                # Get input data from microphone
                input_data = indata[:, 0]
                
                # Apply simple gain - add USB boost if needed
                gain = self.volume
                if hasattr(self, 'is_usb_mic') and self.is_usb_mic:
                    gain *= (10.0 ** (self.usb_boost / 20.0))  # Convert dB to linear gain
                
                # Apply gain to the raw input data
                processed = input_data * gain
                
                # Apply soft clipping to prevent distortion
                processed = soft_clip(processed)
                
                # Copy directly to output
                outdata[:, 0] = processed.astype(np.float32)
        except Exception as e:
            # Handle errors gracefully - fill with zeros and log
            print(f"Error in mic processing: {e}")
            outdata.fill(0)