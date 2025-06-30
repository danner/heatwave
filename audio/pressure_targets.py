import numpy as np
import time
import gevent
from state import notify_channel_updated

class PressureTargetSystem:
    """Class for managing target pressure distributions and animations"""
    
    def __init__(self, algorithm):
        # Store reference to parent algorithm
        self.algorithm = algorithm
        
        # Target pressure parameters
        self.target_pressure = None
        self.positions = None
        
        # Animation parameters
        self.active = False
        self.time = 0.0
        self.duration = 30.0  # 10 seconds for full animation (one way)
        self.last_optimization_time = 0
        self.optimization_interval = 1.0
        self.profile = "gaussian"
        self.width = 0.2
        self.direction = 1  # 1 for up, -1 for down
        
        # Optimization control
        self.optimization_greenlet = None
        self.optimization_running = False
        self.current_solution = None
        
        # CPU usage control
        self.last_center_position = 0
        self.position_threshold = 0.2  # Trigger new optimization after 20% movement
        self.last_optimization_duration = 0
        self.max_cpu_percent = 0.3  # Maximum fraction of time to spend optimizing
        
    def update_positions(self, positions):
        """Update the positions array used for target pressure"""
        self.positions = positions
        
    def create_target_pressure(self, profile="gaussian", center=0.5, width=0.2):
        """Create a target pressure distribution with the specified profile"""
        if self.positions is None:
            return None
    
        print(f"\n=== Creating Target Pressure Profile ===")
        print(f"Profile type: {profile}")
        print(f"Center: {center}, Width: {width}")
        print(f"Position range: 0 to {self.algorithm.tube_length}m ({len(self.positions)} points)")
            
        # Normalize positions to [0,1] for easier math
        norm_positions = self.positions / self.algorithm.tube_length
        
        # Create target pressure based on selected profile
        if profile == "gaussian":
            # Gaussian distribution centered at specified position
            self.target_pressure = np.exp(-((norm_positions - center) ** 2) / (2 * width ** 2))
        elif profile == "sine":
            # Sine wave distribution
            self.target_pressure = 0.5 + 0.5 * np.sin(2 * np.pi * norm_positions)
        elif profile == "square":
            # Square wave / band distribution
            left_edge = center - width/2
            right_edge = center + width/2
            self.target_pressure = np.where(
                (norm_positions >= left_edge) & (norm_positions <= right_edge),
                1.0, 0.0)
        elif profile == "bimodal":
            # Bimodal distribution (two peaks)
            peak1 = 0.3
            peak2 = 0.7
            width1 = 0.15
            width2 = 0.15
            g1 = np.exp(-((norm_positions - peak1) ** 2) / (2 * width1 ** 2))
            g2 = np.exp(-((norm_positions - peak2) ** 2) / (2 * width2 ** 2))
            self.target_pressure = g1 + g2
            # Normalize to [0,1]
            self.target_pressure = self.target_pressure / np.max(self.target_pressure)
        else:
            # Default to uniform distribution
            self.target_pressure = np.ones_like(self.positions)
            
        print(f"Target created with max pressure: {np.max(self.target_pressure):.2f}")
        return self.target_pressure
        
    def get_current_center_position(self, elapsed_time):
        """Get the current center position based on animation time"""
        cycle_position = (elapsed_time % (2 * self.duration)) / self.duration
        
        # For the second half of the cycle, go backwards
        if cycle_position > 1.0:
            center = 2.0 - cycle_position
            self.direction = -1
        else:
            center = cycle_position
            self.direction = 1
            
        return center
    
    def create_animated_target_pressure(self, elapsed_time):
        """Create a time-varying target pressure distribution with oscillating motion"""
        if self.positions is None:
            return None
            
        # Get the center position
        center = self.get_current_center_position(elapsed_time)
        
        # Create target pressure based on selected profile with animated center
        if self.profile == "gaussian":
            # Normalize positions to [0,1] for easier math
            norm_positions = self.positions / self.algorithm.tube_length
            # Gaussian distribution centered at time-varying position
            self.target_pressure = np.exp(-((norm_positions - center) ** 2) / (2 * self.width ** 2))
            # Normalize to [0,1]
            if np.max(self.target_pressure) > 0:
                self.target_pressure = self.target_pressure / np.max(self.target_pressure)
        
        return self.target_pressure
    
    def start_animation(self):
        """Start the animation system"""
        print("\n=== Pressure Animation Starting ===")
        print(f"Profile: {self.profile}")
        print(f"Duration: {self.duration}s per cycle")
        print(f"Optimization interval: {self.optimization_interval}s")
        print(f"Position threshold: {self.position_threshold}")
        
        self.active = True
        self.time = 0
        self.last_optimization_time = 0
        self.last_center_position = 0
        
        # Start the optimization greenlet
        if not self.optimization_running:
            print("Starting optimization process for animated targets...")
            self.optimization_running = True
            self.optimization_greenlet = gevent.spawn(self.optimization_loop)
        else:
            print("Optimization greenlet already running")
            
    def stop_animation(self):
        """Stop the animation system"""
        self.optimization_running = False
        if self.optimization_greenlet:
            try:
                self.optimization_greenlet.kill(block=False)
            except:
                pass
            self.optimization_greenlet = None
        self.reset()
        
    def reset(self):
        """Reset the animation state"""
        self.active = False
        self.time = 0
        self.last_optimization_time = 0
        self.last_center_position = 0
        self.direction = 1
    
    def optimization_loop(self):
        """Run optimization in a gevent greenlet to avoid audio interruptions"""
        print("DEBUG: Starting optimization greenlet")
        
        # Check if we have frequencies at the start
        if hasattr(self.algorithm, 'frequencies'):
            print(f"DEBUG: Starting with {len(self.algorithm.frequencies)} active frequencies")
            if len(self.algorithm.frequencies) > 0:
                print(f"DEBUG: Initial frequencies: {[round(f, 1) for f in self.algorithm.frequencies]}")
        else:
            print("DEBUG: WARNING - algorithm has no frequencies attribute!")
            
        # Keep track of previous optimal frequencies for hot-starting
        previous_optimal_freqs = None
        consecutive_skips = 0  # Track how many optimizations we've skipped in a row
        max_consecutive_skips = 2  # Don't allow more than this many skips in a row
        last_print_time = time.time()
        optimization_count = 0
        
        while self.optimization_running and self.active:
            # Calculate current center position
            elapsed_time = self.time
            
            # Get current position
            center = self.get_current_center_position(elapsed_time)
            
            # Only optimize if the position has changed enough
            position_diff = abs(center - self.last_center_position)
            time_since_last = elapsed_time - self.last_optimization_time
            
            # Run optimization if position changed significantly OR enough time has passed
            if position_diff >= self.position_threshold or time_since_last >= self.optimization_interval:
                optimization_count += 1
                print(f"\nDEBUG: Optimization #{optimization_count} at position {center:.2f} (diff={position_diff:.2f})")
                
                # Limit logging frequency
                current_time = time.time()
                if current_time - last_print_time > 1.0:  # Only log once per second
                    direction_text = "⬆️" if self.direction > 0 else "⬇️"
                    print(f"\n--- Optimizing for position {center:.2f} {direction_text} (moved {position_diff:.2f}) ---")
                    last_print_time = current_time
                
                # Determine if we should run optimization based on previous duration and skip count
                should_optimize = True
                if self.last_optimization_duration >= self.optimization_interval * self.max_cpu_percent:
                    if consecutive_skips < max_consecutive_skips:
                        print(f"Previous optimization was slow ({self.last_optimization_duration*1000:.1f}ms), but ensuring we don't skip too many steps")
                        consecutive_skips += 1
                        # Use reduced complexity for this optimization to catch up
                        iterations = 2
                        num_freqs = 2
                    else:
                        print(f"Skipping optimization at {center:.2f} to preserve audio quality")
                        should_optimize = False
                else:
                    # Previous optimization was fast enough, reset consecutive skip counter
                    consecutive_skips = 0
                    iterations = 5
                    num_freqs = 4
                
                if should_optimize:
                    # Generate new target pressure at current position
                    self.create_animated_target_pressure(elapsed_time)
                    
                    # Use modal decomposition to recalculate frequencies
                    try:
                        from .modal_decomposition import ModalDecomposition
                        modal = ModalDecomposition(self.algorithm)
                        
                        start_time = time.time()
                        frequencies, amplitudes = modal.decompose_target(self.target_pressure, num_modes=num_freqs*3)
                        
                        # Apply the frequencies if decomposition succeeded
                        if frequencies is not None and amplitudes is not None:
                            # Update frequencies and amplitudes in algorithm
                            self.algorithm.set_active_frequencies(frequencies, amplitudes)
                            
                            # Store the solution for visualization
                            achieved = self.algorithm.combine_frequency_pressures(frequencies, amplitudes)
                            self.algorithm.current_solution = {
                                'frequencies': frequencies,
                                'amplitudes': amplitudes,
                                'target': self.target_pressure,
                                'achieved': achieved
                            }
                            
                            # Save frequencies for hot-starting
                            previous_optimal_freqs = frequencies.copy()
                    except Exception as e:
                        print(f"Error in optimization: {e}")
                    
                    # Calculate and store optimization duration
                    opt_time = time.time() - start_time
                    self.last_optimization_duration = opt_time
                
                # Always update tracking variables even if we skipped optimization
                self.last_center_position = center
                self.last_optimization_time = elapsed_time
            
            # Increase sleep time to reduce CPU usage
            gevent.sleep(0.75)