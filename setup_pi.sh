#!/bin/bash
# Raspberry Pi Setup Script for Zwiffery Virtual Trainer
# Run this script to automatically set up your Raspberry Pi

set -e

echo "=============================================="
echo "  Zwiffery Virtual Trainer Setup"
echo "  Raspberry Pi Configuration"
echo "=============================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "   Continuing anyway..."
    echo ""
fi

# Update system
echo "📦 Step 1: Updating system packages..."
sudo apt update
echo "✓ System updated"
echo ""

# Install Bluetooth packages
echo "📶 Step 2: Installing Bluetooth dependencies..."
sudo apt install -y bluetooth bluez libbluetooth-dev
echo "✓ Bluetooth packages installed"
echo ""

# Install Python dependencies
echo "🐍 Step 3: Installing Python dependencies..."
sudo apt install -y python3 python3-pip python3-venv
echo "✓ Python installed"
echo ""

# Create virtual environment
echo "🔧 Step 4: Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate and install requirements
echo "📚 Step 5: Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Python packages installed"
echo ""

# Enable Bluetooth
echo "🔵 Step 6: Enabling Bluetooth service..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
echo "✓ Bluetooth service enabled"
echo ""

# Configure BlueZ for iOS bonding
echo "📱 Step 6.5: Configuring BlueZ for iOS bonding..."
BLUEZ_CONF="/etc/bluetooth/main.conf"
if [ -f "$BLUEZ_CONF" ]; then
    # Backup original config
    if [ ! -f "${BLUEZ_CONF}.backup" ]; then
        sudo cp "$BLUEZ_CONF" "${BLUEZ_CONF}.backup"
        echo "✓ Backed up original BlueZ config"
    fi
    
    # Check if Policy section exists and update it
    if grep -q "^\[Policy\]" "$BLUEZ_CONF"; then
        # Policy section exists, update it
        if ! grep -q "JustWorksRepairing=always" "$BLUEZ_CONF"; then
            sudo sed -i '/^\[Policy\]/a JustWorksRepairing=always' "$BLUEZ_CONF"
        fi
        if ! grep -q "^AutoEnable=true" "$BLUEZ_CONF"; then
            sudo sed -i '/^\[Policy\]/a AutoEnable=true' "$BLUEZ_CONF"
        fi
    else
        # Policy section doesn't exist, add it
        echo "" | sudo tee -a "$BLUEZ_CONF" > /dev/null
        echo "[Policy]" | sudo tee -a "$BLUEZ_CONF" > /dev/null
        echo "AutoEnable=true" | sudo tee -a "$BLUEZ_CONF" > /dev/null
        echo "JustWorksRepairing=always" | sudo tee -a "$BLUEZ_CONF" > /dev/null
    fi
    
    echo "✓ BlueZ configured for iOS bonding"
    echo "   - JustWorksRepairing=always (for easier iOS pairing)"
    echo "   - AutoEnable=true (auto-enable Bluetooth)"
    echo ""
    echo "   Restarting Bluetooth service to apply changes..."
    sudo systemctl restart bluetooth
    sleep 2
    echo "✓ Bluetooth service restarted"
else
    echo "⚠️  BlueZ config file not found at $BLUEZ_CONF"
    echo "   You may need to configure it manually"
fi
echo ""

# Check Bluetooth status
echo "🔍 Step 7: Checking Bluetooth status..."
if systemctl is-active --quiet bluetooth; then
    echo "✓ Bluetooth service is running"
else
    echo "❌ Bluetooth service is not running"
    echo "   Try: sudo systemctl start bluetooth"
fi
echo ""

# Set up permissions
echo "🔐 Step 8: Setting up Bluetooth permissions..."
echo ""
echo "Choose a permission method:"
echo "  1) Run with sudo (simpler, need sudo each time)"
echo "  2) Set capabilities (recommended, no sudo needed)"
echo ""
read -p "Enter choice [1 or 2]: " choice

if [ "$choice" = "2" ]; then
    echo "Setting capabilities..."
    sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))
    echo "✓ Capabilities set (no sudo needed)"
    RUN_CMD="python3 virtual_trainer.py"
else
    echo "✓ You'll need to run with sudo"
    RUN_CMD="sudo python3 virtual_trainer.py"
fi
echo ""

# Create systemd service (optional)
echo "🤖 Step 9: Create systemd service (auto-start on boot)?"
read -p "Install as system service? [y/N]: " install_service

if [ "$install_service" = "y" ] || [ "$install_service" = "Y" ]; then
    SERVICE_FILE="/etc/systemd/system/zwiffery.service"
    
    echo "Creating systemd service..."
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Zwiffery Virtual Trainer
After=bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 $(pwd)/virtual_trainer.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable zwiffery.service
    
    echo "✓ Systemd service created"
    echo ""
    echo "Service commands:"
    echo "  Start:   sudo systemctl start zwiffery"
    echo "  Stop:    sudo systemctl stop zwiffery"
    echo "  Status:  sudo systemctl status zwiffery"
    echo "  Logs:    sudo journalctl -u zwiffery -f"
    echo ""
fi

# Test Bluetooth
echo "🧪 Step 10: Testing Bluetooth..."
if command -v hciconfig &> /dev/null; then
    sudo hciconfig hci0 up
    if sudo hciconfig hci0 | grep -q "UP RUNNING"; then
        echo "✓ Bluetooth adapter is up and running"
    else
        echo "⚠️  Bluetooth adapter may not be working properly"
    fi
else
    echo "⚠️  hciconfig not found (this is okay on newer systems)"
fi
echo ""

# Final instructions
echo "=============================================="
echo "  ✓ Setup Complete!"
echo "=============================================="
echo ""
echo "🚀 Quick Start:"
echo ""
echo "  1. Run the trainer:"
echo "     $RUN_CMD"
echo ""
echo "  2. Open Zwift on your device"
echo ""
echo "  3. Look for 'Zwiffery Trainer' in pairing screen"
echo ""
echo "  4. Pair as Power Source and Cadence"
echo ""
echo "  5. Start riding! 🚴"
echo ""
echo "📖 For more options:"
echo "   python3 virtual_trainer.py --help"
echo ""
echo "🐛 Troubleshooting:"
echo "   See README.md for common issues"
echo ""
echo "=============================================="

