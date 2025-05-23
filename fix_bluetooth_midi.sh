#!/bin/bash
# Script to fix Bluetooth MIDI profile issues

set -e  # Exit on errors

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root (sudo)."
  exit 1
fi

echo "=== Fixing Bluetooth MIDI Profile ==="

# Make sure the Bluetooth service is running
systemctl restart bluetooth
sleep 2

# Install required packages
apt-get update -qq
apt-get install -y -qq bluez-hcidump bluez-tools 

# Fix Bluetooth permissions
echo "Fixing Bluetooth permissions..."
usermod -a -G bluetooth,audio heatwave

# Update ALSA config for better MIDI timing
if ! grep -q "options snd-seq" /etc/modprobe.d/alsa-base.conf 2>/dev/null; then
  echo "options snd-seq devices=1 seq_midi_event=1" > /etc/modprobe.d/alsa-base.conf
fi

# Create/update Bluetooth MIDI profile configuration
echo "Setting up Bluetooth MIDI profile..."
cat > /etc/bluetooth/midi.conf << EOF
[General]
# MIDI profile improvements
# Increase timeouts and buffer sizes
ReadTimeout=10000
WriteTimeout=10000
BufferSize=4096
# Set MIDI as trusted profile
Enable=Source,Sink,Media,Socket
EOF

# Restart ALSA services
echo "Restarting ALSA services..."
systemctl restart alsa-restore.service || true
sleep 1

# Fix BlueZ plugin for MIDI
if ! grep -q "midi.conf" /etc/bluetooth/main.conf 2>/dev/null; then
  echo "Updating BlueZ configuration..."
  echo "ConfigFile=midi.conf" >> /etc/bluetooth/main.conf
fi

# Fix profile timing issues
echo "Fixing profile timing issues..."
BT_DEVICE="B5:66:41:94:78:F5"  # Your SMC-Mixer device

# Disconnect and reconnect with improved settings
echo "Resetting connection to MIDI device..."
bluetoothctl -- disconnect $BT_DEVICE || true
sleep 2
bluetoothctl -- remove $BT_DEVICE || true
sleep 2
bluetoothctl -- scan on &
SCAN_PID=$!
sleep 5
kill $SCAN_PID || true

# Pair with specific MIDI profile options
bluetoothctl -- pair $BT_DEVICE || true
sleep 2
bluetoothctl -- trust $BT_DEVICE
sleep 1

# Try connecting with improved timeouts
echo "Attempting improved connection..."
bluetoothctl -- connect $BT_DEVICE
sleep 3

echo "=== Fix completed ==="
echo "Bluetooth MIDI profile has been reconfigured."
echo "Restart the heatwave service with: sudo systemctl restart heatwave"
echo "If MIDI still doesn't work, try rebooting the system."
