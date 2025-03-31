// Flame visualization and animation

let flames = []; // Will be populated after DOM loads
let flameHistory = []; // Will be populated after DOM loads
let flowRateHistory = []; // Will be populated after DOM loads

// Initialize flame elements - renamed to match calling convention
function initializeFlames() {
    console.log("Initializing flames with count:", window.flameCount);
    const tube = document.getElementById('tube');
    
    // Create flames
    for (let i = 0; i < window.flameCount; i++) {
        const flame = document.createElement('div');
        flame.className = 'flame';
        flame.style.left = `${(i / window.flameCount) * 100}%`;
        flame.style.height = '10px'; // Default height
        tube.appendChild(flame);
    }
    
    // Get all flames for animation
    flames = document.querySelectorAll('.flame');
    
    // Create flame history arrays for smoothing
    flameHistory = Array.from({ length: window.flameCount }, () => Array(10).fill(20));
    
    // Create flow rate history arrays
    flowRateHistory = Array(window.pointCount).fill().map(() => []);
}

// Calculate the average flow rate over the time window
function calculateAverageFlowRate(currentFlowRate, position) {
    // Get the history for this position
    const history = flowRateHistory[position];
    
    // Add the current flow rate to the history
    history.push(currentFlowRate);
    
    // Limit history length to our averaging window
    if (history.length > FRAMES_TO_AVERAGE) {
        history.shift();
    }
    
    // Calculate the average
    const sum = history.reduce((acc, val) => acc + val, 0);
    return history.length > 0 ? sum / history.length : 0;
}

// Calculate flow rates for each flame position
function calculateFlameFlowRates(waveData) {
    return Array.from({ length: flames.length }, (_, i) => {
        const dataIndex = Math.floor((i / flames.length) * waveData.length);
        
        // Get pressure and calculate pressure gradient
        const pressure = waveData[dataIndex];
        const pressureGradient = calculatePressureGradient(waveData, dataIndex);
        
        // Use oscillation magnitude for Bernoulli effect
        const oscillationMagnitude = Math.abs(pressureGradient);
        
        // Calculate time-averaged oscillation magnitude
        const avgOscillation = calculateAverageFlowRate(oscillationMagnitude, dataIndex);
        
        // Calculate flow rate based on hole size
        const holeArea = Math.PI * Math.pow(holeSize, 2);
        
        // Return flow rate using Bernoulli principle
        return avgOscillation * Math.sqrt(holeArea) * 2000;
    });
}

// Convert flow rates to normalized factors for gas conservation
function normalizeFlowFactors(flowRates) {
    // Convert flow rates to factors (0.5 to 2.0 range)
    const oscillationFactors = flowRates.map(rate => 
        0.5 + Math.min(1.5, Math.abs(rate) / 50));
    
    // Calculate total for normalization
    const totalOscillationFactor = oscillationFactors.reduce((sum, factor) => sum + factor, 0);
    
    // Return normalized factors that maintain total gas flow
    return oscillationFactors.map(factor => 
        (factor / totalOscillationFactor) * flames.length);
}

// Update flame visuals based on normalized height factors
function updateFlameVisuals(normalizedFactors, baseHeight) {
    for (let i = 0; i < flames.length; i++) {
        // Calculate new height with conservation of total flow
        const newHeight = baseHeight * normalizedFactors[i];
        
        // Update flame's height history
        flameHistory[i].shift();
        flameHistory[i].push(newHeight);
        
        // Calculate the average height over the last frames for smoothing
        const averageHeight = flameHistory[i].reduce((sum, h) => sum + h, 0) / 
                              flameHistory[i].length;
        
        // Apply height to flame
        flames[i].style.height = `${averageHeight}px`;
        
        // Calculate intensity based on ratio to base height
        const heightRatio = averageHeight / baseHeight;
        updateFlameAppearance(flames[i], heightRatio);
    }
}

// Update flame color and width based on height ratio
function updateFlameAppearance(flameElement, heightRatio) {
    const normalizedIntensity = Math.min(1, Math.max(0.2, heightRatio * 0.8));
    
    // Scientific flame coloration gradient
    flameElement.style.background = `
        linear-gradient(to top,
        rgb(0, 0, ${Math.min(255, 180 + normalizedIntensity * 75)}),
        rgb(${Math.min(255, 150 + normalizedIntensity * 105)}, 
            ${Math.min(255, 150 + normalizedIntensity * 105)}, 
            ${Math.min(255, 100 + normalizedIntensity * 155)}),
        rgb(${Math.min(255, 220 + normalizedIntensity * 35)}, 
            ${Math.min(255, 180 + normalizedIntensity * 75)}, 
            ${Math.min(255, 50 * normalizedIntensity)}),
        rgb(${Math.min(255, 255)}, 
            ${Math.min(255, 100 * normalizedIntensity)}, 
            0))
    `;
    
    // Width calculation based on height ratio
    const baseWidth = Math.max(2, Math.min(5, holeSize * 10000));
    const widthFactor = heightRatio > 1 ? Math.sqrt(heightRatio) : 1;
    const flameWidth = baseWidth * widthFactor;
    flameElement.style.width = `${Math.min(20, flameWidth)}px`;
}

// Main flame animation function
function animateFlames(waveData) {
    // Calculate flow rates based on pressure oscillations
    const flowRates = calculateFlameFlowRates(waveData);
    
    // Calculate base height based on propane pressure
    const baseHeight = 20 + (propanePressure * 20);
    
    // Convert to normalized factors that conserve total gas flow
    const normalizedFactors = normalizeFlowFactors(flowRates);
    
    // Update visual appearance of flames
    updateFlameVisuals(normalizedFactors, baseHeight);
}

// Expose the function to the global scope
window.initializeFlames = initializeFlames;
window.animateFlames = animateFlames;
window.calculateAverageFlowRate = calculateAverageFlowRate;
window.calculateFlameFlowRates = calculateFlameFlowRates;
window.normalizeFlowFactors = normalizeFlowFactors;
