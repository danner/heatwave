// Flame visualization and animation

let flames = []; // Will be populated after DOM loads
let flameHistory = []; // Will be populated after DOM loads - for visual smoothing only

// Initialize flame elements
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
    
    // Create flame history arrays for visual smoothing only
    flameHistory = Array.from({ length: window.flameCount }, () => Array(5).fill(20));
}

// Update flame visuals based on normalized height factors
function updateFlameVisuals(normalizedFactors, baseHeight) {
    for (let i = 0; i < flames.length; i++) {
        // Calculate new height with conservation of total flow
        const newHeight = baseHeight * normalizedFactors[i];
        
        // Update flame's height history (for visual smoothing only)
        flameHistory[i].shift();
        flameHistory[i].push(newHeight);
        
        // Calculate the average height over the last frames for visual smoothing
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

// Main flame animation function - now directly uses pressure values
function animateFlames() {
    // Get pressure values from physics engine
    const pressureValues = window.normalizedFlameFactors || Array(flames.length).fill(1);
    
    // Base height constant - this will be multiplied by pressure
    const baseHeight = 20;
    
    // Scale factor to make flames visible (since pressure values are typically small)
    const pressureScaleFactor = 50 * propanePressure;
    
    // Update visual appearance of flames
    for (let i = 0; i < flames.length; i++) {
        // Calculate new height based directly on pressure values
        const newHeight = baseHeight + pressureValues[i] * pressureScaleFactor;
        
        // Update flame's height history (for visual smoothing only)
        flameHistory[i].shift();
        flameHistory[i].push(newHeight);
        
        // Calculate the average height over the last frames for visual smoothing
        const averageHeight = flameHistory[i].reduce((sum, h) => sum + h, 0) / 
                              flameHistory[i].length;
        
        // Apply height to flame
        flames[i].style.height = `${Math.max(5, averageHeight)}px`;
        
        // Calculate intensity based on relative height
        const heightRatio = averageHeight / baseHeight;
        updateFlameAppearance(flames[i], heightRatio);
    }
}

// Expose the function to the global scope
window.initializeFlames = initializeFlames;
window.animateFlames = animateFlames;
