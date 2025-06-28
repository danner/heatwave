#!/bin/bash

# Heatwave deployment script
# This script will copy configuration files to the correct locations and restart services

# Exit on any error
set -e

# Configuration
APP_DIR="/home/heatwave/heatwave-app"
SYSTEMD_SERVICE_FILE="heatwave.service"
DNSMASQ_CONF="dnsmasq.conf"
NM_SCRIPT="nm-heatwave-ap.sh"
NM_SCRIPT_DEST="/etc/NetworkManager/dispatcher.d/90-heatwave-ap"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root"
    echo "Try: sudo $0"
    exit 1
fi

echo "Deploying Heatwave application..."

# Get the current directory
CURRENT_DIR=$(pwd)

# Check if we need to download libraries (if static/libs directory is empty)
if [ ! -d "static/libs" ] || [ -z "$(ls -A static/libs 2>/dev/null)" ]; then
    echo "Local libraries not found. Downloading required libraries..."
    bash download_libs.sh
fi

# Install Python dependencies
echo "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    # Check if we're already in a virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "Using existing virtual environment: $VIRTUAL_ENV"
        pip install -r requirements.txt
    else
        # Check if a venv exists in the app directory, if not create one
        VENV_DIR="$APP_DIR/venv"
        if [ ! -d "$VENV_DIR" ]; then
            echo "Creating a virtual environment in $VENV_DIR"
            python3 -m venv "$VENV_DIR"
        else
            echo "Using existing virtual environment in $VENV_DIR"
        fi

        # Activate and use the virtual environment to install packages
        echo "Installing packages in the virtual environment..."
        "$VENV_DIR/bin/pip" install -r requirements.txt

        # Update the systemd service file to use the virtual environment
        if [ -f "$SYSTEMD_SERVICE_FILE" ]; then
            # Use sed to update the ExecStart path if needed
            sed -i "s|^ExecStart=.*|ExecStart=$VENV_DIR/bin/python main.py|" "$SYSTEMD_SERVICE_FILE"
            echo "Updated systemd service to use the virtual environment"
        fi
    fi
else
    echo "Warning: requirements.txt not found in current directory"
fi

# 1. Ensure the application directory exists
echo "Checking application directory..."
mkdir -p "$APP_DIR"

# 2. Copy systemd service file
echo "Installing systemd service file..."
if [ -f "$SYSTEMD_SERVICE_FILE" ]; then
    cp "$SYSTEMD_SERVICE_FILE" /etc/systemd/system/
else
    echo "Warning: $SYSTEMD_SERVICE_FILE not found in current directory"
fi

# 3. Copy dnsmasq configuration if we're not already in the app directory
echo "Installing dnsmasq configuration..."
if [ "$CURRENT_DIR" != "$APP_DIR" ] && [ -f "$DNSMASQ_CONF" ]; then
    cp "$DNSMASQ_CONF" "$APP_DIR/"
elif [ ! -f "$APP_DIR/$DNSMASQ_CONF" ]; then
    echo "Warning: $DNSMASQ_CONF not found in current directory or app directory"
fi

# 4. Install NetworkManager dispatcher script
echo "Installing NetworkManager dispatcher script..."
if [ -f "$NM_SCRIPT" ]; then
    cp "$NM_SCRIPT" "$NM_SCRIPT_DEST"
    chmod +x "$NM_SCRIPT_DEST"
else
    echo "Warning: $NM_SCRIPT not found in current directory"
fi

# 5. Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# 6. Restart the Heatwave service
echo "Restarting Heatwave service..."
if systemctl is-active --quiet heatwave; then
    systemctl restart heatwave
else
    systemctl enable heatwave
    systemctl start heatwave
fi

# 7. Restart NetworkManager to pick up the dispatcher script
echo "Restarting NetworkManager..."
systemctl restart NetworkManager

echo "Deployment complete!"
echo "Heatwave should now be running and will start automatically on boot."
echo "Web interface is available at http://$(hostname -I | awk '{print $1}'):6134"
echo "If using the AP mode, connect to the 'Heatwave' network to access the application."
