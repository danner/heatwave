import sounddevice as sd
import threading
import numpy as np
import gevent
import time
from scipy.optimize import minimize
from .audio_core import RATE, AMPLITUDE, MASTER_VOLUME, soft_clip, INTERPOLATION_DURATION, BUFFER_SIZE
from state import tube_params, channels, notify_channel_updated
from .pressure_targets import PressureTargetSystem
from .modal_decomposition import ModalDecomposition
from .pressure_matrix import PressureMatrixGenerator

class PressureAlgorithmInput:
    """Class for generating audio from pressure distribution algorithms"""
    
    def __init__(self, rate=RATE):
        self.rate = rate
        self.lock = threading.Lock()
        self.volume = AMPLITUDE * MASTER_VOLUME
        self.active = False
        self.stream = None
        
        # Audio generation parameters
        self.position_count = 10  # Number of positions to calculate pressures at
        self.positions = None  # Will be initialized from tube parameters
        self.time = 0  # Current time in the simulation
        self.frequencies = []  # Active frequencies
        self.amplitudes = []   # Active amplitudes
        
        # Solution storage
        self.current_solution = None
        
        # Physical constants for propane
        self.specific_heat_ratio = 1.4  # γ (gamma) for propane
        self.density = 1.9  # kg/m³ at room temperature
        self.hole_impedance_factor = 0.6  # End correction factor for holes
        
        # Initialize components
        self.pressure_matrix = PressureMatrixGenerator(self)
        self.targets = PressureTargetSystem(self)
        
        # Initialize with tube parameters from state
        self.update_from_tube_params()
    
    def update_from_tube_params(self):
        """Update physics parameters from global tube_params"""
        # Get tube parameters from state
        self.speed_of_sound = tube_params['speed_of_sound']
        self.tube_length = tube_params['tube_length']
        self.tube_diameter = tube_params['tube_diameter']
        self.damping_coefficient = tube_params['damping_coefficient']
        self.hole_size = tube_params['hole_size']
        self.propane_pressure = tube_params['propane_pressure']
        self.reflection_count = tube_params['reflections']
        self.q_factor = tube_params['q_factor']
        
        # Update positions array
        self.positions = np.linspace(0, self.tube_length, self.position_count)
        
        # Update target system with positions
        self.targets.update_positions(self.positions)
        
        # Generate pressure matrix after updating tube parameters
        self.pressure_matrix.generate_pressure_matrix()
    
    def start(self):
        """Start the pressure algorithm audio generator"""
        # Update parameters from state before starting
        self.update_from_tube_params()
        
        if self.stream is not None and self.stream.active:
            return
            
        try:
            print("\n=== Pressure Algorithm Initialization ===")
            print(f"Position count: {self.position_count}")
            print(f"Active frequencies: {len(self.frequencies)}")
            if len(self.frequencies) > 0:
                print(f"  - Frequencies: {np.round(self.frequencies, 1)}")
                print(f"  - Amplitudes: {np.round(self.amplitudes, 2)}")
            print(f"Matrix size: {len(self.pressure_matrix.freq_range)} frequencies x {len(self.positions)} positions")
            
            self.stream = sd.OutputStream(
                samplerate=self.rate,
                channels=1,
                dtype='float32',
                callback=self.callback,
                blocksize=BUFFER_SIZE,
                latency='low'
            )
            self.active = True
            self.time = 0  # Reset simulation time
            
            # Start the optimization using gevent greenlet if animation is active
            if self.targets.active:
                print("Starting animation system with target tracking...")
                self.targets.start_animation()
                
            self.stream.start()
            print("Pressure algorithm started and producing audio")
        except Exception as e:
            print(f"Error starting pressure algorithm stream: {e}")
            self.active = False
            self.stream = None
    
    def stop(self):
        """Stop the pressure algorithm audio generator"""
        # Stop the optimization in target system first
        self.targets.stop_animation()
            
        if self.stream is not None and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.active = False
            print("Pressure algorithm audio generator stopped")
    
    def set_volume(self, volume):
        """Set the volume of the pressure algorithm audio"""
        with self.lock:
            self.volume = volume * MASTER_VOLUME
    
    def set_active_frequencies(self, frequencies, amplitudes):
        """Set the active frequencies and amplitudes for the pressure algorithm"""
        with self.lock:
            self.frequencies = frequencies
            self.amplitudes = amplitudes
            if len(frequencies) > 0:
                print(f"DEBUG: Pressure model frequencies set: {[round(f, 1) for f in frequencies[:4]]}" + 
                      ("..." if len(frequencies) > 4 else ""))
                print(f"DEBUG: Pressure model amplitudes: {[round(a, 2) for a in amplitudes[:4]]}" +
                      ("..." if len(amplitudes) > 4 else ""))
            else:
                print("DEBUG: WARNING - Pressure model got empty frequencies list!")
            
    def callback(self, outdata, frames, time_info, status):
        """Generate audio based on pressure distribution algorithm"""
        if status:
            print(f"DEBUG: Pressure algorithm callback status: {status}")
            
        with self.lock:
            # Periodic debug info (not every callback to avoid console flooding)
            if self.time % 5 < 0.02:  # Every ~5 seconds
                print(f"DEBUG: Pressure callback active, {len(self.frequencies)} frequencies, vol={self.volume:.3f}")
                if len(self.frequencies) > 0:
                    print(f"DEBUG: Using freqs: {[round(f, 1) for f in self.frequencies[:4]]}" + 
                          ("..." if len(self.frequencies) > 4 else ""))
        
            # Create empty output buffer
            output = np.zeros(frames, dtype=np.float32)
            
            # Update animation time (but don't run optimization here)
            if self.targets.active:
                # Update animation time
                frame_duration = frames / self.rate
                self.targets.time += frame_duration
                
                # Update target pressure visualization but don't run optimization here
                # (that happens in the separate optimization thread)
                center = self.targets.get_current_center_position(self.targets.time)
                
                # Log the position less frequently to avoid console spam
                if frames > 1000:  # Log less often for larger frames
                    direction_text = "⬆️ up" if self.targets.direction > 0 else "⬇️ down"
                    print(f"Target center: {center:.3f} {direction_text} (t={self.targets.time:.2f}s)")
        
            # Check if we have frequencies - add diagnostic
            if len(self.frequencies) == 0 or len(self.amplitudes) == 0:
                if self.time % 5 < 0.02:  # Log every ~5 seconds
                    print("DEBUG: WARNING - No frequencies/amplitudes set in pressure model!")
                    
                # Generate a diagnostic test tone so we can at least verify audio path
                test_freq = 220.0  # A3 note
                t = np.arange(frames) / self.rate
                output = 0.3 * np.sin(2 * np.pi * test_freq * t)
                output *= self.volume  # Apply volume
            else:
                # Generate audio samples based on pressure distributions
                time_step = 1.0 / self.rate
                for i in range(frames):
                    # Calculate pressure at a fixed point in the tube over time
                    pressure = self.calculate_pressure_at_time(self.time)
                    
                    # Use the pressure value as the audio sample
                    output[i] = pressure * self.volume
                    
                    # Advance simulation time
                    self.time += time_step
                    
                # Debug output value range occasionally
                if self.time % 5 < 0.02:  # Every ~5 seconds
                    output_min = np.min(output)
                    output_max = np.max(output)
                    output_rms = np.sqrt(np.mean(np.square(output)))
                    print(f"DEBUG: Output range: min={output_min:.3f}, max={output_max:.3f}, rms={output_rms:.3f}")
        
        # Apply soft clipping to prevent distortion
        output = soft_clip(output)
        
        # Copy to output
        outdata[:, 0] = output.astype(np.float32)
    
    def calculate_pressure_at_time(self, t):
        """Calculate pressure at a specific time using multiple monitoring positions"""
        # Use multiple monitoring positions for richer harmonic content
        monitor_positions = [
            self.tube_length * 0.25,  # 1/4 of the way down the tube
            self.tube_length * 0.5,   # Middle of the tube
            self.tube_length * 0.75   # 3/4 of the way down the tube
        ]
        
        # Sum contributions from all active frequencies
        pressure = 0
        
        # Debug periodically
        debug_this_call = (t % 5 < 0.01) and len(self.frequencies) > 0
        frequencies_debug = []
        
        for i, freq in enumerate(self.frequencies):
            if i < len(self.amplitudes):
                amplitude = self.amplitudes[i]
                if debug_this_call and i < 2:  # Only collect debug data for first 2 freqs
                    frequencies_debug.append(f"{freq:.1f}Hz")
                
                # Calculate angular frequency
                omega = 2 * np.pi * freq
                
                # Calculate wave number (k = ω/c)
                k = omega / self.speed_of_sound
                
                # For each monitoring position
                position_contribution = 0
                for pos in monitor_positions:
                    # Calculate pressure contribution at this position
                    position_component = np.cos(k * pos)
                    time_component = np.sin(omega * t)
                    
                    # Apply damping based on frequency and position
                    damping = np.exp(-self.damping_coefficient * pos * (freq / 110))
                    
                    # Add contribution from this position
                    position_contribution += position_component * time_component * damping
                
                # Average the contributions from different positions
                position_contribution /= len(monitor_positions)
                
                # Add to total pressure
                pressure += amplitude * position_contribution
        
        # Add harmonic content through modest non-linearity
        pressure += 0.1 * pressure**3
        
        # Debug pressure value periodically
        if debug_this_call:
            print(f"DEBUG: Pressure calculation using {len(frequencies_debug)} freqs ({', '.join(frequencies_debug)}) = {pressure:.3f}")
        
        return pressure
    
    # Delegate pressure calculation to the pressure matrix module
    def calculate_t_network_pressures(self, frequency, positions):
        """Delegate to pressure matrix module"""
        return self.pressure_matrix.calculate_t_network_pressures(frequency, positions)
    
    def update_from_synth_channels(self, channels):
        """Update frequencies and amplitudes from synth channels"""
        frequencies = []
        amplitudes = []
        
        for channel_id, channel in channels.items():
            if not channel['mute'] and channel['volume'] > 0:
                frequencies.append(max(1, channel['frequency']))
                amplitudes.append(channel['volume'])
        
        self.set_active_frequencies(frequencies, amplitudes)
        return len(frequencies) > 0  # Return True if we have active channels
    
    # Delegate to the pressure matrix module
    def combine_frequency_pressures(self, frequencies, amplitudes=None):
        """Delegate to pressure matrix module"""
        return self.pressure_matrix.combine_frequency_pressures(frequencies, amplitudes)
    
    def reset_animation(self):
        """Proxy method to reset animation in target system"""
        return self.targets.reset()
    
    def configure_model_and_apply_frequencies(self, profile="gaussian", num_freqs=4, animated=False):
        """
        Configure the pressure model and apply appropriate frequencies using modal decomposition
        
        Args:
            profile: Type of pressure profile to generate ("gaussian", "sine", etc.)
            num_freqs: Number of frequencies to use
            animated: Whether the target should animate through the tube
            
        Returns:
            List of frequencies that were applied
        """
        print(f"\n=== Pressure Model Configuration ===")
        print(f"Profile: {profile}")
        print(f"Animation: {'Enabled' if animated else 'Disabled'}")
        print(f"Number of frequencies: {num_freqs}")
        print("Using modal decomposition")
        
        # Create target pressure distribution
        if animated:
            self.targets.create_animated_target_pressure(0)  # Start at time 0
            self.targets.profile = profile
            self.targets.active = True
            print(f"Animated {profile} pressure target created")
        else:
            self.targets.create_target_pressure(profile=profile)
            self.targets.active = False
            print(f"Static {profile} pressure target created")
        
        # Use modal decomposition to find optimal frequencies
        print("\n=== Running Modal Decomposition ===")
        modal = ModalDecomposition(self)
        
        # Use more modes to get better quality
        modes_count = max(12, num_freqs*3)
        print(f"Analyzing with {modes_count} theoretical modes")
        
        frequencies, amplitudes = modal.decompose_target(self.targets.target_pressure, num_modes=modes_count)
        
        if frequencies is not None and amplitudes is not None:
            print(f"Modal decomposition found {len(frequencies)} usable frequencies:")
            for i, (freq, amp) in enumerate(zip(frequencies[:5], amplitudes[:5])):
                print(f"  Mode {i}: {freq:.1f} Hz, amplitude {amp:.3f}")
            if len(frequencies) > 5:
                print(f"  ...and {len(frequencies)-5} more modes")
                
            # Apply to audio and channels
            self.set_active_frequencies(frequencies, amplitudes)
            self._apply_frequencies_to_channels(frequencies, amplitudes)
            
            # Store solution for visualization
            achieved_pressure = self.combine_frequency_pressures(frequencies, amplitudes)
            self.current_solution = {
                'frequencies': frequencies,
                'amplitudes': amplitudes,
                'target': self.targets.target_pressure,
                'achieved': achieved_pressure
            }
            
            return frequencies
        
        # If we get here, something went wrong
        print("ERROR: Modal decomposition failed to produce valid frequencies")
        return []
    
    def _apply_frequencies_to_channels(self, frequencies, amplitudes=None):
        """Apply the calculated frequencies and amplitudes to synth channels"""
        if amplitudes is None:
            amplitudes = np.ones(len(frequencies))
            
        print(f"\n=== Applying {len(frequencies)} Frequencies to Channels ===")
        
        # Find significant amplitudes
        if len(amplitudes) > 8:  # Need to select subset if we have too many
            # Get indices sorted by amplitude
            indices = np.argsort(amplitudes)[::-1]  # Sort descending
            # Take top 8
            indices = indices[:8]
            # Get corresponding frequencies and amplitudes
            selected_freqs = [frequencies[i] for i in indices]
            selected_amps = [amplitudes[i] for i in indices]
        else:
            selected_freqs = frequencies
            selected_amps = amplitudes
            
        # Apply to channels - maximum of 8
        num_to_apply = min(len(selected_freqs), 8)
        
        for i in range(num_to_apply):
            freq = selected_freqs[i]
            amp = selected_amps[i] if i < len(selected_amps) else 1.0
            # Scale amplitude by base volume
            volume = min(1.0, amp * 1.0)
            
            print(f"  Channel {i}: {freq:.1f}Hz with amplitude {volume:.2f}")
            
            # Update the channel
            channels[i]['frequency'] = float(freq)
            channels[i]['mute'] = False
            channels[i]['volume'] = float(volume)
            notify_channel_updated(i)
            
        # Mute any unused channels
        for i in range(num_to_apply, 8):
            channels[i]['mute'] = True
            notify_channel_updated(i)