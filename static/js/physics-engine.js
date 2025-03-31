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

// Add these at the top with other physics parameters
// Constants for flow rate calculations
const FLOW_AVERAGING_TIME = 0.15;  // seconds of physics time to average over

// Physics data storage
let flowRateTimeHistory = {};  // Store history as {position: [{time, value}]}
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

// Calculate flow rate at a specific position - more physically accurate model
function calculateFlowRate(waveData, index, time) {
    if (index <= 0 || index >= waveData.length - 1) {
        return 0; // Return zero at boundaries
    }
    
    const position = (index / pointCount) * tubeLength;
    let totalFlowRate = 0;
    
    // For each active channel, calculate its contribution to flow rate
    for (const channelId in channelData) {
        const channel = channelData[channelId];
        if (channel.mute || channel.volume === 0) continue;
        
        const freq = channel.frequency || baseFrequency;
        const amplitude = channel.volume || 0.5;
        
        // Calculate wavelength and wave properties
        const wavelength = speedOfSound / freq;
        const k = 2 * Math.PI / wavelength;  // Wave number
        const omega = 2 * Math.PI * freq;    // Angular frequency
        
        // In a standing wave, velocity is 90 degrees out of phase with pressure
        // This is a key physics principle in acoustic standing waves
        
        // Calculate spatial component with quarter-wavelength shift to account for
        // end corrections in Rijke tube (prevents zeros at certain frequencies)
        const spatialPhase = Math.PI / 2; // 90 degree phase shift
        const positionFactor = Math.cos(k * position - spatialPhase);
        
        // Calculate temporal component 
        const timeFactor = Math.sin(omega * time);
        
        // Calculate contributions without using reflections directly
        // This prevents the mathematical artifacts at 50Hz intervals
        const flowContribution = amplitude * positionFactor * timeFactor;
        
        // Add to the total flow rate
        totalFlowRate += flowContribution;
    }
    
    // Apply damping based on position - use less aggressive damping
    totalFlowRate *= Math.exp(-dampingCoefficient * 0.5 * position);
    
    return totalFlowRate;
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

// Calculate flow rates for each flame position - more physically accurate model
function calculateFlameFlowRates(waveData, flameCount, currentTime) {
    return Array.from({ length: flameCount }, (_, i) => {
        const dataIndex = Math.floor((i / flameCount) * waveData.length);
        
        // Calculate flow rate at this position
        const flowRate = calculateFlowRate(waveData, dataIndex, currentTime);
        
        // Store in history and get time-averaged value
        return calculateAverageFlowRate(flowRate, dataIndex, currentTime);
    });
}

// Convert flow rates to normalized factors for gas conservation - moved from flame-visualizer.js
function normalizeFlowFactors(flowRates) {
    const MIN_FACTOR = 0.125;  // 1/8 of normal height
    const MAX_FACTOR = 4.0;    // 4x normal height
    
    // Calculate the total absolute flow across all flames
    const totalFlow = flowRates.reduce((sum, rate) => sum + Math.abs(rate), 0);
    
    // Calculate the average flow per flame
    const averageFlow = totalFlow / flowRates.length || 1;
    
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
    
    return oscillationFactors.map(factor => factor * normalizeRatio);
}

// Update physics for flames - connects physics loop to flame visualization
function updateFlamePhysics(waveData, flameCount, currentTime) {
    // Calculate flow rates based on current wave data
    const flowRates = Array.from({ length: flameCount }, (_, i) => {
        const dataIndex = Math.floor((i / flameCount) * waveData.length);
        
        // Calculate flow rate at this position
        const flowRate = calculateFlowRate(waveData, dataIndex, currentTime);
        
        // Store in history and get time-averaged value
        return calculateAverageFlowRate(flowRate, dataIndex, currentTime);
    });
    
    // Normalize flow rates to conserve gas
    normalizedFlameFactors = normalizeFlowFactors(flowRates);
    
    // Expose to global scope for flame visualization
    window.normalizedFlameFactors = normalizedFlameFactors;
    
    return normalizedFlameFactors;
}

window.calculateFundamental = calculateFundamental;
window.generateStandingWave = generateStandingWave;
window.calculatePressureGradient = calculatePressureGradient;
window.generateEnvelope = generateEnvelope;
window.calculateFlowRate = calculateFlowRate;
window.updateFlamePhysics = updateFlamePhysics;