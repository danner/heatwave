import numpy as np
import time
import gevent

class PressureTargetSystem:
    """Class for managing target pressure distributions and animations"""
    
    def __init__(self, algorithm):
        # Store reference to parent algorithm
        self.algorithm = algorithm
        
        # Target pressure parameters
        self.target_pressure = None
        self.positions = None
        
        # Pre-processed targets storage
        self.targets = []        # List of pre-processed target distributions
        self.target_count = 8    # Number of targets to pre-process
        self.current_index = 0   # Current target index
        
        # Animation parameters
        self.active = False
        self.time = 0.0
        self.duration = 30.0  
        self.last_target_change_time = 0
        self.profile = "gaussian"
        self.width = 0.2
        self.direction = 1  # 1 for up, -1 for down
        
        # Target change tracking
        self.last_target_index = -1
        self.optimization_greenlet = None
        self.optimization_running = False
    
    def update_positions(self, positions):
        """Update the positions array used for target pressure"""
        self.positions = positions
        # Pre-process targets when positions are set
        if self.positions is not None:
            self.pre_process_targets()
    
    def pre_process_targets(self):
        """Pre-process target distributions across the tube"""
        if self.positions is None:
            return
            
        print(f"\n=== Pre-processing {self.target_count} Target Pressure Profiles ===")
        self.targets = []
        
        # Create evenly distributed centers across the tube
        centers = np.linspace(0.1, 0.9, self.target_count)
        
        # Generate a target for each center position
        for i, center in enumerate(centers):
            print(f"Generating target {i+1}/{self.target_count} at position {center:.2f}")
            
            # Create normalized positions
            norm_positions = self.positions / self.algorithm.tube_length
            
            # Create Gaussian distribution centered at the specified position
            target = np.exp(-((norm_positions - center) ** 2) / (2 * self.width ** 2))
            
            # Normalize to [0,1]
            if np.max(target) > 0:
                target = target / np.max(target)
                
            self.targets.append(target)
            
        print(f"Pre-processed {len(self.targets)} targets successfully")
        
    def create_target_pressure(self, profile="gaussian", center=0.5, width=0.2):
        """Create a static target pressure distribution with the specified profile"""
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
        if not self.targets:
            return 0.5  # Default center if no targets
            
        # Calculate which target to use
        total_positions = self.target_count * 2 - 2  # Forward then backward (without repeating end positions)
        cycle_duration = self.duration
        
        # Normalize time to [0, 1] over the cycle
        cycle_position = (elapsed_time % cycle_duration) / cycle_duration
        
        # Scale to target range
        target_position = cycle_position * total_positions
        
        # Convert to index
        if target_position < self.target_count:
            # Forward direction (0 to target_count-1)
            self.current_index = int(target_position)
            self.direction = 1
        else:
            # Reverse direction (target_count-2 down to 1)
            self.current_index = int(total_positions - target_position)
            self.direction = -1
            
        # Calculate normalized center position for display
        center = (self.current_index + 0.5) / self.target_count
        return center
    
    def create_animated_target_pressure(self, elapsed_time):
        """Get the appropriate pre-processed target based on time"""
        if not self.targets:
            # Create targets if they don't exist yet
            self.pre_process_targets()
            if not self.targets:
                return None
            
        # Get current target index based on time
        _ = self.get_current_center_position(elapsed_time)  # Updates self.current_index
        
        # Use the pre-processed target
        self.target_pressure = self.targets[self.current_index]
        return self.target_pressure
    
    def start_animation(self):
        """Start the animation system"""
        print("\n=== Pressure Animation Starting ===")
        print(f"Profile: {self.profile}")
        print(f"Using {self.target_count} pre-processed targets")
        print(f"Duration: {self.duration}s per cycle")
        
        # Make sure targets are pre-processed
        if not self.targets:
            self.pre_process_targets()
        
        self.active = True
        self.time = 0
        self.last_target_change_time = 0
        self.last_target_index = -1
        
        # Start the monitoring greenlet
        if not self.optimization_running:
            print("Starting target monitoring process...")
            self.optimization_running = True
            self.optimization_greenlet = gevent.spawn(self.target_monitor_loop)
        else:
            print("Target monitoring already running")
            
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
        self.last_target_change_time = 0
        self.current_index = 0
        self.direction = 1
        self.last_target_index = -1
    
    def target_monitor_loop(self):
        """Monitor for target changes and notify algorithm"""
        print("DEBUG: Starting target monitor greenlet with pre-processed targets")
        
        last_print_time = time.time()
        
        while self.optimization_running and self.active:
            # Get current target index
            _ = self.get_current_center_position(self.time)  # Updates self.current_index
            current_index = self.current_index
            
            # Check if the target has changed
            if current_index != self.last_target_index:
                # Get the current target pressure
                self.create_animated_target_pressure(self.time)
                
                # Log target change (with rate limiting)
                current_time = time.time()
                if current_time - last_print_time > 1.0:
                    direction_text = "⬆️" if self.direction > 0 else "⬇️"
                    center = (current_index + 0.5) / self.target_count
                    print(f"\n--- Target changed to #{current_index+1} at position {center:.2f} {direction_text} ---")
                    last_print_time = current_time
                
                # Notify algorithm about the target change
                self.algorithm.on_target_changed(self.target_pressure)
                
                # Update tracking variable
                self.last_target_index = current_index
                self.last_target_change_time = self.time
            
            # Sleep to reduce CPU usage
            gevent.sleep(0.5)