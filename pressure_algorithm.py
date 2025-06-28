import sounddevice as sd
import threading
import numpy as np
import gevent
import time
from scipy.optimize import minimize
from audio_core import RATE, AMPLITUDE, MASTER_VOLUME, soft_clip, INTERPOLATION_DURATION, BUFFER_SIZE
from state import tube_params, channels
from pressure_targets import PressureTargetSystem

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
        
        # Add pressure matrix parameters
        self.pressure_matrix = None  # Will store pre-calculated pressures
        self.freq_range = None       # Will store frequencies used in matrix
        self.min_matrix_freq = 20    # Minimum frequency for matrix (Hz)
        self.max_matrix_freq = 500   # Maximum frequency for matrix (Hz)
        self.freq_resolution = 1     # Frequency resolution (Hz)
        
        # Initialize target system
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
        
        # Physical constants for propane
        self.specific_heat_ratio = 1.4  # γ (gamma) for propane
        self.density = 1.9  # kg/m³ at room temperature
        self.hole_impedance_factor = 0.6  # End correction factor for holes
        
        # Update positions array
        self.positions = np.linspace(0, self.tube_length, self.position_count)
        
        # Update target system with positions
        self.targets.update_positions(self.positions)
        
        # Generate pressure matrix after updating tube parameters
        self.generate_pressure_matrix()
    
    def generate_pressure_matrix(self):
        """Pre-calculate pressure matrix for all frequencies and positions"""
        print("Generating pressure matrix...")
        start_time = time.time()
        
        # Use a more efficient frequency resolution - 2Hz instead of 1Hz
        self.freq_resolution = 2
        
        # Create frequency range with optimized resolution
        freq_count = int((self.max_matrix_freq - self.min_matrix_freq) / self.freq_resolution) + 1
        self.freq_range = np.linspace(self.min_matrix_freq, self.max_matrix_freq, freq_count)
        
        # Initialize pressure matrix with dimensions [freq_count, position_count]
        self.pressure_matrix = np.zeros((len(self.freq_range), len(self.positions)))
        
        # Calculate pressure for each frequency at each position - vectorize where possible
        for i, freq in enumerate(self.freq_range):
            # Calculate pressure distribution for this frequency
            pressures = self.calculate_t_network_pressures(freq, self.positions)
            
            # Store in matrix
            self.pressure_matrix[i, :] = pressures
    
        # Report on matrix size and generation time
        matrix_size_mb = self.pressure_matrix.nbytes / (1024 * 1024)
        elapsed_time = time.time() - start_time
        print(f"Pressure matrix generated: {len(self.freq_range)}x{len(self.positions)} ({matrix_size_mb:.1f} MB)")
        print(f"Generation took {elapsed_time:.2f} seconds")
    
    def get_pressure_from_matrix(self, frequency, position_index):
        """Get pressure value from pre-calculated matrix using optimized interpolation"""
        # Direct lookup for exact matches to avoid interpolation overhead
        if frequency in self.freq_range:
            freq_idx = np.where(self.freq_range == frequency)[0][0]
            return self.pressure_matrix[freq_idx, position_index]
            
        # Faster bounds check
        if frequency <= self.min_matrix_freq:
            return self.pressure_matrix[0, position_index]
        elif frequency >= self.max_matrix_freq:
            return self.pressure_matrix[-1, position_index]
        
        # Optimized index calculation using numpy
        freq_idx_low = int((frequency - self.min_matrix_freq) / self.freq_resolution)
        freq_idx_high = min(freq_idx_low + 1, len(self.freq_range) - 1)
        
        # Get frequencies and pressures for interpolation
        freq_low = self.freq_range[freq_idx_low]
        freq_high = self.freq_range[freq_idx_high]
        pressure_low = self.pressure_matrix[freq_idx_low, position_index]
        pressure_high = self.pressure_matrix[freq_idx_high, position_index]
        
        # Linear interpolation
        t = (frequency - freq_low) / (freq_high - freq_low) if freq_high > freq_low else 0
        return pressure_low + t * (pressure_high - pressure_low)
        
    def start(self):
        """Start the pressure algorithm audio generator"""
        # Update parameters from state before starting
        self.update_from_tube_params()
        
        if self.stream is not None and self.stream.active:
            return
            
        try:
            self.stream = sd.OutputStream(
                samplerate=self.rate,
                channels=1,
                dtype='float32',
                callback=self.callback,
                blocksize=BUFFER_SIZE,  # Use larger buffer from audio_core
                latency='high'  # Higher latency for stability
            )
            self.active = True
            self.time = 0  # Reset simulation time
            
            # Start the optimization using gevent greenlet if animation is active
            if self.targets.active:
                self.targets.start_animation()
                
            self.stream.start()
            print("Pressure algorithm audio generator started")
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
            
    def callback(self, outdata, frames, time_info, status):
        """Generate audio based on pressure distribution algorithm"""
        if status:
            print(f"Pressure algorithm callback status: {status}")
            
        with self.lock:
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
            
            # Generate audio samples based on pressure distributions
            time_step = 1.0 / self.rate
            for i in range(frames):
                # Calculate pressure at a fixed point in the tube over time
                pressure = self.calculate_pressure_at_time(self.time)
                
                # Use the pressure value as the audio sample
                output[i] = pressure * self.volume
                
                # Advance simulation time
                self.time += time_step
            
            # Apply soft clipping to prevent distortion
            output = soft_clip(output)
            
            # Copy to output
            outdata[:, 0] = output.astype(np.float32)
    
    def calculate_pressure_at_time(self, t):
        """Calculate pressure at a specific time at a fixed monitoring position"""
        # Fixed monitoring position (can be adjusted for different harmonic content)
        monitor_position = self.tube_length * 0.75  # 3/4 of the way down the tube
        
        # Sum contributions from all active frequencies
        pressure = 0
        for i, freq in enumerate(self.frequencies):
            if i < len(self.amplitudes):
                amplitude = self.amplitudes[i]
                
                # Calculate angular frequency
                omega = 2 * np.pi * freq
                
                # Calculate wave number (k = ω/c)
                k = omega / self.speed_of_sound
                
                # Calculate pressure contribution from this frequency
                # Standing wave pattern with position and time components
                position_component = np.cos(k * monitor_position)
                time_component = np.sin(omega * t)
                
                # Apply damping based on frequency
                damping = np.exp(-self.damping_coefficient * monitor_position * (freq / 110))
                
                # Add contribution to overall pressure
                pressure += amplitude * position_component * time_component * damping
        
        # Add harmonic content through modest non-linearity
        pressure += 0.1 * pressure**3
        
        return pressure
    
    def calculate_t_network_pressures(self, frequency, positions):
        """Calculate pressure distribution using T-network model (similar to physics-engine.js)"""
        # Convert angular frequency
        omega = 2 * np.pi * frequency
        
        # Calculate wave number (k = ω/c)
        k = omega / self.speed_of_sound
        
        # Calculate base acoustic impedance (Z₀)
        z0 = self.density * self.speed_of_sound
        
        # Array to store calculated pressures at each position
        pressures = np.zeros(len(positions))
        
        # Both ends are closed (reflection coefficient = +1)
        left_end_reflection = 1.0   # Closed end at x=0
        right_end_reflection = 1.0  # Closed end at x=L
        
        # Calculate Q-weighted damping coefficient - lower damping = sharper resonances
        effective_damping = self.damping_coefficient / self.q_factor
        
        # Calculate for each position considering multiple reflections
        for i, x in enumerate(positions):
            # Incident wave traveling right (initial wave)
            incident_wave = np.cos(k * x)
            
            # Add initial incident wave with position-based damping
            damping_factor = np.exp(-effective_damping * x)
            pressures[i] += incident_wave * damping_factor
            
            # First reflection - more strongly weighted to enhance standing wave formation
            if self.reflection_count >= 1:
                first_reflection_path = 2 * self.tube_length - x
                first_reflection_damping = np.exp(-effective_damping * first_reflection_path)
                first_reflected_wave = right_end_reflection * np.cos(k * first_reflection_path)
                pressures[i] += first_reflected_wave * first_reflection_damping
            
            # Add remaining reflections with uniform physical properties
            for r in range(2, self.reflection_count + 1):
                reflected_phase = 1
                reflection_path = 0
                
                if r % 2 == 1:
                    # Odd reflections (right end first)
                    reflected_phase = right_end_reflection
                    reflection_path = r * self.tube_length - x
                else:
                    # Even reflections (left end after right end)
                    reflected_phase = right_end_reflection * left_end_reflection
                    reflection_path = r * self.tube_length + x
                
                # Apply damping based on path length
                reflection_damping = np.exp(-effective_damping * reflection_path)
                
                # Add this reflection to the total pressure
                reflected_wave = reflected_phase * np.cos(k * reflection_path)
                pressures[i] += reflected_wave * reflection_damping
            
            # Apply standing wave interference effects - this naturally enhances resonant frequencies
            if self.reflection_count > 2:
                # Standing wave factor naturally enhances resonances without targeting frequencies
                standing_wave_factor = 1.0 + 0.3 * np.abs(np.sin(k * self.tube_length)) * (self.reflection_count / 5)
                pressures[i] *= standing_wave_factor
            
            # Apply hole effects from T-network model
            if self.hole_size > 0:
                # Calculate impedance effects from the holes
                hole_impedance = z0 * k * (self.hole_size / 2) * (1 + self.hole_impedance_factor)
                impedance_effect = (z0 / hole_impedance) * 0.3
                pressures[i] *= (1 + impedance_effect * np.sin(k * x))
            
            # Take absolute value for magnitude
            pressures[i] = np.abs(pressures[i])
        
        return pressures
    
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
    
    def combine_frequency_pressures(self, frequencies, amplitudes=None):
        """Combine pressure distributions from multiple frequencies using optimized matrix operations"""
        if amplitudes is None:
            amplitudes = np.ones(len(frequencies))
            
        # Initialize combined pressure
        combined = np.zeros(len(self.positions))
        
        # Check if we have a valid pressure matrix
        if self.pressure_matrix is None:
            # Fall back to direct calculation if matrix is not available
            for i, freq in enumerate(frequencies):
                if i < len(amplitudes):
                    pressure = self.calculate_t_network_pressures(freq, self.positions)
                    combined += amplitudes[i] * pressure
        else:
            # Use pre-calculated matrix with vectorized operations
            amplitudes_array = np.array(amplitudes[:len(frequencies)])
            
            # Create an array to store all pressure contributions
            all_pressures = np.zeros((len(frequencies), len(self.positions)))
            
            # Calculate all pressures at once for each frequency
            for i, freq in enumerate(frequencies):
                if i < len(amplitudes):
                    # Get pressure for this frequency at all positions
                    for pos_idx in range(len(self.positions)):
                        all_pressures[i, pos_idx] = self.get_pressure_from_matrix(freq, pos_idx)
            
            # Multiply each frequency's pressure by its amplitude and sum
            # Using broadcasting to multiply each row by its amplitude
            amplitudes_column = amplitudes_array[:, np.newaxis]
            weighted_pressures = all_pressures * amplitudes_column
            combined = np.sum(weighted_pressures, axis=0)
            
        # Normalize the combined pressure
        max_pressure = np.max(combined)
        if max_pressure > 0:
            combined = combined / max_pressure
                
        return combined
        
    def pressure_error_function(self, freqs, target_pressure):
        """Calculate error between a set of frequencies and the target pressure with optimized calculation"""
        # Ensure frequencies are positive and in reasonable range
        freqs = np.clip(freqs, 20, 2000)
        
        # Get the combined pressure from these frequencies using optimized method
        combined_pressure = self.combine_frequency_pressures(freqs)
        
        # Calculate mean squared error - vectorized operation
        error = np.mean((combined_pressure - target_pressure) ** 2)
        return error
        
    def find_optimal_frequencies(self, num_freqs=4, min_freq=20, max_freq=300, iterations=5, initial_freqs=None):
        """Find the optimal set of frequencies with option for hot-starting from previous solutions"""
        # Ensure we have an up-to-date pressure matrix
        if self.pressure_matrix is None:
            print("Pressure matrix not initialized. Generating now...")
            self.generate_pressure_matrix()
            
        if self.targets.target_pressure is None:
            self.targets.create_target_pressure()
            
        best_error = float('inf')
        best_freqs = None
        
        start_time = time.time()
        
        # Try multiple random starting points to avoid local minima
        for i in range(iterations):
            iter_start = time.time()
            
            # Start with provided frequencies (hot-start) or random frequencies
            if initial_freqs is not None and i == 0 and len(initial_freqs) == num_freqs:
                # Use provided frequencies for first iteration
                initial_guess = initial_freqs.copy()
            else:
                # Use random frequencies for other iterations
                initial_guess = np.random.uniform(min_freq, max_freq, num_freqs)
        
            # Define bounds for the optimization
            bounds = [(min_freq, max_freq) for _ in range(num_freqs)]
            
            # Run the optimization
            result = minimize(
                lambda x: self.pressure_error_function(x, self.targets.target_pressure),
                initial_guess,
                bounds=bounds,
                method='L-BFGS-B'
            )
            
            sorted_freqs = np.sort(result.x)
            
            if result.fun < best_error:
                best_error = result.fun
                best_freqs = sorted_freqs  # Store sorted frequencies
            
        # Sort the frequencies for consistent reporting
        sorted_freqs = np.sort(best_freqs)

        total_time = time.time() - start_time
        print(f"Found optimal frequencies: {sorted_freqs.round(1)} (error: {best_error:.6f})")
        print(f"Optimization took {total_time*1000:.1f}ms with {iterations} iterations")
        # Store the solution with sorted frequencies
        self.current_solution = {
            'frequencies': sorted_freqs,  # Store sorted frequencies
            'error': best_error,
            'target': self.targets.target_pressure,
            'achieved': self.combine_frequency_pressures(sorted_freqs)
        }
        
        return sorted_freqs
    
    def reset_animation(self):
        """Proxy method to reset animation in target system"""
        return self.targets.reset()
    
    """Proxy method to access target system's optimize_and_apply"""
    def optimize_and_apply(self, profile="gaussian", num_freqs=4, animated=False):
        # Convenience methods to access target functionality
        return self.targets.optimize_and_apply(profile, num_freqs, animated)