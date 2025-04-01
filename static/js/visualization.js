// Main visualization.js - Acts as the orchestrator module

// Define globals at the top - ONLY HERE, not in other files
const HOLE_SPACING = 0.02; // 2cm spacing between holes
window.pointCount = 500; // Number of points to plot
window.flameCount = 150; // Default number of flames
window.channelData = {};
window.isPaused = false;
window.animationFrameId = null;
window.time = 0;
window.reflections = 5;  // Default number of reflections
window.Q_FACTOR = 5.0;   // Default Q factor

// Function to set up the tube container element
function setupTube() {
    console.log("Setting up tube container...");
    const visualizationContainer = document.getElementById('visualization-container') || document.body;
    
    // Check if tube already exists
    let tubeElement = document.getElementById('tube');
    if (!tubeElement) {
        tubeElement = document.createElement('div');
        tubeElement.id = 'tube';
        visualizationContainer.prepend(tubeElement);
        console.log("Tube element created");
    }
    
    // Calculate flame count based on tube length and hole spacing
    window.flameCount = Math.floor(tubeLength / HOLE_SPACING);
    console.log(`Configured tube with ${window.flameCount} flames at ${HOLE_SPACING}m spacing`);
    
    return tubeElement;
}

// Single DOMContentLoaded event listener that handles all initialization
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing components...');
    
    // Ensure global variables are set before other scripts use them
    window.reflections = window.reflections || 5;
    window.Q_FACTOR = window.Q_FACTOR || 5.0;
    
    // Initialize components in the correct order
    setupTube();
    
    // Wait for modules to be ready before initializing
    // Each module should expose an initialization function
    if (typeof initializeFlames === 'function') {
        console.log("Initializing flames...");
        initializeFlames();
    }
    
    if (typeof initializeChart === 'function') {
        console.log("Initializing chart...");
        initializeChart();
    }
    
    if (typeof initializeUI === 'function') {
        console.log("Initializing UI...");
        initializeUI();
    }
    
    if (typeof initializeChannelManager === 'function') {
        console.log("Initializing channel manager...");
        initializeChannelManager();
    }
    
    // Start the simulation if UI module has exposed this function
    if (typeof updatePhysicsInfo === 'function') {
        updatePhysicsInfo();
    }
    
    if (typeof updateSimulation === 'function') {
        updateSimulation();
    }
});