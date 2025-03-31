// Main visualization.js - Acts as the orchestrator module

// Define globals at the top - ONLY HERE, not in other files
window.pointCount = 500; // Number of points to plot
window.flameCount = 100; // Number of flames along the tube
window.channelData = {};
window.isPaused = false;
window.animationFrameId = null;
window.time = 0;

// Initialize everything when DOM is loaded - moved to end of file
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing components...");
    
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