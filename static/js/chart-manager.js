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
    chart.data.datasets[3].label = 'Average Flow Rate (1/4 sec)';
}

// Update chart with new wave data
function updateChartData(waveData) {
    // Calculate actual elapsed time since last frame
    const now = performance.now();
    const deltaTime = now - (lastFrameTime || now);
    lastFrameTime = now;
    
    const positions = Array(pointCount).fill().map((_, i) => (i / pointCount) * tubeLength);

    // Calculate instantaneous flow rate data
    const instantFlowRateData = waveData.map((pressure, index) => {
        // Use pressure gradient for flow rate calculation
        return calculatePressureGradient(waveData, index);
    });
    
    // Calculate the average flow rate using time window
    const averageFlowRateData = instantFlowRateData.map((flowRate, index) => 
        calculateAverageFlowRate(flowRate, index));

    const envelopeData = positions.map(pos => generateEnvelope(pos));
    const negativeEnvelopeData = envelopeData.map(val => -val);

    // Update main datasets
    chart.data.datasets[0].data = waveData;
    chart.data.datasets[1].data = envelopeData;
    chart.data.datasets[2].data = negativeEnvelopeData;
    chart.data.datasets[3].data = averageFlowRateData; // Use average flow rate
    
    // Remove any extra datasets beyond the main ones
    while (chart.data.datasets.length > 4) {
        chart.data.datasets.pop();
    }

    chart.update();
}

window.updateChart = updateChartData;
window.initializeChart = initializeChart;