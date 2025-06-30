import sounddevice as sd
from threading import Lock  # Only import Lock instead of the full threading module
import numpy as np
from .audio_core import RATE, AMPLITUDE, MASTER_VOLUME, soft_clip, BUFFER_SIZE  # Removed unused INTERPOLATION_DURATION
from state import tube_params, channels, notify_channel_updated
from .pressure_targets import PressureTargetSystem
from .modal_decomposition import ModalDecomposition
from .pressure_matrix import PressureMatrixGenerator
from .pressure_utils import calculate_pressure_vector, update_precalculated_values
import time  # Added missing import for time

class PressureAlgorithmInput:
    """Class for generating audio from pressure distribution algorithms"""
    
    def __init__(self, rate=RATE):
        self.rate = rate
        self.lock = Lock()  # Updated to use Lock directly
        self.volume = AMPLITUDE * MASTER_VOLUME
        self.active = False
        self.stream = None
        
        # Audio generation parameters
        self.position_count = 8  # Number of positions to calculate pressures at
        self.positions = None  # Will be initialized from tube parameters
        self.time = 0  # Current time in the simulation
        self.frequencies = []  # Active frequencies
        self.amplitudes = []   # Active amplitudes
        
        # Initialize components
        self.pressure_matrix = PressureMatrixGenerator(self)
        self.targets = PressureTargetSystem(self)
        
        # Precalculated values for performance optimization
        self.monitor_positions = []  # Will be initialized in update_from_tube_params
        self.precalc_omegas = []  # Angular frequencies
        self.precalc_wave_numbers = []  # Wave numbers (k)
        self.precalc_position_components = []  # Position components for each freq and position
        self.precalc_damping_factors = []  # Damping factors for each freq and position
        self.precalc_position_weights = []  # Weights to apply to each position
        
        # Add cache for physics parameters to avoid unnecessary recalculations
        self._cached_physics_params = None
        
        # Preallocated arrays for optimized audio calculation
        self.time_step_vector = None    # Constant step vector for time calculations
        self.last_frame_size = 0        # Track frame size for reallocation if needed
        
        # Initialize debug timer
        self.last_debug_time = 0.0  # Fixed uninitialized debug timer
    
        # Add harmonic gain as a configurable parameter
        self.harmonic_gain = 0.1  # Default value for harmonic non-linearity
        
        # Cache for ModalDecomposition instance
        self.modal_decomposition = None  # Will store a cached instance
    
        # Initialize with tube parameters from state
        self.update_from_tube_params()
    
    def update_from_tube_params(self):
        """Update physics parameters from global tube_params"""
        # Extract physics-only parameters that would require matrix rebuilding
        current_physics_params = {
            'speed_of_sound': tube_params['speed_of_sound'],
            'tube_length': tube_params['tube_length'],
            'tube_diameter': tube_params['tube_diameter'],
            'damping_coefficient': tube_params['damping_coefficient'],
            'hole_size': tube_params['hole_size'],
            'reflection_count': tube_params['reflections'],
            'q_factor': tube_params['q_factor'],
            'propane_pressure': tube_params['propane_pressure'],  # Added missing field
            'position_count': self.position_count  # Include this since it affects positions array
        }
        
        # If physics parameters haven't changed, skip expensive recalculations
        if self._cached_physics_params == current_physics_params:
            print("Physics parameters unchanged, skipping matrix regeneration")
            return
            
        # Physics parameters have changed, update cache and recalculate
        print("Physics parameters changed, updating matrices and precalculated values")
        self._cached_physics_params = current_physics_params.copy()
        
        # Get tube parameters from state
        self.speed_of_sound = tube_params['speed_of_sound']
        self.tube_length = tube_params['tube_length']
        self.tube_diameter = tube_params['tube_diameter']
        self.damping_coefficient = tube_params['damping_coefficient']
        self.hole_size = tube_params['hole_size']
        self.propane_pressure = tube_params['propane_pressure']  # Added missing assignment
        self.reflection_count = tube_params['reflections']
        self.q_factor = tube_params['q_factor']
        
        # Update positions array
        self.positions = np.linspace(0, self.tube_length, self.position_count)
        
        # Update target system with positions
        self.targets.update_positions(self.positions)
        
        # Generate pressure matrix after updating tube parameters
        self.pressure_matrix.generate_pressure_matrix()
        
        # Update monitor positions (previously calculated on every call)
        self.monitor_positions = [
            self.tube_length * 0.25,  # 1/4 of the way down the tube
            self.tube_length * 0.5,   # Middle of the tube
            self.tube_length * 0.75   # 3/4 of the way down the tube
        ]
        self.precalc_position_weights = np.ones(len(self.monitor_positions)) / len(self.monitor_positions)
        
        # Update precalculated values if frequencies are available
        if len(self.frequencies) > 0:
            self._update_precalculated_values()
    
    def _update_precalculated_values(self):
        """Precalculate values that don't change between audio frames"""
        result = update_precalculated_values(
            self.frequencies,
            self.speed_of_sound,
            self.damping_coefficient,
            self.tube_length,
            self.positions,
            self.amplitudes
        )
        if result:
            (
                self.precalc_omegas,
                self.precalc_envelope,
                self.precalc_position_weights,
                self.precalc_wave_numbers,
                self.precalc_position_components,
                self.precalc_damping_factors,
            ) = result

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
                # Precalculate values for performance
                self._update_precalculated_values()
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
            
            # Start the target animation if active
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
                # Precalculate values for performance when frequencies change
                self._update_precalculated_values()
            else:
                print("DEBUG: WARNING - Pressure model got empty frequencies list!")
            
    def callback(self, outdata, frames, time_info, status):
        """Generate audio based on pressure distribution algorithm"""
        if status:
            print(f"DEBUG: Pressure algorithm callback status: {status}")
            
        with self.lock:
            # Reduce debug logging frequency
            current_time = time.time()
            debug_this_frame = (current_time - self.last_debug_time > 5.0)
            if debug_this_frame:
                self.last_debug_time = current_time
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
                
                # Only update visualization info if we're actually logging it
                if debug_this_frame:
                    center = self.targets.get_current_center_position(self.targets.time)
                    direction_text = "⬆️ up" if self.targets.direction > 0 else "⬇️ down"
                    print(f"Target center: {center:.3f} {direction_text} (t={self.targets.time:.2f}s)")
    
            # Check if we have frequencies - add diagnostic
            if len(self.frequencies) == 0 or len(self.amplitudes) == 0:
                if debug_this_frame:
                    print("DEBUG: WARNING - No frequencies/amplitudes set in pressure model!")
                    
                # Generate a diagnostic test tone so we can at least verify audio path
                t = np.arange(frames) / self.rate
                output = 0.3 * np.sin(2 * np.pi * 220.0 * t)
                output *= self.volume  # Apply volume
            else:
                # Generate audio samples using vectorized approach
                self.calculate_pressure_vector(output, frames, self.time)
                output *= self.volume  # Apply volume scaling
                
                # Advance simulation time
                self.time += frames / self.rate
                
                # Debug output value range occasionally
                if debug_this_frame:
                    output_min = np.min(output)
                    output_max = np.max(output)
                    output_rms = np.sqrt(np.mean(np.square(output)))
                    print(f"DEBUG: Output range: min={output_min:.3f}, max={output_max:.3f}, rms={output_rms:.3f}")
        
        # Apply soft clipping to prevent distortion
        output = soft_clip(output)
        
        # Copy to output
        outdata[:, 0] = output.astype(np.float32)
    
    def on_target_changed(self, target_pressure):
        """Handle target change notification from target system"""
        if not self.active or target_pressure is None:
            return
            
        print("Target change detected, optimizing frequencies...")
        
        # Use cached ModalDecomposition instance if available
        if self.modal_decomposition is None:
            self.modal_decomposition = ModalDecomposition(self)
        
        # Limit the number of modes for performance
        num_freqs = 4
        modes_count = max(10, num_freqs * 2)
        
        # Run the decomposition
        frequencies, amplitudes = self.modal_decomposition.decompose_target(target_pressure, num_modes=modes_count)
        
        if frequencies is not None and amplitudes is not None:
            print(f"Found {len(frequencies)} frequencies for new target")
            
            # Apply to audio
            self.set_active_frequencies(frequencies, amplitudes)
            
            # Also update channel display
            self._apply_frequencies_to_channels(frequencies, amplitudes)
        else:
            print("Failed to find frequencies for new target")
    
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
            # Set up target animation system
            self.targets.profile = profile
            self.targets.active = True
            
            # For animated targets, we'll get the first target
            self.targets.create_animated_target_pressure(0)  # Start at time 0
            print(f"Animated {profile} pressure target system created")
        else:
            # For static targets, create it directly
            self.targets.create_target_pressure(profile=profile)
            self.targets.active = False
            print(f"Static {profile} pressure target created")
        
        # Use cached ModalDecomposition instance if available
        if self.modal_decomposition is None:
            self.modal_decomposition = ModalDecomposition(self)
        
        # Use more modes to get better quality
        modes_count = max(12, num_freqs * 3)
        print(f"Analyzing with {modes_count} theoretical modes")
        
        frequencies, amplitudes = self.modal_decomposition.decompose_target(self.targets.target_pressure, num_modes=modes_count)
        
        if frequencies is not None and amplitudes is not None:
            print(f"Modal decomposition found {len(frequencies)} usable frequencies:")
            for i, (freq, amp) in enumerate(zip(frequencies[:5], amplitudes[:5])):
                print(f"  Mode {i}: {freq:.1f} Hz, amplitude {amp:.3f}")
            if len(frequencies) > 5:
                print(f"  ...and {len(frequencies)-5} more modes")
                
            # Apply to audio and channels
            self.set_active_frequencies(frequencies, amplitudes)
            self._apply_frequencies_to_channels(frequencies, amplitudes)
            
            return frequencies
        
        # If we get here, something went wrong
        print("ERROR: Modal decomposition failed to produce valid frequencies")
        return []
    
    def calculate_pressure_vector(self, output, frames, start_time):
        """
        Precalculate pressure for all samples in a frame
        """
        if len(self.frequencies) == 0 or len(self.amplitudes) == 0:
            return output
            
        # Check if we need to create or resize the precalculated time step vector
        if self.time_step_vector is None or frames != self.last_frame_size:
            # Create time step vector (constant steps, to be reused)
            time_step = 1.0 / self.rate
            self.time_step_vector = np.arange(frames) * time_step
            self.last_frame_size = frames
    
        # Create time vector for this frame by adding current start time
        # This avoids reallocating a new array on each callback
        time_vector = self.time_step_vector + start_time
    
        # ULTRA-OPTIMIZED VECTORIZED IMPLEMENTATION:
        
        # 1. Calculate sin term: shape (F, frames)
        #    Broadcasting: (F,1) * (frames,) -> (F, frames)
        sin_term = np.sin(self.precalc_omegas * time_vector)
        
        # 2. Reshape sin_term for broadcasting with positions: shape (F, 1, frames)
        sin_term = sin_term[:, np.newaxis, :]
        
        # 3. Reshape precalculated envelope for broadcasting: shape (F, P, 1)
        envelope = self.precalc_envelope[:, :, np.newaxis]
        
        # 4. Calculate contribution with single operation: shape (F, P, frames)
        #    Broadcasting: (F,P,1) * (F,1,frames) -> (F,P,frames)
        contribution = envelope * sin_term
        
        # 5. Apply position weights and sum over all frequencies and positions
        # Manual summation to avoid tensordot issues
        weighted_contribution = contribution * self.precalc_position_weights[np.newaxis, :, np.newaxis]
        output[:] = np.sum(np.sum(weighted_contribution, axis=0), axis=0)
        
        # 6. Add harmonic content through configurable non-linearity
        output += self.harmonic_gain * output**3
        
        return output

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