#!/bin/bash
# Streamlined Bluetooth MIDI setup script for Raspberry Pi

# Set the MAC address of the SMC-Mixer device
MIDI_DEVICE="B5:66:41:94:78:F5"
MIDI_NAME="SMC-Mixer"

echo "===== HeatWave Bluetooth MIDI Setup ====="
echo "Setting up connection to $MIDI_NAME ($MIDI_DEVICE)"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root (sudo)."
  exit 1
fi

# Install required packages
echo "Installing required Bluetooth packages..."
apt-get update -qq && apt-get install -y -qq bluetooth bluez bluez-tools

# Restart and enable Bluetooth service
echo "Configuring Bluetooth service..."
systemctl restart bluetooth
systemctl enable bluetooth

# Add user to bluetooth group
usermod -a -G bluetooth heatwave
usermod -a -G audio heatwave

# Configure Bluetooth settings
echo "Configuring Bluetooth settings..."
cat > /etc/bluetooth/main.conf << EOF
[General]
Name = HeatWave
Class = 0x000100
DiscoverableTimeout = 0
PairableTimeout = 0
AutoEnable=true

[Policy]
AutoEnable=true
EOF

# Create automatic connection script
echo "Creating connection script..."
cat > /usr/local/bin/connect-midi.sh << EOF
#!/bin/bash
# Script to connect to SMC-Mixer Bluetooth MIDI device

# Ensure Bluetooth is up and running
hciconfig hci0 up
bluetoothctl -- power on
bluetoothctl -- agent on 
bluetoothctl -- default-agent

# Connect to the MIDI device
echo "Connecting to $MIDI_NAME ($MIDI_DEVICE)..."
bluetoothctl -- trust $MIDI_DEVICE
bluetoothctl -- connect $MIDI_DEVICE
EOF

chmod +x /usr/local/bin/connect-midi.sh

# Create systemd service for auto-reconnecting
echo "Creating autostart service..."
cat > /etc/systemd/system/bluetooth-midi-connect.service << EOF
[Unit]
Description=Connect to SMC-Mixer Bluetooth MIDI device
After=bluetooth.service
Requires=bluetooth.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/connect-midi.sh
RemainAfterExit=true
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable bluetooth-midi-connect.service

# Attempt to connect now
echo "Attempting to connect to $MIDI_NAME now..."
/usr/local/bin/connect-midi.sh

echo "Setup complete. The system will automatically try to connect to $MIDI_NAME on startup."
echo "To manually reconnect at any time, run: sudo /usr/local/bin/connect-midi.sh"
