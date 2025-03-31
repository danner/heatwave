// Main visualization.js - Acts as the orchestrator module

// Define globals at the top - ONLY HERE, not in other files
const HOLE_SPACING = 0.02; // 2cm spacing between holes
window.pointCount = 500; // Number of points to plot
window.flameCount = Math.floor(tubeLength / HOLE_SPACING); // Calculate flame count from tube length
window.channelData = {};
window.isPaused = false;
window.animationFrameId = null;
window.time = 0;
window.reflections = 5; // Default number of reflections

// Initialize everything when DOM is loaded - moved to end of file
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing components...");
    
    // Calculate flame count based on tube length and hole spacing
    window.flameCount = Math.floor(tubeLength / HOLE_SPACING);
    console.log(`Setting up tube with ${window.flameCount} flames at ${HOLE_SPACING}m spacing`);
    
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