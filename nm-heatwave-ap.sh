#!/bin/bash

# NetworkManager dispatcher script for Heatwave AP
# This script starts/stops the dnsmasq captive portal when the Heatwave AP is activated

INTERFACE=$1
STATUS=$2
CONNECTION=$3

# Location of the custom dnsmasq config
DNSMASQ_CONF="/home/heatwave/heatwave-app/dnsmasq.conf"

# Log file
LOG_FILE="/var/log/heatwave-ap.log"

log() {
    echo "$(date): $1" >> "$LOG_FILE"
    echo "$1"
}

# Only run for the Heatwave connection
if [ "$CONNECTION" = "Heatwave" ]; then
    if [ "$STATUS" = "up" ]; then
        log "Heatwave AP activated on $INTERFACE. Starting captive portal..."
        
        # Stop the system dnsmasq if it's running
        if systemctl is-active --quiet dnsmasq; then
            log "Stopping system dnsmasq service"
            systemctl stop dnsmasq
        fi
        
        # Start dnsmasq with our custom config
        log "Starting dnsmasq with custom config"
        dnsmasq --conf-file="$DNSMASQ_CONF" --no-daemon --log-facility="$LOG_FILE" &
        
        # Store the PID for later cleanup
        echo $! > /tmp/heatwave-dnsmasq.pid
        log "Dnsmasq started with PID $(cat /tmp/heatwave-dnsmasq.pid)"
        
    elif [ "$STATUS" = "down" ]; then
        log "Heatwave AP deactivated. Stopping captive portal..."
        
        # Kill our custom dnsmasq instance
        if [ -f /tmp/heatwave-dnsmasq.pid ]; then
            DNSMASQ_PID=$(cat /tmp/heatwave-dnsmasq.pid)
            log "Killing dnsmasq PID $DNSMASQ_PID"
            kill "$DNSMASQ_PID" 2>/dev/null
            rm /tmp/heatwave-dnsmasq.pid
        fi
        
        # Restart the system dnsmasq if it was enabled
        if systemctl is-enabled --quiet dnsmasq; then
            log "Restarting system dnsmasq service"
            systemctl start dnsmasq
        fi
    fi
fi
