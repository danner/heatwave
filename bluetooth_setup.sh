#!/bin/bash
# Bluetooth MIDI troubleshooting and setup script for Raspberry Pi

echo "===== HeatWave Bluetooth MIDI Setup Script ====="
echo "This script will help diagnose and fix Bluetooth MIDI issues."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root (sudo)."
  exit 1
fi

# Step 1: Install required packages
echo "Step 1: Installing required Bluetooth packages..."
apt-get update
apt-get install -y bluetooth bluez bluez-tools pulseaudio-module-bluetooth python3-dbus

# Step 2: Check Bluetooth service status
echo -e "\nStep 2: Checking Bluetooth service status..."
systemctl status bluetooth --no-pager
systemctl restart bluetooth
sleep 2
echo "Enabling Bluetooth service to start on boot..."
systemctl enable bluetooth

# Step 3: Set executable permission for mido
echo -e "\nStep 3: Setting correct permissions for Python MIDI packages..."
# Find the virtual environment path (assumes it exists)
VENV_PATH="/home/heatwave/heatwave-venv"
if [ -d "$VENV_PATH" ]; then
  # Make sure the heatwave user owns the virtual environment
  chown -R heatwave:heatwave "$VENV_PATH"
  echo "Fixed permissions for $VENV_PATH"
else
  echo "Warning: Virtual environment not found at $VENV_PATH"
fi

# Step 4: Load Bluetooth modules
echo -e "\nStep 4: Loading Bluetooth modules..."
modprobe btusb
echo "btusb" >> /etc/modules

# Step 5: Configure Bluetooth agent
echo -e "\nStep 5: Configuring Bluetooth agent to auto-accept pairing requests..."
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

# Step 6: Add user to bluetooth group
echo -e "\nStep 6: Adding heatwave user to bluetooth group..."
usermod -a -G bluetooth heatwave

# Step 7: Create a udev rule for better MIDI device permissions
echo -e "\nStep 7: Creating udev rules for MIDI devices..."
cat > /etc/udev/rules.d/99-midi.rules << EOF
KERNEL=="midi*", GROUP="audio", MODE="0660"
KERNEL=="amidi*", GROUP="audio", MODE="0660"
SUBSYSTEMS=="usb", ATTRS{product}=="*MIDI*", GROUP="audio", MODE="0666"
SUBSYSTEMS=="bluetooth", GROUP="audio", MODE="0666"
EOF

# Reload udev rules
udevadm control --reload-rules && udevadm trigger

# Step 8: Create a script for scanning and connecting to the target MIDI device
echo -e "\nStep 8: Creating a Bluetooth scan and connection script..."
cat > /usr/local/bin/connect-midi.sh << EOF
#!/bin/bash
# Script to scan, pair, and connect to SMC-Mixer Bluetooth MIDI device

echo "Scanning for MIDI devices..."
hciconfig hci0 up
bluetoothctl -- power on
bluetoothctl -- agent on 
bluetoothctl -- default-agent
DEVICE=\$(bluetoothctl -- scan on | grep -i "SMC-Mixer" | awk '{print \$3}')

if [ -z "\$DEVICE" ]; then
  echo "SMC-Mixer not found."
  exit 1
fi

echo "Found SMC-Mixer Bluetooth device with address \$DEVICE"
bluetoothctl -- pair \$DEVICE
bluetoothctl -- trust \$DEVICE
bluetoothctl -- connect \$DEVICE

echo "Connection attempt complete."
EOF

chmod +x /usr/local/bin/connect-midi.sh

# Step 9: Create a systemd service for auto-reconnecting at startup
echo -e "\nStep 9: Creating a systemd service for automatic connection..."
cat > /etc/systemd/system/bluetooth-midi-connect.service << EOF
[Unit]
Description=Connect to Bluetooth MIDI device
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

systemctl daemon-reload
systemctl enable bluetooth-midi-connect.service

# Step 10: Restart services and perform manual connection attempt
echo -e "\nStep 10: Restarting Bluetooth and performing initial connection..."
systemctl restart bluetooth

echo -e "\nRunning connection script. Please make sure your MIDI controller is in pairing mode..."
/usr/local/bin/connect-midi.sh

echo -e "\n===== Setup Complete ====="
echo "The system has been configured for Bluetooth MIDI. Reboot recommended."
echo "After reboot, if the device doesn't connect automatically, run: sudo /usr/local/bin/connect-midi.sh"
echo "To check Bluetooth status: bluetoothctl"
echo "Common bluetoothctl commands:"
echo "  - devices           (list paired devices)"
echo "  - scan on           (scan for new devices)"
echo "  - pair [MAC]        (pair with device)"
echo "  - connect [MAC]     (connect to device)"
echo "  - trust [MAC]       (trust device for auto-connection)"
echo "  - info [MAC]        (get device info)"
echo "===== End of Setup ====="
