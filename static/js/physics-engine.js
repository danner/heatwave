// Physics parameters and calculations

// Physics parameters
let speedOfSound = 258; // m/s - speed of sound in propane
let tubeLength = 3; // meters
let tubeDiameter = 0.10; // meters (10cm - heatwave tube diameter)
let holeSize = 0.001; // meters (1mm - typical hole diameter)
let propanePressure = 1.1; // Normalized pressure
let baseFrequency = 110; // Hz
let dampingCoefficient = 0.05; // Damping coefficient per meter
const externalPressure = 1.0; // Normalized external pressure

// Constants for flow rate calculations
const FLOW_RATE_AVERAGING_WINDOW = 0.5;
const TIME_INCREMENT = 0.02;
const FRAMES_TO_AVERAGE = Math.ceil(FLOW_RATE_AVERAGING_WINDOW / TIME_INCREMENT);
let reflections = 5; // Default number of reflections

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

        // Skip muted channels
        if (channel.mute) continue;

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
            const reflectionContribution = amplitude * reflectionDamping * 
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
window.calculateFundamental = calculateFundamental;
window.generateStandingWave = generateStandingWave;
window.calculatePressureGradient = calculatePressureGradient;
window.generateEnvelope = generateEnvelope;