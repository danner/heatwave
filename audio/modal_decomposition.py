import numpy as np
from scipy import linalg

class ModalDecomposition:
    """Implements modal decomposition approach for pressure patterns"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
    
    def decompose_target(self, target_pressure, num_modes=10, lambda_reg=1e-6):
        """Decompose target pressure into modes using the physics model"""
        if target_pressure is None or len(target_pressure) == 0:
            return None, None
        
        # Get positions array
        positions = self.algorithm.positions
        tube_length = self.algorithm.tube_length
        speed_of_sound = self.algorithm.speed_of_sound
        
        # Create response matrix P
        P = np.zeros((len(positions), num_modes))
        frequencies = []
        
        # For each mode, calculate the expected pressure response
        for n in range(num_modes):
            # Calculate frequency for this mode (odd quarter-waves)
            # f_n = (2n-1) * c / 4L where n=1,2,3,...
            freq = (2*n+1) * speed_of_sound / (4*tube_length)
            frequencies.append(freq)
            
            # Calculate pressure distribution for this frequency
            pressure = self.algorithm.calculate_t_network_pressures(freq, positions)
            # Normalize the pressure
            if np.max(np.abs(pressure)) > 0:
                pressure = pressure / np.max(np.abs(pressure))
            
            # Store in response matrix
            P[:, n] = pressure
            
        # Solve the linear system with regularization
        # Minimize ||P*A - target||² + lambda*||A||²
        PTP = P.T @ P + lambda_reg * np.eye(num_modes)
        PTg = P.T @ target_pressure
        
        try:
            # Solve for amplitudes
            amplitudes = linalg.solve(PTP, PTg)
            
            # Clip to avoid extreme values
            amplitudes = np.clip(amplitudes, 0, 1.0)
            
            # Return the frequencies and their corresponding amplitudes
            return frequencies, amplitudes
        except np.linalg.LinAlgError:
            print("Matrix singular, using fallback method")
            return None, None