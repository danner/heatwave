import sounddevice as sd
import threading
import numpy as np
from audio_core import RATE, AMPLITUDE, MASTER_VOLUME, soft_clip

class SamplerInput:
    """Class for sample playback"""
    def __init__(self, rate=RATE):
        self.rate = rate
        self.lock = threading.Lock()
        self.volume = AMPLITUDE * MASTER_VOLUME
        self.active = False
        self.stream = None
        self.sample_data = None
        self.sample_position = 0
        self.sample_loaded = False
        self.looping = True
        
    def load_sample(self, file_path=None):
        """Load audio sample from file or use a default sine wave if no file specified"""
        try:
            if file_path and file_path.endswith(('.wav', '.mp3')):
                # Simple sample loading using NumPy (would use librosa or soundfile in a real app)
                # This is just a placeholder - would need an audio file library to implement properly
                print(f"Would load sample from {file_path}")
                # For demo purposes, create a simple tone instead
                duration = 1.0  # 1 second sample
                t = np.linspace(0, duration, int(self.rate * duration), False)
                self.sample_data = 0.5 * np.sin(2 * np.pi * 220 * t)
                self.sample_loaded = True
                print("Sample loaded (demo sine wave)")
            else:
                # Create a default sample (simple melody)
                print("Creating default sample pattern")
                duration = 2.0  # 2 seconds
                t = np.linspace(0, duration, int(self.rate * duration), False)
                notes = [220, 330, 440, 330]  # A3, E4, A4, E4
                note_duration = duration / len(notes)
                
                self.sample_data = np.zeros(int(self.rate * duration))
                for i, note in enumerate(notes):
                    start = int(i * note_duration * self.rate)
                    end = int((i + 1) * note_duration * self.rate)
                    t_segment = np.linspace(0, note_duration, end - start, False)
                    self.sample_data[start:end] = 0.5 * np.sin(2 * np.pi * note * t_segment)
                    
                # Apply short fade in/out to prevent clicks
                fade_samples = int(0.01 * self.rate)  # 10ms fade
                fade_in = np.linspace(0, 1, fade_samples)
                fade_out = np.linspace(1, 0, fade_samples)
                
                self.sample_data[:fade_samples] *= fade_in
                self.sample_data[-fade_samples:] *= fade_out
                
                self.sample_loaded = True
                print("Default sample pattern created")
                
        except Exception as e:
            print(f"Error loading sample: {e}")
            self.sample_loaded = False
    
    def start(self):
        """Start playing the sample"""
        if self.stream is not None and self.stream.active:
            return
            
        if not self.sample_loaded:
            self.load_sample()  # Load a default sample if none loaded
            
        try:
            self.stream = sd.OutputStream(
                samplerate=self.rate,
                channels=1,
                dtype='float32',
                callback=self.callback,
                blocksize=256,
                latency='low'
            )
            self.active = True
            self.sample_position = 0  # Reset playback position
            self.stream.start()
            print("Sampler started")
        except Exception as e:
            print(f"Error starting sampler stream: {e}")
            self.active = False
            self.stream = None
            
    def stop(self):
        """Stop playing the sample"""
        if self.stream is not None and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.active = False
            print("Sampler stopped")
            
    def set_volume(self, volume):
        """Set the volume of the sample playback"""
        with self.lock:
            self.volume = volume * MASTER_VOLUME
            
    def callback(self, outdata, frames, time_info, status):
        """Process audio data from sample to output"""
        if status:
            print(f"Sampler callback status: {status}")
            
        with self.lock:
            if not self.sample_loaded or self.sample_data is None:
                outdata.fill(0)
                return
                
            # Calculate how many samples to read
            available_samples = len(self.sample_data) - self.sample_position
            
            # If we need to loop
            if available_samples < frames and self.looping:
                # First, fill what we can from the current position
                output = np.zeros(frames, dtype=np.float32)
                output[:available_samples] = self.sample_data[self.sample_position:] * self.volume
                
                # Then loop back to the beginning for the rest
                remaining = frames - available_samples
                cycles = remaining // len(self.sample_data) + 1
                
                for i in range(cycles):
                    chunk_size = min(remaining, len(self.sample_data))
                    if chunk_size > 0:
                        output[available_samples + i*len(self.sample_data):available_samples + i*len(self.sample_data) + chunk_size] = \
                            self.sample_data[:chunk_size] * self.volume
                        remaining -= chunk_size
                
                self.sample_position = chunk_size % len(self.sample_data)
            else:
                # Just play what we have
                if available_samples >= frames:
                    output = self.sample_data[self.sample_position:self.sample_position + frames] * self.volume
                    self.sample_position += frames
                else:
                    # Not enough samples and not looping - fill with zeros after available samples
                    output = np.zeros(frames, dtype=np.float32)
                    output[:available_samples] = self.sample_data[self.sample_position:] * self.volume
                    self.sample_position = len(self.sample_data)  # Reached the end
            
            # Apply soft clipping to prevent distortion
            output = soft_clip(output)
            
            # Copy to output
            outdata[:, 0] = output.astype(np.float32)
