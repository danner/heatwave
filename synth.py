import numpy as np
import sounddevice as sd
import threading
from audio_core import RATE, AMPLITUDE, MASTER_VOLUME, INTERPOLATION_DURATION, soft_clip

class ToneSynth:
    """Multi-channel synth class using sample-accurate control"""
    def __init__(self, num_channels=8, rate=RATE):
        self.rate = rate
        self.num_channels = num_channels
        self.lock = threading.Lock()
        
        # Initialize state for each channel
        self.phases = np.zeros(num_channels)
        self.current_freqs = np.ones(num_channels) * 110.0
        self.target_freqs = np.ones(num_channels) * 110.0
        self.volumes = np.ones(num_channels) * AMPLITUDE
        self.interp_start_freqs = np.ones(num_channels) * 110.0
        self.interp_times = np.zeros(num_channels)
        self.interp_active = np.zeros(num_channels, dtype=bool)
        self.muted = np.zeros(num_channels, dtype=bool)
        
        # Start the audio stream
        self.stream = sd.OutputStream(
            samplerate=rate,
            channels=1,
            dtype='float32',
            callback=self.callback,
            blocksize=256,  # Smaller blocksize for lower latency
            latency='low'
        )
        self.stream.start()
        
    def set_frequency(self, channel, freq):
        with self.lock:
            if freq != self.target_freqs[channel]:
                print(f"Interpolating frequency for channel {channel} from {self.current_freqs[channel]} to {freq}")
                self.interp_start_freqs[channel] = self.current_freqs[channel]
                self.target_freqs[channel] = freq
                self.interp_times[channel] = 0.0
                self.interp_active[channel] = True
                return True
            return False
    
    def set_volume(self, channel, volume, muted=False):
        with self.lock:
            self.volumes[channel] = volume
            self.muted[channel] = muted
    
    def callback(self, outdata, frames, time_info, status):
        if status:
            print(f"Audio callback status: {status}")
        
        # Create empty output buffer
        output = np.zeros(frames, dtype=np.float32)
        
        with self.lock:
            for ch in range(self.num_channels):
                if self.muted[ch]:
                    continue
                    
                if self.interp_active[ch]:
                    # Calculate time sequence for this buffer
                    t_seq = np.arange(frames) / self.rate
                    interp_t = self.interp_times[ch] + t_seq
                    
                    # Calculate interpolation factor (0 to 1)
                    alpha = np.minimum(interp_t / INTERPOLATION_DURATION, 1.0)
                    
                    # Interpolate frequency
                    freq = (1 - alpha) * self.interp_start_freqs[ch] + alpha * self.target_freqs[ch]
                    
                    # Calculate phase increments based on instantaneous frequency
                    phase_incs = 2 * np.pi * freq / self.rate
                    
                    # Calculate phases for all samples in this buffer
                    phases = np.zeros(frames)
                    phases[0] = self.phases[ch]
                    for i in range(1, frames):
                        phases[i] = phases[i-1] + phase_incs[i-1]
                    
                    # Generate sine wave with interpolated frequency
                    wave = self.volumes[ch] * MASTER_VOLUME * np.sin(phases)
                    
                    # Update phase for next buffer
                    self.phases[ch] = phases[-1] + phase_incs[-1]
                    self.phases[ch] %= 2 * np.pi  # Keep phase within [0, 2π]
                    
                    # Update interpolation time and check if complete
                    self.interp_times[ch] += frames / self.rate
                    if self.interp_times[ch] >= INTERPOLATION_DURATION:
                        self.interp_active[ch] = False
                        self.current_freqs[ch] = self.target_freqs[ch]
                else:
                    # Steady-state sine wave
                    freq = self.current_freqs[ch]
                    phase_inc = 2 * np.pi * freq / self.rate
                    phases = self.phases[ch] + np.arange(frames) * phase_inc
                    wave = self.volumes[ch] * MASTER_VOLUME * np.sin(phases)
                    self.phases[ch] = (phases[-1] + phase_inc) % (2 * np.pi)
                
                # Mix this channel into the output
                output += wave
        
        # Apply soft clipping to prevent distortion when channels are mixed
        output = soft_clip(output)
        
        # Copy to stereo output
        outdata[:, 0] = output.astype(np.float32)

    def close(self):
        if self.stream is not None and self.stream.active:
            self.stream.stop()
            self.stream.close()
