// Frequency Response Visualization

let frequencyResponseChart;
const MIN_FREQ = 20;  // Hz
const MAX_FREQ = 500; // Hz
const FREQ_STEPS = 350; // Higher resolution
const POSITION_STEPS = 200;

// Audio visualization constants
const MIN_MAGNITUDE_DB = 0;  // dB floor for visualization
const DEFAULT_MAX_MAGNITUDE_DB = 0;
const MIN_PRESSURE_MAGNITUDE = 1e-2;  // Minimum pressure magnitude (prevents -Infinity dB)
const MIN_DB_RANGE = 10;  // Ensure at least this much range for color scaling
const HUE_MAX = 240;  // Blue in HSL
const HUE_MIN = 0;    // Red in HSL

// Store min/max values globally for color scaling
let minMagnitude = MIN_MAGNITUDE_DB;
let maxMagnitude = DEFAULT_MAX_MAGNITUDE_DB;

// Initialize the frequency response chart
function initializeFrequencyResponse() {
    const ctx = document.getElementById('frequencyResponseChart').getContext('2d');
    
    // Create a blank chart initially
    frequencyResponseChart = new Chart(ctx, {
        type: 'matrix', 
        data: {
            datasets: [{
                label: 'Pressure Magnitude (dB)',
                data: [],
                borderWidth: 0,
                borderColor: 'transparent',
                backgroundColor: function(context) {
                    // Get value for this cell
                    const value = context.dataset.data[context.dataIndex]?.v || minMagnitude;
                    
                    // Create normalized value between 0-1
                    const normalizedValue = Math.max(0, Math.min(1, (value - minMagnitude) / (maxMagnitude - minMagnitude)));
                    
                    // Rainbow gradient - map to hue (240 = blue, 0 = red)
                    // Invert so blue is low and red is high
                    const hue = HUE_MAX - (normalizedValue * HUE_MAX);
                    
                    // Return HSL color with full saturation and 50% lightness
                    return `hsl(${hue}, 100%, 50%)`;
                },
                width: function(context) {
                    // Width of each cell based on number of data points
                    return (ctx.canvas.width * 0.9) / (FREQ_STEPS + 1);
                },
                height: function(context) {
                    // Height of each cell based on number of data points
                    return (ctx.canvas.height * 0.9) / (POSITION_STEPS + 1);
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const item = context[0];
                            return `Frequency: ${item.raw.x.toFixed(1)} Hz, Position: ${item.raw.y.toFixed(2)} m`;
                        },
                        label: function(context) {
                            return `Magnitude: ${context.raw.v.toFixed(2)} dB`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Frequency (Hz)'
                    },
                    min: MIN_FREQ,
                    max: MAX_FREQ
                },
                y: {
                    title: {
                        display: true,
                        text: 'Position (m)'
                    },
                    min: 0,
                    max: tubeLength
                }
            }
        }
    });
}

// Calculate magnitude data for the frequency response chart
function calculateFrequencyResponse() {
    const data = [];
    const freqStep = (MAX_FREQ - MIN_FREQ) / FREQ_STEPS;
    const posStep = tubeLength / POSITION_STEPS;
    
    // Reset min/max values
    minMagnitude = MIN_MAGNITUDE_DB;
    maxMagnitude = DEFAULT_MAX_MAGNITUDE_DB;
    
    // First pass - collect all magnitudes to find min/max
    const rawMagnitudes = [];
    
    // For every frequency
    for (let i = 0; i <= FREQ_STEPS; i++) {
        const frequency = MIN_FREQ + (i * freqStep);
        
        // Calculate pressures at this frequency for all positions
        const positions = Array(POSITION_STEPS + 1).fill().map((_, j) => j * posStep);
        let pressures;
        
        try {
            pressures = calculateTNetworkPressures(frequency, positions);
            
            // Store magnitude values
            for (let j = 0; j < pressures.length; j++) {
                const magnitude = Math.abs(pressures[j]); // Use absolute value
                const dB = magnitude > MIN_PRESSURE_MAGNITUDE ? 20 * Math.log10(magnitude) : MIN_MAGNITUDE_DB;
                rawMagnitudes.push(dB);
                
                // Update min/max
                minMagnitude = Math.min(minMagnitude, dB);
                maxMagnitude = Math.max(maxMagnitude, dB);
            }
        } catch (error) {
            console.error(`Error calculating pressures at frequency ${frequency} Hz:`, error);
            continue;
        }
    }
    
    // Ensure we have a reasonable range (avoid flat colors if all values are the same)
    if (maxMagnitude - minMagnitude < MIN_DB_RANGE) {
        minMagnitude = Math.min(MIN_MAGNITUDE_DB, minMagnitude - 5);
        maxMagnitude = Math.max(DEFAULT_MAX_MAGNITUDE_DB, maxMagnitude + 5);
    }
    
    console.log(`Magnitude range: ${minMagnitude.toFixed(2)}dB to ${maxMagnitude.toFixed(2)}dB`);
    
    // Second pass - create the dataset with the normalized values
    for (let i = 0; i <= FREQ_STEPS; i++) {
        const frequency = MIN_FREQ + (i * freqStep);
        
        // Calculate pressures again (could optimize by storing from first pass)
        const positions = Array(POSITION_STEPS + 1).fill().map((_, j) => j * posStep);
        let pressures;
        
        try {
            pressures = calculateTNetworkPressures(frequency, positions);
            
            // Convert to dB and add to dataset
            for (let j = 0; j < pressures.length; j++) {
                const position = j * posStep;
                const magnitude = Math.abs(pressures[j]);
                const dB = magnitude > MIN_PRESSURE_MAGNITUDE ? 20 * Math.log10(magnitude) : MIN_MAGNITUDE_DB;
                
                data.push({
                    x: frequency, 
                    y: position,
                    v: dB
                });
            }
        } catch (error) {
            continue; // Already logged in first pass
        }
    }
    
    return data;
}

// Add this to ensure the frequency response chart updates with reflections changes
function updateFrequencyResponse() {
    console.log(`Updating frequency response chart with reflections=${window.reflections}, Q=${window.Q_FACTOR}...`);
    const responseData = calculateFrequencyResponse();
    
    frequencyResponseChart.data.datasets[0].data = responseData;
    frequencyResponseChart.options.scales.y.max = tubeLength;
    frequencyResponseChart.update();
    
    // Update magnitude key labels with current min/max values
    const lowLabel = document.querySelector('.magnitude-labels span:first-child');
    const highLabel = document.querySelector('.magnitude-labels span:last-child');
    
    if (lowLabel && highLabel) {
        lowLabel.textContent = `${minMagnitude.toFixed(0)} dB`;
        highLabel.textContent = `${maxMagnitude.toFixed(0)} dB`;
    }
    
    console.log(`Generated ${responseData.length} data points for frequency response`);
}

// Initialize and expose functions
window.initializeFrequencyResponse = initializeFrequencyResponse;
window.updateFrequencyResponse = updateFrequencyResponse;