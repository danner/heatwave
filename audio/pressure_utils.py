import numpy as np

def calculate_pressure_vector(precalc_omegas, precalc_envelope, precalc_position_weights, output, frames, start_time, rate, time_step_vector, last_frame_size):
    """
    Precalculate pressure for all samples in a frame
    Uses full NumPy broadcasting to eliminate Python loops
    """
    if len(precalc_omegas) == 0:
        return output
        
    # Check if we need to create or resize the precalculated time step vector
    if time_step_vector is None or frames != last_frame_size:
        # Create time step vector (constant steps, to be reused)
        time_step = 1.0 / rate
        time_step_vector = np.arange(frames) * time_step
        last_frame_size = frames

    # Create time vector for this frame by adding current start time
    # This avoids reallocating a new array on each callback
    time_vector = time_step_vector + start_time

    # ULTRA-OPTIMIZED VECTORIZED IMPLEMENTATION:
    
    # 1. Calculate sin term: shape (F, frames)
    #    Broadcasting: (F,1) * (frames,) -> (F, frames)
    sin_term = np.sin(precalc_omegas * time_vector)
    
    # 2. Reshape sin_term for broadcasting with positions: shape (F, 1, frames)
    sin_term = sin_term[:, np.newaxis, :]
    
    # 3. Reshape precalculated envelope for broadcasting: shape (F, P, 1)
    envelope = precalc_envelope[:, :, np.newaxis]
    
    # 4. Calculate contribution with single operation: shape (F, P, frames)
    #    Broadcasting: (F,P,1) * (F,1,frames) -> (F,P,frames)
    contribution = envelope * sin_term
    
    # 5. Apply position weights and sum over all frequencies and positions
    # FIX: Replace tensordot with manual weighted sum to ensure correct output shape
    weighted_contribution = contribution * precalc_position_weights[np.newaxis, :, np.newaxis]
    output[:] = np.sum(np.sum(weighted_contribution, axis=0), axis=0)
    
    return output

def update_precalculated_values(frequencies, speed_of_sound, damping_coefficient, tube_length, positions, amplitudes):
    """
    Precalculate values that don't change between audio frames
    """
    if len(frequencies) == 0:
        return None, None, None, None, None, None

    # Get frequency array and number of positions
    num_freqs = len(frequencies)
    freqs = np.array(frequencies)

    # Calculate all values using vectorized operations
    # Angular frequencies and wave numbers
    precalc_omegas = 2 * np.pi * freqs
    precalc_wave_numbers = precalc_omegas / speed_of_sound

    # FIXED: Reshape arrays for proper broadcasting
    # Create position matrix: shape (1, P)
    position_matrix = np.array(positions).reshape(1, -1)
    
    # Reshape wave numbers to (F, 1) for proper broadcasting with positions
    wave_numbers_matrix = precalc_wave_numbers.reshape(-1, 1)
    
    # Calculate position components using broadcasting: shape (F, P)
    # Broadcasting: (F,1) * (1,P) -> (F,P)
    precalc_position_components = np.cos(wave_numbers_matrix * position_matrix)

    # Create frequency matrix: shape (F, 1)
    freq_matrix = freqs.reshape(-1, 1)

    # Define reference frequency (replace magic constant 110)
    reference_freq = speed_of_sound / (4 * tube_length)  # Fundamental frequency

    # Calculate damping factors using broadcasting: shape (F, P)
    damping_term = damping_coefficient * position_matrix
    freq_term = freq_matrix / reference_freq  # Normalize by fundamental

    # Calculate full damping matrix: shape (F, P)
    precalc_damping_factors = np.exp(-damping_term * freq_term)

    # Reshape arrays for optimized broadcasting
    # omegas: shape (F,1) for broadcasting with time
    precalc_omegas = precalc_omegas.reshape(-1, 1)
    
    # Create amplitude array ready for broadcasting: shape (F, 1)
    precalc_amplitudes = np.array(amplitudes[:num_freqs]).reshape(-1, 1)
    
    # Pre-calculate amplitude * position_component * damping for each (freq, pos)
    precalc_envelope = precalc_amplitudes * precalc_position_components * precalc_damping_factors
    
    # Position weights: shape (P,) for final reduction
    precalc_position_weights = np.ones(len(positions)) / len(positions)

    return precalc_omegas, precalc_envelope, precalc_position_weights, precalc_wave_numbers, precalc_position_components, precalc_damping_factors
