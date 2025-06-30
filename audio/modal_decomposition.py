import numpy as np
from scipy import linalg
import time

class ModalDecomposition:
    """Implements modal decomposition approach for pressure patterns"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        # Cache for response matrices and factorizations
        self._response_matrix_cache = {}  # Cache for the response matrix P
        self._factorization_cache = {}    # Cache for matrix factorizations
    
    def _get_cache_key(self, num_modes):
        """Generate a cache key based on physical parameters"""
        # Include all physical parameters that affect the response matrix
        return (
            self.algorithm.tube_length,
            self.algorithm.speed_of_sound,
            self.algorithm.damping_coefficient,
            self.algorithm.reflection_count,
            self.algorithm.q_factor,
            tuple(self.algorithm.positions),  # Convert to tuple to make it hashable
            num_modes
        )
    
    def decompose_target(self, target_pressure, num_modes=10, lambda_reg=1e-6):
        """Decompose target pressure into modes using the physics model"""
        if target_pressure is None or len(target_pressure) == 0:
            return None, None
            
        start_time = time.time()
        
        # Get positions array
        positions = self.algorithm.positions
        tube_length = self.algorithm.tube_length
        speed_of_sound = self.algorithm.speed_of_sound
        
        # Check cache for response matrix P
        cache_key = self._get_cache_key(num_modes)
        
        if cache_key in self._response_matrix_cache:
            # Use cached response matrix
            P, frequencies = self._response_matrix_cache[cache_key]
            print(f"Using cached response matrix for {num_modes} modes")
        else:
            # Calculate new response matrix
            print(f"Building new response matrix for {num_modes} modes")
            
            # Calculate frequencies for all modes at once
            frequencies = [(2 * n + 1) * speed_of_sound / (4 * tube_length) for n in range(num_modes)]
            frequencies = np.array(frequencies)  # Convert to NumPy array
            
            # Calculate pressure matrix for all frequencies at once
            pressure_matrix = self.algorithm.pressure_matrix.calculate_t_network_pressures(frequencies, positions)
            
            # CRITICAL FIX: Transpose the matrix to get shape (P, F) instead of (F, P)
            pressure_matrix = pressure_matrix.T
            
            # Normalize each column of the pressure matrix
            max_abs_values = np.max(np.abs(pressure_matrix), axis=0)
            P = np.divide(
                pressure_matrix,
                max_abs_values,
                out=np.zeros_like(pressure_matrix),
                where=max_abs_values > 0
            )
            
            # Cache the response matrix
            self._response_matrix_cache[cache_key] = (P, frequencies)
        
        # Solve the linear system with regularization
        # Cache PTP and its factorization separately since target changes more often than P
        if cache_key in self._factorization_cache:
            print("Using cached matrix factorization")
            PTP, cholesky_factor = self._factorization_cache[cache_key]
            # Only calculate P^T @ target_pressure (much cheaper than reforming PTP)
            PTg = P.T @ target_pressure
            
            try:
                # Solve using cached factorization (fast back-substitution)
                amplitudes = linalg.cho_solve(cholesky_factor, PTg)
            except np.linalg.LinAlgError:
                # If cached factorization fails, recompute
                print("Cached factorization failed, computing new one")
                try:
                    PTP = P.T @ P + lambda_reg * np.eye(num_modes)
                    cholesky_factor = linalg.cho_factor(PTP)
                    self._factorization_cache[cache_key] = (PTP, cholesky_factor)
                    amplitudes = linalg.cho_solve(cholesky_factor, PTg)
                except np.linalg.LinAlgError:
                    # Fall back to direct solve if Cholesky fails
                    print("Cholesky factorization failed, using direct solve")
                    try:
                        amplitudes = linalg.solve(PTP, PTg)
                    except:
                        print("Matrix singular, using fallback method")
                        return None, None
        else:
            # No cached factorization, compute new one
            # Form P^T @ P once and cache both it and its factorization
            PTP = P.T @ P + lambda_reg * np.eye(num_modes)
            PTg = P.T @ target_pressure
            
            try:
                # Try Cholesky factorization (faster for symmetric positive definite matrices)
                cholesky_factor = linalg.cho_factor(PTP)
                self._factorization_cache[cache_key] = (PTP, cholesky_factor)
                amplitudes = linalg.cho_solve(cholesky_factor, PTg)
            except np.linalg.LinAlgError:
                # Fall back to direct solve if Cholesky fails
                print("Cholesky factorization failed, using direct solve")
                try:
                    amplitudes = linalg.solve(PTP, PTg)
                except:
                    print("Matrix singular, using fallback method")
                    return None, None
        
        # Clip to avoid extreme values
        amplitudes = np.clip(amplitudes, 0, 1.0)
        
        # Report performance
        elapsed = time.time() - start_time
        print(f"Modal decomposition completed in {elapsed:.3f} seconds")
        
        # Return the frequencies and their corresponding amplitudes
        return frequencies, amplitudes
    
    def clear_cache(self):
        """Clear all cached matrices and factorizations"""
        self._response_matrix_cache.clear()
        self._factorization_cache.clear()
        print("Modal decomposition cache cleared")