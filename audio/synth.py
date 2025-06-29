import numpy as np
import sounddevice as sd
import threading
import time
from .audio_core import RATE, AMPLITUDE, MASTER_VOLUME, soft_clip, BUFFER_SIZE

class ToneSynth:
    """Multi-channel synth class with robust error handling"""
    def __init__(self, num_channels=8, rate=RATE):
        self.rate = rate
        self.num_channels = num_channels
        self.lock = threading.Lock()
        
        # Simplified state - only the essential variables
        self.phases = np.zeros(num_channels)
        self.frequencies = np.ones(num_channels) * 110.0
        self.volumes = np.ones(num_channels) * AMPLITUDE
        self.muted = np.zeros(num_channels, dtype=bool)
        
        # For tracking errors and performance
        self.error_count = 0
        self.last_successful_callback = time.time()
        self.debug_mode = True  # Set to False in production
        
        # Start the audio stream
        self.stream = sd.OutputStream(
            samplerate=rate,
            channels=1,
            dtype='float32',
            callback=self.callback,
            blocksize=BUFFER_SIZE,
            latency='low'
        )
        print("Starting ToneSynth with simplified architecture")
        self.stream.start()
    
    def set_frequency(self, channel, freq):
        """Set frequency for a channel (thread-safe)"""
        if not (0 <= channel < self.num_channels):
            return False
            
        # Simple bounds checking
        freq = max(1.0, min(20000.0, freq))
        
        with self.lock:
            if self.frequencies[channel] != freq:
                self.frequencies[channel] = freq
                return True
        return False
    
    def set_volume(self, channel, volume, muted=False):
        """Set volume for a channel (thread-safe)"""
        if not (0 <= channel < self.num_channels):
            return
            
        with self.lock:
            self.volumes[channel] = volume
            self.muted[channel] = muted
    
    def callback(self, outdata, frames, time_info, status):
        """Ultra-reliable audio callback that can't fail"""
        # Always fill with zeros first in case of error
        outdata.fill(0)
        
        try:
            # Performance tracking
            callback_start = time.time()
            
            # Create output buffer
            output = np.zeros(frames, dtype=np.float32)
            
            # Only lock when copying the data
            with self.lock:
                local_frequencies = self.frequencies.copy()
                local_volumes = self.volumes.copy()
                local_muted = self.muted.copy()
                local_phases = self.phases.copy()
            
            # Process each channel without holding the lock
            for ch in range(self.num_channels):
                if local_muted[ch]:
                    continue
                    
                # Simple sine wave generation - no interpolation
                freq = local_frequencies[ch]
                volume = local_volumes[ch] * MASTER_VOLUME
                
                # Generate sine wave
                phase_inc = 2 * np.pi * freq / self.rate
                phases = local_phases[ch] + np.arange(frames) * phase_inc
                wave = volume * np.sin(phases)
                
                # Add to output
                output += wave
                
                # Store the final phase for next time
                local_phases[ch] = phases[-1] % (2 * np.pi)
            
            # Apply soft clipping
            output = soft_clip(output)
            
            # Copy to output buffer
            outdata[:, 0] = output
            
            # Only lock when updating phases
            with self.lock:
                self.phases = local_phases
            
            # Update successful callback time
            self.last_successful_callback = time.time()
            
        except Exception as e:
            self.error_count += 1
            if self.debug_mode or self.error_count < 5:
                print(f"Audio error ({self.error_count}): {e}")
            
            # Don't need to fill with zeros as we did that at the start
            
        # Debug info occasionally
        if self.debug_mode and self.error_count == 0 and time.time() % 10 < 0.1:
            elapsed = time.time() - self.last_successful_callback
            print(f"Audio running smoothly for {elapsed:.1f} seconds")

    def close(self):
        """Clean up resources"""
        if self.stream is not None:
            if self.stream.active:
                self.stream.stop()
            self.stream.close()
            self.stream = None