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
    
    def apply_to_channels(self, frequencies, amplitudes):
        """Apply the calculated frequencies and amplitudes to synth channels"""
        if frequencies is None or amplitudes is None:
            return False
            
        from state import channels, notify_channel_updated
        
        # Find non-zero amplitudes and their corresponding frequencies
        significant_indices = np.where(np.abs(amplitudes) > 0.01)[0]
        sig_freqs = [frequencies[i] for i in significant_indices]
        sig_amps = [amplitudes[i] for i in significant_indices]
        
        # Sort by amplitude (highest first)
        sorted_indices = np.argsort(sig_amps)[::-1]
        sorted_freqs = [sig_freqs[i] for i in sorted_indices]
        sorted_amps = [sig_amps[i] for i in sorted_indices]
        
        # Apply to channels (limit to 8 channels)
        num_to_apply = min(len(sorted_freqs), 8)
        
        print(f"Applying {num_to_apply} frequencies from modal decomposition:")
        for i in range(num_to_apply):
            freq = sorted_freqs[i]
            amp = sorted_amps[i]
            # Scale amplitude by base volume
            volume = min(1.0, amp * 1.0)  # Scale if needed
            
            print(f"Channel {i}: {freq:.1f}Hz with amplitude {volume:.2f}")
            
            # Update the channel
            channels[i]['frequency'] = float(freq)
            channels[i]['mute'] = False
            channels[i]['volume'] = float(volume)
            notify_channel_updated(i)
            
        # Mute any unused channels
        for i in range(num_to_apply, 8):
            channels[i]['mute'] = True
            notify_channel_updated(i)
            
        return True
