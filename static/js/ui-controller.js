// UI controls and event handlers

// Variables for tracking state
window.isPaused = false;
window.animationFrameId = null;

// Use existing socket from channel-manager.js rather than creating a new one
let socketIO = null;

// Initialize all UI controls
function initializeControls() {
    setupBasicControls();
    setupDampingControl();
    setupReflectionsControl();
    setupTubeDiameterControl();
    setupHoleSizeControl();
    setupPressureControl();
    setupQFactorControl();
    
    // Initialize Socket.IO connection
    initializeSocketIO();
}

// Initialize Socket.IO connection
function initializeSocketIO() {
    // Get socket reference from channel-manager.js
    if (window.socket) {
        socketIO = window.socket;
        
        // Listen for tube parameter updates
        socketIO.on('update_tube_param', function(data) {
            updateTubeParamControl(data.param, data.value);
        });
        
        socketIO.on('update_tube_params', function(data) {
            // Update all tube parameters at once
            Object.entries(data).forEach(([param, value]) => {
                updateTubeParamControl(param, value);
            });
        });
        
        // Request current tube parameters
        socketIO.emit('request_tube_params');
        console.log("Socket.IO initialized for UI controller");
    } else {
        console.log("Socket.IO not available - running in standalone mode");
    }
}

// Update UI control based on tube parameter updates from server
function updateTubeParamControl(param, value) {
    // console.log(`Updating tube parameter: ${param} = ${value}`);
    switch(param) {
        case 'speed_of_sound':
            document.getElementById('speedOfSound').value = value;
            speedOfSound = value;
            break;
        case 'tube_length':
            document.getElementById('tubeLength').value = value;
            tubeLength = value;
            break;
        case 'tube_diameter':
            document.getElementById('tubeDiameterSlider').value = value * 100;
            document.getElementById('tubeDiameterValue').textContent = (value * 100).toFixed(1);
            tubeDiameter = value;
            break;
        case 'damping_coefficient':
            document.getElementById('dampingSlider').value = value;
            document.getElementById('dampingValue').textContent = value.toFixed(2);
            dampingCoefficient = value;
            break;
        case 'hole_size':
            document.getElementById('holeSizeSlider').value = value * 1000;
            document.getElementById('holeSizeValue').textContent = (value * 1000).toFixed(1);
            holeSize = value;
            break;
        case 'propane_pressure':
            document.getElementById('propanePressureSlider').value = value;
            document.getElementById('propanePressureValue').textContent = value.toFixed(1);
            propanePressure = value;
            break;
        case 'reflections':
            document.getElementById('reflectionsInput').value = value;
            window.reflections = value;
            break;
        case 'q_factor':
            document.getElementById('qFactor').value = value;
            document.getElementById('qFactor').nextElementSibling.textContent = value.toFixed(1);
            window.Q_FACTOR = value;
            break;
    }
    
    // Update physics info and frequency response
    updatePhysicsInfo();
    if (window.updateFrequencyResponse) {
        window.updateFrequencyResponse();
    }
}

// Send tube parameter changes to server
function emitTubeParamChange(param, value) {
    if (socketIO && socketIO.connected) {
        // console.log(`Emitting tube param change: ${param} = ${value}`);
        socketIO.emit('change_tube_param', {
            param: param,
            value: value
        });
    }
}

// Set up basic controls (speed of sound, tube length, animation toggle)
function setupBasicControls() {
    document.getElementById('speedOfSound').addEventListener('input', function(e) {
        speedOfSound = parseFloat(e.target.value);
        updatePhysicsInfo();
        window.updateFrequencyResponse();
        emitTubeParamChange('speed_of_sound', speedOfSound);
    });
    
    document.getElementById('tubeLength').addEventListener('input', function(e) {
        tubeLength = parseFloat(e.target.value);
        updatePhysicsInfo();
        window.updateFrequencyResponse();
        emitTubeParamChange('tube_length', tubeLength);
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
        window.updateFrequencyResponse();
        emitTubeParamChange('damping_coefficient', dampingCoefficient);
    });
}

// Set up reflections control
function setupReflectionsControl() {
    const controlsDiv = document.querySelector('.controls');
    const reflectionsControl = document.createElement('div');
    reflectionsControl.className = 'control-group';
    reflectionsControl.innerHTML = `
        <span class="control-label">Reflections</span>
        <input type="number" id="reflectionsInput" value="${window.reflections}" min="1" max="20" step="1">
    `;
    controlsDiv.appendChild(reflectionsControl);

    document.getElementById('reflectionsInput').addEventListener('input', function(e) {
        window.reflections = parseInt(e.target.value, 10);
        
        // Force frequency response update when reflections change
        if (window.updateFrequencyResponse) {
            window.updateFrequencyResponse();
        }
        
        // Force immediate chart update
        if (!window.isPaused) {
            if (window.animationFrameId) {
                cancelAnimationFrame(window.animationFrameId);
                window.animationFrameId = null;
            }
            updateSimulation();
        }
        
        emitTubeParamChange('reflections', window.reflections);
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
        window.updateFrequencyResponse();
        emitTubeParamChange('tube_diameter', tubeDiameter);
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
        window.updateFrequencyResponse();
        emitTubeParamChange('hole_size', holeSize);
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
        emitTubeParamChange('propane_pressure', propanePressure);
    });
}

// Add to UI initialization
function setupQFactorControl() {
    const controlDiv = document.createElement('div');
    controlDiv.className = 'control-group';
    
    const label = document.createElement('span');
    label.className = 'control-label';
    label.textContent = 'Resonance Quality (Q)';
    
    const input = document.createElement('input');
    input.type = 'range';
    input.id = 'qFactor';
    input.min = '1';
    input.max = '15';
    input.value = '5';
    input.step = '0.5';
    
    const valueDisplay = document.createElement('span');
    valueDisplay.textContent = input.value;
    valueDisplay.style.marginLeft = '8px';
    
    controlDiv.appendChild(label);
    controlDiv.appendChild(input);
    controlDiv.appendChild(valueDisplay);
    
    document.querySelector('.controls').appendChild(controlDiv);
    
    // Initialize global variable
    window.Q_FACTOR = parseFloat(input.value);
    
    // Event listener
    input.addEventListener('input', function() {
        window.Q_FACTOR = parseFloat(this.value);
        valueDisplay.textContent = this.value;
        
        // Update frequency response chart
        if (window.updateFrequencyResponse) {
            window.updateFrequencyResponse();
        }
        
        emitTubeParamChange('q_factor', window.Q_FACTOR);
    });
}

// Function to update the physics information display
function updatePhysicsInfo() {
    const fundamental = calculateFundamental();
    
    // Add null checks for all elements
    const fundamentalElem = document.getElementById('fundamentalFreq');
    if (fundamentalElem) fundamentalElem.textContent = fundamental.toFixed(1);
    
    // Calculate wavelength for current frequency
    const wavelength = speedOfSound / baseFrequency;
    const wavelengthElem = document.getElementById('wavelength');
    if (wavelengthElem) wavelengthElem.textContent = wavelength.toFixed(1);
    
    // Calculate resonances (odd harmonics only)
    const resonances = [1, 3, 5, 7, 9, 11, 13].map(n => (n * fundamental).toFixed(1)).join(', ') + '...';
    const resonancesElem = document.getElementById('resonances');
    if (resonancesElem) resonancesElem.textContent = resonances;
    
    // Add effective length calculation
    const radius = tubeDiameter / 2;
    const endCorrection = 0.6 * radius;
    const effectiveLength = tubeLength + endCorrection;
    
    // Add null checks for all remaining elements
    const elements = {
        'effectiveLength': effectiveLength.toFixed(1),
        'tubeDiameter': (tubeDiameter * 100).toFixed(1),
        'holeSize': (holeSize * 1000).toFixed(1),
        'propanePressure': propanePressure.toFixed(1),
        'reflections': window.reflections,
        'damping': dampingCoefficient.toFixed(2)
    };
    
    // Set text content only if element exists
    Object.entries(elements).forEach(([id, value]) => {
        const elem = document.getElementById(id);
        if (elem) elem.textContent = value;
    });
}

// Function to set up the physics info display elements in the DOM
function setupPhysicsInfoDisplay() {
    const physicsInfoDiv = document.querySelector('.physics-info');
    
    // Check if the display is already populated to avoid duplication
    if (physicsInfoDiv.querySelector('.physics-params')) {
        return; // Exit if already set up
    }
    
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

// Physics timing variables
let lastPhysicsTime = 0;
const PHYSICS_TIMESTEP = 0.007; // Changed from 0.01 to 0.007 (approx 143Hz)
let accumulatedTime = 0;
let waveData = []; 

// Add frequency monitoring
let physicsStepsThisSecond = 0;
let lastSecond = Math.floor(performance.now() / 1000);

// Main update function that drives the simulation
function updateSimulation() {
    if (window.isPaused) {
        requestAnimationFrame(updateSimulation);
        return;
    }
    
    // Calculate delta time since last frame
    const currentTime = performance.now() / 1000;
    const deltaTime = Math.min(0.1, currentTime - lastPhysicsTime);
    lastPhysicsTime = currentTime;
    
    // Accumulate time for fixed physics steps
    accumulatedTime += deltaTime;
    
    // Flag to track if physics was updated this frame
    let physicsUpdated = false;
    
    // Update physics with fixed timestep
    while (accumulatedTime >= PHYSICS_TIMESTEP) {
        // Increment simulation time
        time += PHYSICS_TIMESTEP;
        window.time = time;
        
        // Generate wave data for the current time
        waveData = Array(pointCount).fill().map((_, i) => {
            const position = (i / pointCount) * tubeLength;
            return generateStandingWave(position, time, reflections).combinedWave;
        });
        
        // Calculate pressure distribution here in the physics loop
        const positions = Array(pointCount).fill().map((_, i) => (i / pointCount) * tubeLength);
        const pressureDistribution = calculatePressureDistribution(positions, time);
        
        // Store normalized pressure distribution for visualization
        const maxPressure = Math.max(...pressureDistribution.map(Math.abs));
        window.normalizedPressureDistribution = maxPressure > 0 
            ? pressureDistribution.map(p => p / maxPressure)
            : [...pressureDistribution];
        
        window.normalizedFlameFactors = updateFlamePhysics(waveData, window.flameCount, time);
        
        accumulatedTime -= PHYSICS_TIMESTEP;
        physicsUpdated = true;

        // Add frequency monitoring
        physicsStepsThisSecond++;
        const currentSecond = Math.floor(performance.now() / 1000);
        if (currentSecond > lastSecond) {
            // console.log(`Physics updates per second: ${physicsStepsThisSecond}`);
            physicsStepsThisSecond = 0;
            lastSecond = currentSecond;
        }
    }
    
    // Update visual elements at display refresh rate
    if (waveData && waveData.length > 0) {
        updateChart(waveData);
        animateFlames();
    }
    
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
    
    // Initialize frequency response chart
    window.initializeFrequencyResponse();
    
    // Generate initial frequency response data
    window.updateFrequencyResponse();
}

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