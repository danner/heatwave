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
        self.freq_resolution = 2     # Frequency resolution (Hz)
        self.position_count = 0      # Number of positions in the matrix
        
    def generate_pressure_matrix(self):
        """Pre-calculate pressure matrix for all frequencies and positions"""
        print("Generating pressure matrix...")
        start_time = time.time()
        
        # Create frequency range with the configured resolution
        freq_count = int((self.max_freq - self.min_freq) / self.freq_resolution) + 1
        self.freq_range = np.linspace(self.min_freq, self.max_freq, freq_count)
        
        # Get positions from the algorithm
        positions = self.algorithm.positions
        self.position_count = len(positions)
        
        # Vectorized calculation of pressure matrix
        self.pressure_matrix = self.calculate_t_network_pressures(self.freq_range, positions)
    
        # Report on matrix size and generation time
        matrix_size_mb = self.pressure_matrix.nbytes / (1024 * 1024)
        elapsed_time = time.time() - start_time
        print(f"Pressure matrix generated: {len(self.freq_range)}x{self.position_count} ({matrix_size_mb:.1f} MB)")
        print(f"Generation took {elapsed_time:.2f} seconds")
        
    def get_pressure_from_matrix(self, frequency, position_index):
        """Get pressure value from pre-calculated matrix using optimized interpolation"""
        # Approximate match using searchsorted
        idx = np.searchsorted(self.freq_range, frequency)
        if idx < len(self.freq_range) and abs(self.freq_range[idx] - frequency) < 1e-6:
            return self.pressure_matrix[idx, position_index]
            
        # Faster bounds check
        if frequency <= self.min_freq:
            return self.pressure_matrix[0, position_index]
        elif frequency >= self.max_freq:
            return self.pressure_matrix[-1, position_index]
        
        # Interpolation
        freq_idx_low = max(0, idx - 1)
        freq_idx_high = min(idx, len(self.freq_range) - 1)
        freq_low = self.freq_range[freq_idx_low]
        freq_high = self.freq_range[freq_idx_high]
        pressure_low = self.pressure_matrix[freq_idx_low, position_index]
        pressure_high = self.pressure_matrix[freq_idx_high, position_index]
        
        # Guard against tiny denominators
        denom = freq_high - freq_low
        t = (frequency - freq_low) / denom if abs(denom) > 1e-8 else 0
        return pressure_low + t * (pressure_high - pressure_low)
        
    def calculate_t_network_pressures(self, frequencies, positions):
        """Calculate pressure distribution using T-network model (vectorized)"""
        # Get physics parameters from the algorithm
        speed_of_sound = self.algorithm.speed_of_sound
        tube_length = self.algorithm.tube_length
        damping_coefficient = self.algorithm.damping_coefficient
        reflection_count = self.algorithm.reflection_count
        q_factor = self.algorithm.q_factor
        
        # Convert angular frequencies and wave numbers
        omegas = 2 * np.pi * frequencies[:, np.newaxis]  # Shape (F, 1)
        k = omegas / speed_of_sound  # Shape (F, 1)
        
        # Vectorized positions
        x_vec = positions[np.newaxis, :]  # Shape (1, P)
        
        # Incident wave traveling right
        incident = np.cos(k * x_vec) * np.exp(-damping_coefficient * x_vec / q_factor)
        
        # Reflections
        pressures = incident.copy()
        for r in range(1, reflection_count + 1):
            path_lengths = (2 * r * tube_length - x_vec) if r % 2 == 1 else (2 * r * tube_length + x_vec)
            reflected_wave = np.cos(k * path_lengths) * np.exp(-damping_coefficient * path_lengths / q_factor)
            pressures += reflected_wave
        
        # Return pressures without taking absolute value (preserve phase)
        return pressures
    
    def combine_frequency_pressures(self, frequencies, amplitudes=None):
        """Combine pressure distributions from multiple frequencies using the matrix"""
        if amplitudes is None:
            amplitudes = np.ones(len(frequencies))
            
        # Check if we have a valid pressure matrix
        if self.pressure_matrix is None:
            # Fall back to direct calculation if matrix is not available
            pressures = self.calculate_t_network_pressures(frequencies, self.algorithm.positions)
            combined = np.sum(pressures * amplitudes[:, np.newaxis], axis=0)
        else:
            # Use pre-calculated matrix
            indices = np.searchsorted(self.freq_range, frequencies)
            valid_indices = (indices >= 0) & (indices < len(self.freq_range))
            indices = indices[valid_indices]
            amplitudes = np.array(amplitudes)[valid_indices]
            
            # Slice the matrix and combine
            selected_pressures = self.pressure_matrix[indices, :]
            combined = np.sum(selected_pressures * amplitudes[:, np.newaxis], axis=0)
        
        # Normalize combined pressure
        max_pressure = np.max(np.abs(combined))
        if max_pressure > 0:
            combined /= max_pressure
                
        return combined
