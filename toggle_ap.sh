#!/bin/bash

# Toggle between WiFi client mode and AP mode
# This script handles the transition in a single command to prevent disconnection issues

HOME_CONN="TheAddiction"
AP_CONN="Heatwave"

function activate_ap() {
    echo "Activating Heatwave AP mode..."
    # Execute both commands in sequence without allowing interruption
    (nmcli con down "$HOME_CONN" && nmcli con up "$AP_CONN") &
    
    echo "AP mode transition initiated!"
    echo "You will be disconnected from SSH if connected via WiFi."
    echo "The Heatwave AP will be available in a few seconds."
    echo "Connect to the 'Heatwave' network to access the web interface."
}

function activate_client() {
    echo "Switching back to home WiFi mode..."
    # Execute both commands in sequence without allowing interruption
    (nmcli con down "$AP_CONN" && nmcli con up "$HOME_CONN") &
    
    echo "WiFi client mode transition initiated!"
    echo "You will be disconnected from the AP if connected via it."
    echo "The Raspberry Pi will attempt to connect back to your home WiFi."
}

# Show current state
echo "Current network status:"
nmcli con show --active

# Check if we're currently in AP mode
if nmcli -t -f NAME con show --active | grep -q "$AP_CONN"; then
    echo "Currently in AP mode"
    read -p "Switch back to home WiFi? (y/n): " choice
    if [[ $choice == [Yy]* ]]; then
        activate_client
    else
        echo "Staying in AP mode"
    fi
else
    echo "Currently in client WiFi mode"
    read -p "Switch to AP mode? (y/n): " choice
    if [[ $choice == [Yy]* ]]; then
        activate_ap
    else
        echo "Staying in client mode"
    fi
fi
