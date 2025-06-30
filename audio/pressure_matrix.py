import numpy as np
import time

class PressureMatrixGenerator:
    """Class for generating and managing pressure matrices based on T-network model"""
    
    def __init__(self, algorithm):
        """Initialize with a reference to the parent algorithm"""
        self.algorithm = algorithm
        
        # Matrix parameters
        self.pressure_matrix = None  # Will store pre-calculated pressures
        self.freq_range = None       # Will store frequencies used in matrix
        self.min_freq = 20           # Minimum frequency for matrix (Hz)
        self.max_freq = 500          # Maximum frequency for matrix (Hz)
        self.freq_resolution = 1     # Frequency resolution (Hz)
        self.position_count = 0      # Number of positions in the matrix
        
    def generate_pressure_matrix(self):
        """Pre-calculate pressure matrix for all frequencies and positions"""
        print("Generating pressure matrix...")
        start_time = time.time()
        
        # Use an efficient frequency resolution for the matrix
        self.freq_resolution = 2
        
        # Create frequency range with optimized resolution
        freq_count = int((self.max_freq - self.min_freq) / self.freq_resolution) + 1
        self.freq_range = np.linspace(self.min_freq, self.max_freq, freq_count)
        
        # Get positions from the algorithm
        positions = self.algorithm.positions
        self.position_count = len(positions)
        
        # Initialize pressure matrix with dimensions [freq_count, position_count]
        self.pressure_matrix = np.zeros((len(self.freq_range), self.position_count))
        
        # Calculate pressure for each frequency at each position
        for i, freq in enumerate(self.freq_range):
            # Calculate pressure distribution for this frequency
            pressures = self.calculate_t_network_pressures(freq, positions)
            
            # Store in matrix
            self.pressure_matrix[i, :] = pressures
    
        # Report on matrix size and generation time
        matrix_size_mb = self.pressure_matrix.nbytes / (1024 * 1024)
        elapsed_time = time.time() - start_time
        print(f"Pressure matrix generated: {len(self.freq_range)}x{self.position_count} ({matrix_size_mb:.1f} MB)")
        print(f"Generation took {elapsed_time:.2f} seconds")
        
    def get_pressure_from_matrix(self, frequency, position_index):
        """Get pressure value from pre-calculated matrix using optimized interpolation"""
        # Direct lookup for exact matches to avoid interpolation overhead
        if frequency in self.freq_range:
            freq_idx = np.where(self.freq_range == frequency)[0][0]
            return self.pressure_matrix[freq_idx, position_index]
            
        # Faster bounds check
        if frequency <= self.min_freq:
            return self.pressure_matrix[0, position_index]
        elif frequency >= self.max_freq:
            return self.pressure_matrix[-1, position_index]
        
        # Optimized index calculation using numpy
        freq_idx_low = int((frequency - self.min_freq) / self.freq_resolution)
        freq_idx_high = min(freq_idx_low + 1, len(self.freq_range) - 1)
        
        # Get frequencies and pressures for interpolation
        freq_low = self.freq_range[freq_idx_low]
        freq_high = self.freq_range[freq_idx_high]
        pressure_low = self.pressure_matrix[freq_idx_low, position_index]
        pressure_high = self.pressure_matrix[freq_idx_high, position_index]
        
        # Linear interpolation
        t = (frequency - freq_low) / (freq_high - freq_low) if freq_high > freq_low else 0
        return pressure_low + t * (pressure_high - pressure_low)
        
    def calculate_t_network_pressures(self, frequency, positions):
        """Calculate pressure distribution using T-network model"""
        # Get physics parameters from the algorithm
        speed_of_sound = self.algorithm.speed_of_sound
        tube_length = self.algorithm.tube_length
        damping_coefficient = self.algorithm.damping_coefficient
        hole_size = self.algorithm.hole_size
        reflection_count = self.algorithm.reflection_count
        q_factor = self.algorithm.q_factor
        density = self.algorithm.density
        hole_impedance_factor = self.algorithm.hole_impedance_factor
        
        # Convert angular frequency
        omega = 2 * np.pi * frequency
        
        # Calculate wave number (k = ω/c)
        k = omega / speed_of_sound
        
        # Calculate base acoustic impedance (Z₀)
        z0 = density * speed_of_sound
        
        # Array to store calculated pressures at each position
        pressures = np.zeros(len(positions))
        
        # Both ends are closed (reflection coefficient = +1)
        left_end_reflection = 1.0   # Closed end at x=0
        right_end_reflection = 1.0  # Closed end at x=L
        
        # Calculate Q-weighted damping coefficient - lower damping = sharper resonances
        effective_damping = damping_coefficient / q_factor
        
        # Calculate for each position considering multiple reflections
        for i, x in enumerate(positions):
            # Incident wave traveling right (initial wave)
            incident_wave = np.cos(k * x)
            
            # Add initial incident wave with position-based damping
            damping_factor = np.exp(-effective_damping * x)
            pressures[i] += incident_wave * damping_factor
            
            # First reflection - more strongly weighted to enhance standing wave formation
            if reflection_count >= 1:
                first_reflection_path = 2 * tube_length - x
                first_reflection_damping = np.exp(-effective_damping * first_reflection_path)
                first_reflected_wave = right_end_reflection * np.cos(k * first_reflection_path)
                pressures[i] += first_reflected_wave * first_reflection_damping
            
            # Add remaining reflections with uniform physical properties
            for r in range(2, reflection_count + 1):
                reflected_phase = 1
                reflection_path = 0
                
                if r % 2 == 1:
                    # Odd reflections (right end first)
                    reflected_phase = right_end_reflection
                    reflection_path = r * tube_length - x
                else:
                    # Even reflections (left end after right end)
                    reflected_phase = right_end_reflection * left_end_reflection
                    reflection_path = r * tube_length + x
                
                # Apply damping based on path length
                reflection_damping = np.exp(-effective_damping * reflection_path)
                
                # Add this reflection to the total pressure
                reflected_wave = reflected_phase * np.cos(k * reflection_path)
                pressures[i] += reflected_wave * reflection_damping
            
            # Apply standing wave interference effects - this naturally enhances resonant frequencies
            if reflection_count > 2:
                # Standing wave factor naturally enhances resonances without targeting frequencies
                standing_wave_factor = 1.0 + 0.3 * np.abs(np.sin(k * tube_length)) * (reflection_count / 5)
                pressures[i] *= standing_wave_factor
            
            # Apply hole effects from T-network model
            if hole_size > 0:
                # Calculate impedance effects from the holes
                hole_impedance = z0 * k * (hole_size / 2) * (1 + hole_impedance_factor)
                impedance_effect = (z0 / hole_impedance) * 0.3
                pressures[i] *= (1 + impedance_effect * np.sin(k * x))
            
            # Take absolute value for magnitude
            pressures[i] = np.abs(pressures[i])
        
        return pressures
    
    def combine_frequency_pressures(self, frequencies, amplitudes=None):
        """Combine pressure distributions from multiple frequencies using the matrix"""
        if amplitudes is None:
            amplitudes = np.ones(len(frequencies))
            
        # Initialize combined pressure
        positions = self.algorithm.positions
        combined = np.zeros(len(positions))
        
        # Check if we have a valid pressure matrix
        if self.pressure_matrix is None:
            # Fall back to direct calculation if matrix is not available
            for i, freq in enumerate(frequencies):
                if i < len(amplitudes):
                    pressure = self.calculate_t_network_pressures(freq, positions)
                    combined += amplitudes[i] * pressure
        else:
            # Use pre-calculated matrix with vectorized operations
            amplitudes_array = np.array(amplitudes[:len(frequencies)])
            
            # Create an array to store all pressure contributions
            all_pressures = np.zeros((len(frequencies), len(positions)))
            
            # Calculate all pressures at once for each frequency
            for i, freq in enumerate(frequencies):
                if i < len(amplitudes):
                    # Get pressure for this frequency at all positions
                    for pos_idx in range(len(positions)):
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
