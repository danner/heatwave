// Physics parameters and calculations

// Physics parameters
let speedOfSound = 258; // m/s - speed of sound in propane
let tubeLength = 3; // meters
let tubeDiameter = 0.10; // meters (10cm - heatwave tube diameter)
let holeSize = 0.001; // meters (1mm - typical hole diameter)
let propanePressure = 1.1; // Normalized pressure
let baseFrequency = 110; // not used unless server channels are missing
let dampingCoefficient = 0.05; // Damping coefficient per meter
const externalPressure = 1.0; // Normalized external pressure
let reflections = 5; // Default number of reflections

// Constants for T-network model
const SPECIFIC_HEAT_RATIO = 1.4;  // γ (gamma) for propane
const DENSITY_PROPANE = 1.9;     // kg/m³ at room temperature
const HOLE_IMPEDANCE_FACTOR = 0.6; // End correction factor for holes

// Physics data storage
const PRESSURE_AVERAGING_TIME = 0.15;  // seconds of physics time to average over
let pressureTimeHistory = {};  // Store history as {position: [{time, value}]}
let normalizedFlameFactors = []; // Precalculated factors for flames

// Calculate fundamental frequency with end correction
function calculateFundamental() {
    // Calculate the radius
    const radius = tubeDiameter / 2;
    
    // End correction for one open end is approximately 0.6 * radius
    const endCorrection = 0.6 * radius;
    
    // Effective acoustic length is physical length + end correction
    const effectiveLength = tubeLength + endCorrection;
    
    // For a tube with one closed end: f₁ = v/(4*L_effective)
    return speedOfSound / (4 * effectiveLength);
}

// Generate standing wave for a closed-end tube with damping
function generateStandingWave(position, time, reflectionCount = reflections) {
    // Combined wave (sum of all reflections and channels)
    let combinedWave = 0;
    
    // Array to store individual reflection contributions
    let reflectionWaves = Array(reflectionCount).fill(0);

    // Sum the contributions from the active channels
    for (const channelId in channelData) {
        const channel = channelData[channelId];

        // Skip muted channels or channels with zero volume
        if (channel.mute || channel.volume === 0) continue;

        const freq = channel.frequency || baseFrequency;
        const amplitude = channel.volume || 0.5;

        // Calculate wavelength
        const wavelength = speedOfSound / freq;

        // Wave number
        const k = 2 * Math.PI / wavelength;

        // Angular frequency
        const omega = 2 * Math.PI * freq;

        // Add contributions from multiple reflections
        for (let r = 0; r < reflectionCount; r++) {
            const reflectionDamping = Math.exp(-dampingCoefficient * r * tubeLength);
            const reflectionSign = r % 2 === 0 ? 1 : -1; // Alternate phase for reflections

            // Standing wave with damping for this specific reflection
            // Apply position-based damping for all reflections including r=0
            const positionDamping = Math.exp(-dampingCoefficient * position);
            
            const reflectionContribution = amplitude * reflectionDamping * positionDamping * 
                Math.cos(omega * time) * Math.sin(k * (position + r * tubeLength)) * reflectionSign;
            
            // Add to the specific reflection's wave
            reflectionWaves[r] += reflectionContribution;
            
            // Add to combined wave
            combinedWave += reflectionContribution;
        }
    }

    return { 
        combinedWave, 
        reflectionWaves 
    };
}

// Calculate pressure gradient at a specific position
function calculatePressureGradient(waveData, index) {
    // Using central difference method to calculate pressure gradient
    if (index <= 0 || index >= waveData.length - 1) {
        return 0; // Return zero gradient at boundaries
    }
    
    // Calculate position step
    const dx = tubeLength / pointCount;
    
    // Calculate gradient using central difference
    return (waveData[index + 1] - waveData[index - 1]) / (2 * dx);
}

// Function to generate the standing wave envelope with damping
function generateEnvelope(position) {
    let maxWave = 0;
    
    // Find the maximum amplitude at this position from all channels
    for (const channelId in channelData) {
        const channel = channelData[channelId];
        
        // Skip muted channels
        if (channel.mute) continue;
        
        const freq = channel.frequency || baseFrequency;
        const amplitude = channel.volume || 0.5;
        
        // Calculate wavelength
        const wavelength = speedOfSound / freq;
        
        // Wave number
        const k = 2 * Math.PI / wavelength;
        
        // Calculate the amplitude of the standing wave at this position
        // A(x) = A_0 * sin(kx) * e^(-αx)
        const envelopeAmplitude = amplitude * Math.sin(k * position) * 
                                  Math.exp(-dampingCoefficient * position);
        
        // Take the maximum amplitude from all channels
        maxWave = Math.max(maxWave, Math.abs(envelopeAmplitude));
    }
    
    return maxWave;
}

// Calculate the average flow rate over a time window (physics time-based)
function calculateAverageFlowRate(currentFlowRate, position, currentTime) {
    // Initialize history for this position if it doesn't exist
    if (!flowRateTimeHistory[position]) {
        flowRateTimeHistory[position] = [];
    }
    
    const history = flowRateTimeHistory[position];
    
    // Add the current flow rate to the history with the physics timestamp
    history.push({ time: currentTime, value: currentFlowRate });
    
    // Remove entries older than our averaging window based on physics time
    const cutoffTime = currentTime - FLOW_AVERAGING_TIME;
    while (history.length > 0 && history[0].time < cutoffTime) {
        history.shift();
    }
    
    // Calculate the time-weighted average
    let weightedSum = 0;
    let totalWeight = 0;
    
    for (let i = 0; i < history.length; i++) {
        // More recent values get higher weight
        const age = currentTime - history[i].time;
        const weight = 1.0 - (age / FLOW_AVERAGING_TIME);
        
        weightedSum += history[i].value * weight;
        totalWeight += weight;
    }
    
    return totalWeight > 0 ? weightedSum / totalWeight : 0;
}

// Convert flow rates to normalized factors for gas conservation
function normalizeFlowFactors(flowRates) {
    const MIN_FACTOR = 0.125;  // 1/8 of normal height
    const MAX_FACTOR = 4.0;    // 4x normal height
    
    // Calculate the total absolute flow across all flames
    const totalFlow = flowRates.reduce((sum, rate) => sum + Math.abs(rate), 0);
    
    // Check if total flow is too small (near-zero pressure condition)
    const LOW_FLOW_THRESHOLD = 0.001;
    if (totalFlow < LOW_FLOW_THRESHOLD) {
        // Return uniform factors when pressure is too low
        return Array(flowRates.length).fill(1.0);
    }
    
    // Calculate the average flow per flame
    const averageFlow = totalFlow / flowRates.length;
    
    // Normalize each flow rate relative to the total flow
    const oscillationFactors = flowRates.map(rate => {
        // Scale the flow rate relative to the average flow
        let factor = rate / averageFlow;
        
        // Apply a power curve to enhance visual differences
        factor = Math.sign(factor) * Math.pow(Math.abs(factor), 0.8);
        
        // Map the factor to the desired range
        const scaledFactor = 1 + factor; // Center around 1 (default height)
        
        // Clamp the factor to the min and max range
        return Math.max(MIN_FACTOR, Math.min(MAX_FACTOR, scaledFactor));
    });
    
    // Adjust the factors to conserve total gas flow
    const totalFactor = oscillationFactors.reduce((sum, factor) => sum + factor, 0);
    const normalizeRatio = flowRates.length / totalFactor;
    
    // Final normalization with additional clamping to ensure we don't exceed limits
    return oscillationFactors.map(factor => {
        const normalizedFactor = factor * normalizeRatio;
        // Apply final clamping to ensure we don't exceed limits
        return Math.max(MIN_FACTOR, Math.min(MAX_FACTOR, normalizedFactor));
    });
}

// Update physics for flames - simplified to use pressure directly without normalization
function updateFlamePhysics(waveData, flameCount, currentTime) {
    // Get positions for flame holes
    const holePositions = Array.from(
        { length: flameCount }, 
        (_, i) => i * HOLE_SPACING
    );
    
    // Get active frequencies
    const activeFrequencies = [];
    const activeAmplitudes = [];
    
    for (const channelId in channelData) {
        const channel = channelData[channelId];
        if (!channel.mute && channel.volume > 0) {
            activeFrequencies.push(channel.frequency || baseFrequency);
            activeAmplitudes.push(channel.volume || 0.5);
        }
    }
    
    // Initialize pressure array
    const flamePressures = Array(flameCount).fill(0);
    
    // Sum contributions from each active frequency
    for (let f = 0; f < activeFrequencies.length; f++) {
        const frequency = activeFrequencies[f];
        const amplitude = activeAmplitudes[f];
        
        // Calculate pressures at hole positions
        const pressures = calculateTNetworkPressures(frequency, holePositions);
        
        // Calculate the angular frequency once
        const omega = 2 * Math.PI * frequency;
        const timeComponent = Math.sin(omega * currentTime);
        
        // Add pressure contribution for this frequency at each hole position
        for (let i = 0; i < flameCount; i++) {
            flamePressures[i] += amplitude * pressures[i] * timeComponent;
        }
    }
    
    // Calculate time-averaged pressures - use directly for flames
    const averagedPressures = flamePressures.map((pressure, i) => {
        const position = i * HOLE_SPACING;
        return Math.abs(calculateAveragePressure(position, pressure, currentTime));
    });
    
    // No normalization - use pressure values directly 
    window.normalizedFlameFactors = averagedPressures;
    
    return averagedPressures;
}

// Calculate time-averaged pressure at a position
function calculateAveragePressure(position, currentPressure, currentTime) {
    // Initialize history for this position if it doesn't exist
    if (!pressureTimeHistory[position]) {
        pressureTimeHistory[position] = [];
    }
    
    const history = pressureTimeHistory[position];
    
    // Add the current pressure to the history with the physics timestamp
    history.push({ time: currentTime, value: currentPressure });
    
    // Remove entries older than our averaging window based on physics time
    const cutoffTime = currentTime - PRESSURE_AVERAGING_TIME;
    while (history.length > 0 && history[0].time < cutoffTime) {
        history.shift();
    }
    
    // Calculate the time-weighted average
    let weightedSum = 0;
    let totalWeight = 0;
    
    for (let i = 0; i < history.length; i++) {
        // More recent values get higher weight
        const age = currentTime - history[i].time;
        const weight = 1.0 - (age / PRESSURE_AVERAGING_TIME);
        
        weightedSum += history[i].value * weight;
        totalWeight += weight;
    }
    
    return totalWeight > 0 ? weightedSum / totalWeight : 0;
}

// T-network model for Rubens' flame tube
function calculateTNetworkPressures(frequency, positions) {
    // Convert angular frequency
    const omega = 2 * Math.PI * frequency;
    
    // Calculate wave number (k = ω/c)
    const k = omega / speedOfSound;
    
    // Calculate base acoustic impedance (Z₀)
    const Z0 = DENSITY_PROPANE * speedOfSound;
    
    // Array to store calculated pressures at each position
    const pressures = new Array(positions.length);
    
    // Calculate for each position
    for (let i = 0; i < positions.length; i++) {
        const x = positions[i];
        
        // Transmission line impedance (tube segment)
        // Z = Z₀ * (1 / sin(k*L)) - using actual hole spacing
        const segmentImpedance = Z0 / Math.sin(k * HOLE_SPACING);
        
        // Shunt impedance (hole) - now includes the damping coefficient as a multiplier
        // Z_hole = Z₀ * (k * r * (1 + HOLE_IMPEDANCE_FACTOR)) * dampingFactor
        const dampingFactor = 1 + dampingCoefficient * 2; // Converts user damping into impedance scaling
        const holeImpedance = Z0 * k * (holeSize / 2) * (1 + HOLE_IMPEDANCE_FACTOR) * dampingFactor;
        
        // Calculate pressure at position using impedance model
        // P(x) = P₀ * cos(k*x) + j * (Z₀/Z_hole) * sin(k*x)
        const incidentPressure = Math.cos(k * x);
        
        // Apply tube losses related to distance based on damping coefficient
        const positionDamping = Math.exp(-dampingCoefficient * x);
        const reflectedPressure = (Z0 / holeImpedance) * Math.sin(k * x);
        
        // Total pressure magnitude at this position, with position-based damping applied once
        pressures[i] = Math.sqrt(
            (incidentPressure * incidentPressure) + 
            (reflectedPressure * reflectedPressure)
        ) * positionDamping;
    }
    
    return pressures;
}

// Calculate pressure distribution for the chart
function calculatePressureDistribution(positions, currentTime) {
    // Get active frequencies
    const activeFrequencies = [];
    const activeAmplitudes = [];
    
    for (const channelId in channelData) {
        const channel = channelData[channelId];
        if (!channel.mute && channel.volume > 0) {
            activeFrequencies.push(channel.frequency || baseFrequency);
            activeAmplitudes.push(channel.volume || 0.5);
        }
    }
    
    // Initialize pressure distribution
    const pressureDistribution = new Array(positions.length).fill(0);
    
    // Sum contributions from each active frequency
    for (let f = 0; f < activeFrequencies.length; f++) {
        const frequency = activeFrequencies[f];
        const amplitude = activeAmplitudes[f];
        
        // Calculate pressures using T-network model
        const pressures = calculateTNetworkPressures(frequency, positions);
        
        // Add this frequency's contribution to total pressure
        for (let i = 0; i < positions.length; i++) {
            pressureDistribution[i] += amplitude * pressures[i];
        }
    }
    
    return pressureDistribution;
}

// Export necessary functions
window.calculateFundamental = calculateFundamental;
window.generateStandingWave = generateStandingWave;
window.generateEnvelope = generateEnvelope;
window.updateFlamePhysics = updateFlamePhysics;
window.calculatePressureDistribution = calculatePressureDistribution;