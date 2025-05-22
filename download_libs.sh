#!/bin/bash

# Script to download web libraries for offline use
# This is needed for AP mode where CDN resources aren't available

# Set up directories
LIBS_DIR="static/libs"
mkdir -p $LIBS_DIR

echo "Downloading libraries for offline use..."

# Download Socket.IO
echo "Downloading Socket.IO..."
curl -L https://cdn.socket.io/4.6.0/socket.io.min.js -o $LIBS_DIR/socket.io.min.js

# Download Chart.js
echo "Downloading Chart.js..."
curl -L https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js -o $LIBS_DIR/chart.js

# Download chartjs-chart-matrix
echo "Downloading chartjs-chart-matrix..."
curl -L https://cdn.jsdelivr.net/npm/chartjs-chart-matrix@2/dist/chartjs-chart-matrix.min.js -o $LIBS_DIR/chartjs-chart-matrix.js

# Download chartjs-plugin-colorschemes
echo "Downloading chartjs-plugin-colorschemes..."
curl -L https://cdn.jsdelivr.net/npm/chartjs-plugin-colorschemes@0.4.0/dist/chartjs-plugin-colorschemes.min.js -o $LIBS_DIR/chartjs-plugin-colorschemes.js

echo "Libraries downloaded successfully to $LIBS_DIR"
echo "Make sure to include this directory in your git repository."
