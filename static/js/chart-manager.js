// Chart management and visualization

let chart;
let lastFrameTime = 0;

// Initialize the chart
function initializeChart() {
    const ctx = document.getElementById('waveChart').getContext('2d');
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array(pointCount).fill(''),
            datasets: [
                {
                    label: 'Combined Wave',
                    data: Array(pointCount).fill(0),
                    borderColor: 'rgb(75, 192, 192)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0
                },
                {
                    label: 'Standing Wave Envelope',
                    data: Array(pointCount).fill(0),
                    borderColor: 'rgba(255, 99, 132, 0.5)',
                    borderDash: [5, 5],
                    borderWidth: 1,
                    fill: false,
                    tension: 0
                },
                {
                    label: 'Negative Envelope',
                    data: Array(pointCount).fill(0),
                    borderColor: 'rgba(255, 99, 132, 0.5)',
                    borderDash: [5, 5],
                    borderWidth: 1,
                    fill: false,
                    tension: 0
                },
                {
                    label: 'Average Flow Rate',
                    data: Array(pointCount).fill(0),
                    borderColor: 'rgba(153, 102, 255, 1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0,
                    yAxisID: 'flowrate'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 0 // No animation for better performance
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Position along tube (m)'
                    },
                    ticks: {
                        callback: function(value, index) {
                            // Show only some tick marks
                            if (index % 50 === 0) {
                                return (index / pointCount * tubeLength).toFixed(1);
                            }
                            return null;
                        }
                    }
                },
                y: {
                    min: -1.2,
                    max: 1.2,
                    title: {
                        display: true,
                        text: 'Pressure Amplitude'
                    }
                },
                flowrate: {
                    min: -1.5,
                    max: 1.5,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Flow Rate'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
    
    // Update the dataset label for flow rate
    chart.data.datasets[3].label = 'Flow Velocity';
}

// Update chart with new wave data
function updateChartData(waveData) {
    // Calculate actual elapsed time since last frame
    const now = performance.now();
    const deltaTime = now - (lastFrameTime || now);
    lastFrameTime = now;
    
    const positions = Array(pointCount).fill().map((_, i) => (i / pointCount) * tubeLength);

    // Use the current time for calculations
    const currentTime = window.time || 0;
    
    // Calculate the pressure distribution using the T-network model
    const pressureDistribution = calculatePressureDistribution(positions, currentTime);
    
    // Normalize the pressure distribution for display
    let normalizedPressureDistribution = [...pressureDistribution];
    const maxPressure = Math.max(...pressureDistribution.map(Math.abs));
    if (maxPressure > 0) {
        normalizedPressureDistribution = pressureDistribution.map(p => p / maxPressure);
    }

    // Get the flame height factors
    const normalizedFactors = window.normalizedFlameFactors || Array(window.flameCount).fill(1);
    
    // Resample for chart display - convert from flame positions to chart positions
    const resampledFactors = Array(pointCount).fill(0);
    for (let i = 0; i < pointCount; i++) {
        const position = (i / pointCount) * tubeLength;
        const flameIndex = Math.floor(position / HOLE_SPACING);
        
        if (flameIndex < normalizedFactors.length) {
            resampledFactors[i] = normalizedFactors[flameIndex];
        }
    }

    const envelopeData = positions.map(pos => generateEnvelope(pos));
    const negativeEnvelopeData = envelopeData.map(val => -val);

    // Update main datasets
    chart.data.datasets[0].data = waveData;
    chart.data.datasets[1].data = envelopeData;
    chart.data.datasets[2].data = negativeEnvelopeData;
    chart.data.datasets[3].data = normalizedPressureDistribution;
    
    // Add or update the flame factors dataset
    if (chart.data.datasets.length <= 4) {
        chart.data.datasets.push({
            label: 'Flame Height Factors',
            data: resampledFactors,
            borderColor: 'rgba(255, 159, 64, 1)',
            borderWidth: 2,
            fill: false,
            tension: 0,
            yAxisID: 'flowrate'
        });
    } else {
        chart.data.datasets[4].data = resampledFactors;
    }

    // Update the dataset labels
    chart.data.datasets[3].label = 'Pressure Distribution';
    chart.options.scales.flowrate.title.text = 'Pressure & Flame Factors';
    
    chart.update();
}

window.updateChart = updateChartData;
window.initializeChart = initializeChart;