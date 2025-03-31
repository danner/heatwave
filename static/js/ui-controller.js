// UI controls and event handlers

// Variables for tracking state
window.isPaused = false;
window.animationFrameId = null;

// Initialize all UI controls
function initializeControls() {
    setupBasicControls();
    setupDampingControl();
    setupReflectionsControl();
    setupTubeDiameterControl();
    setupHoleSizeControl();
    setupPressureControl();
}

// Set up basic controls (speed of sound, tube length, animation toggle)
function setupBasicControls() {
    document.getElementById('speedOfSound').addEventListener('input', function(e) {
        speedOfSound = parseFloat(e.target.value);
        updatePhysicsInfo();
    });
    
    document.getElementById('tubeLength').addEventListener('input', function(e) {
        tubeLength = parseFloat(e.target.value);
        updatePhysicsInfo();
    });
    
    document.getElementById('toggleAnimationBtn').addEventListener('click', function() {
        if (window.isPaused) {
            // Currently paused, so resume
            window.isPaused = false;
            this.textContent = 'Pause';
            updateSimulation(); // Restart animation
        } else {
            // Currently playing, so pause
            window.isPaused = true;
            this.textContent = 'Resume';
            if (window.animationFrameId) {
                cancelAnimationFrame(window.animationFrameId);
                window.animationFrameId = null;
            }
        }
    });
}

// Set up damping control
function setupDampingControl() {
    const controlsDiv = document.querySelector('.controls');
    const dampingControl = document.createElement('div');
    dampingControl.className = 'control-group';
    dampingControl.innerHTML = `
        <span class="control-label">Damping</span>
        <input type="range" id="dampingSlider" min="0" max="0.5" step="0.01" value="${dampingCoefficient}">
        <span id="dampingValue">${dampingCoefficient}</span>
    `;
    controlsDiv.appendChild(dampingControl);

    document.getElementById('dampingSlider').addEventListener('input', function(e) {
        dampingCoefficient = parseFloat(e.target.value);
        document.getElementById('dampingValue').textContent = dampingCoefficient.toFixed(2);
        
        // Trigger an immediate update to the visualization
        if (!window.isPaused && !window.animationFrameId) {
            updateSimulation();
        }
    });
}

// Set up reflections control
function setupReflectionsControl() {
    const controlsDiv = document.querySelector('.controls');
    const reflectionsControl = document.createElement('div');
    reflectionsControl.className = 'control-group';
    reflectionsControl.innerHTML = `
        <span class="control-label">Reflections</span>
        <input type="number" id="reflectionsInput" value="${reflections}" min="1" max="20" step="1">
    `;
    controlsDiv.appendChild(reflectionsControl);

    document.getElementById('reflectionsInput').addEventListener('input', function(e) {
        reflections = parseInt(e.target.value, 10);
        // Force immediate chart update to show new reflections
        if (!window.isPaused) {
            if (window.animationFrameId) {
                cancelAnimationFrame(window.animationFrameId);
                window.animationFrameId = null;
            }
            updateSimulation();
        }
    });
}

// Set up tube diameter control
function setupTubeDiameterControl() {
    const controlsDiv = document.querySelector('.controls');
    const diameterControl = document.createElement('div');
    diameterControl.className = 'control-group';
    diameterControl.innerHTML = `
        <span class="control-label">Tube Diameter (cm)</span>
        <input type="range" id="tubeDiameterSlider" min="2" max="15" step="0.5" value="${tubeDiameter * 100}">
        <span id="tubeDiameterValue">${tubeDiameter * 100}</span>
    `;
    controlsDiv.appendChild(diameterControl);

    document.getElementById('tubeDiameterSlider').addEventListener('input', function(e) {
        tubeDiameter = parseFloat(e.target.value) / 100; // Convert cm to meters
        document.getElementById('tubeDiameterValue').textContent = e.target.value;
        updatePhysicsInfo();
    });
}

// Set up hole size control
function setupHoleSizeControl() {
    const controlsDiv = document.querySelector('.controls');
    const holeSizeControl = document.createElement('div');
    holeSizeControl.className = 'control-group';
    holeSizeControl.innerHTML = `
        <span class="control-label">Hole Size (mm)</span>
        <input type="range" id="holeSizeSlider" min="0.5" max="3" step="0.1" value="${holeSize * 1000}">
        <span id="holeSizeValue">${holeSize * 1000}</span>
    `;
    controlsDiv.appendChild(holeSizeControl);

    document.getElementById('holeSizeSlider').addEventListener('input', function(e) {
        holeSize = parseFloat(e.target.value) / 1000; // Convert mm to meters
        document.getElementById('holeSizeValue').textContent = e.target.value;
        updatePhysicsInfo();
    });
}

// Set up propane pressure control
function setupPressureControl() {
    const controlsDiv = document.querySelector('.controls');
    const pressureControl = document.createElement('div');
    pressureControl.className = 'control-group';
    pressureControl.innerHTML = `
        <span class="control-label">Propane Pressure</span>
        <input type="range" id="propanePressureSlider" min="0.2" max="2" step="0.1" value="${propanePressure}">
        <span id="propanePressureValue">${propanePressure}</span>
    `;
    controlsDiv.appendChild(pressureControl);

    document.getElementById('propanePressureSlider').addEventListener('input', function(e) {
        propanePressure = parseFloat(e.target.value);
        document.getElementById('propanePressureValue').textContent = e.target.value;
        updatePhysicsInfo();
    });
}

// Function to update the physics information display
function updatePhysicsInfo() {
    const fundamental = calculateFundamental();
    document.getElementById('fundamentalFreq').textContent = fundamental.toFixed(1);
    
    // Calculate wavelength for current frequency
    const wavelength = speedOfSound / baseFrequency;
    document.getElementById('wavelength').textContent = wavelength.toFixed(1);
    
    // Calculate resonances (odd harmonics only)
    const resonances = [1, 3, 5, 7, 9, 11, 13].map(n => (n * fundamental).toFixed(1)).join(', ') + '...';
    document.getElementById('resonances').textContent = resonances;
    
    // Add effective length calculation
    const radius = tubeDiameter / 2;
    const endCorrection = 0.6 * radius;
    const effectiveLength = tubeLength + endCorrection;
    document.getElementById('effectiveLength').textContent = effectiveLength.toFixed(1);
    document.getElementById('tubeDiameter').textContent = (tubeDiameter * 100).toFixed(1);
    document.getElementById('holeSize').textContent = (holeSize * 1000).toFixed(1);
    document.getElementById('propanePressure').textContent = propanePressure.toFixed(1);
    document.getElementById('reflections').textContent = reflections;
    document.getElementById('damping').textContent = dampingCoefficient.toFixed(2);
}

// Function to set up the physics info display elements in the DOM
function setupPhysicsInfoDisplay() {
    const physicsInfoDiv = document.querySelector('.physics-info');
    physicsInfoDiv.innerHTML = `
        <h3>Physics Parameters</h3>
        <div class="physics-params">
            <div>
                <strong>Fundamental Frequency:</strong> <span id="fundamentalFreq">0</span> Hz
            </div>
            <div>
                <strong>Wavelength:</strong> <span id="wavelength">0</span> m
            </div>
            <div>
                <strong>Resonant Frequencies:</strong> <span id="resonances">0</span> Hz
            </div>
            <div>
                <strong>Effective Length:</strong> <span id="effectiveLength">0</span> m
            </div>
            <div>
                <strong>Tube Diameter:</strong> <span id="tubeDiameter">0</span> cm
            </div>
            <div>
                <strong>Hole Size:</strong> <span id="holeSize">0</span> mm
            </div>
            <div>
                <strong>Propane Pressure:</strong> <span id="propanePressure">0</span> (normalized)
            </div>
            <div>
                <strong>Reflections:</strong> <span id="reflections">0</span>
            </div>
            <div>
                <strong>Damping:</strong> <span id="damping">0</span> m<sup>-1</sup>
            </div>
        </div>
    `;
}

// Setup function for adding navigation links
function setupNavigation() {
    const navDiv = document.querySelector('.nav-link');
    navDiv.innerHTML = `
        <a href="/" class="nav-button">Back to Channel Editor</a>
    `;
}

// Main update function that drives the simulation
function updateSimulation() {
    if (window.isPaused) {
        return;
    }
    
    // Increment simulation time
    time += TIME_INCREMENT;
    
    // Generate wave data for the current time
    const waveData = Array(pointCount).fill().map((_, i) => {
        const position = (i / pointCount) * tubeLength;
        return generateStandingWave(position, time, reflections).combinedWave;
    });
    
    // Update the chart with new data
    updateChart(waveData); 

    // Animate the flames based on the wave data
    animateFlames(waveData);
    
    // Schedule the next animation frame
    window.animationFrameId = requestAnimationFrame(updateSimulation);
}

// Initialize all UI components
function initializeUI() {
    // Set up all control elements
    initializeControls();
    
    // Set up the physics info display
    setupPhysicsInfoDisplay();
    
    // Set up navigation links
    setupNavigation();
    
    // Update physics info with initial values
    updatePhysicsInfo();
    
    // Start the simulation
    if (!window.isPaused) {
        updateSimulation();
    }
}

// Call this when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initializeUI);
window.setupBasicControls = setupBasicControls;
window.setupDampingControl = setupDampingControl;
window.setupReflectionsControl = setupReflectionsControl;
window.setupTubeDiameterControl = setupTubeDiameterControl;
window.setupHoleSizeControl = setupHoleSizeControl;
window.setupPressureControl = setupPressureControl;
window.updateSimulation = updateSimulation;
window.updatePhysicsInfo = updatePhysicsInfo;
window.initializeUI = initializeUI;
window.setupPhysicsInfoDisplay = setupPhysicsInfoDisplay;