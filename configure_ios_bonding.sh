#!/bin/bash
# BlueZ Configuration Script for iOS Bonding
# This script configures BlueZ to work better with iOS devices
# Run this if you're experiencing repeated pairing requests on iPhone

set -e

echo "=============================================="
echo "  BlueZ iOS Bonding Configuration"
echo "=============================================="
echo ""

BLUEZ_CONF="/etc/bluetooth/main.conf"

if [ ! -f "$BLUEZ_CONF" ]; then
    echo "❌ BlueZ config file not found at $BLUEZ_CONF"
    echo "   Make sure BlueZ is installed: sudo apt install bluez"
    exit 1
fi

# Backup original config
if [ ! -f "${BLUEZ_CONF}.backup" ]; then
    echo "📋 Backing up original config..."
    sudo cp "$BLUEZ_CONF" "${BLUEZ_CONF}.backup"
    echo "✓ Backup created: ${BLUEZ_CONF}.backup"
fi

echo "🔧 Configuring BlueZ for iOS bonding..."
echo ""

# Check if Policy section exists
if grep -q "^\[Policy\]" "$BLUEZ_CONF"; then
    echo "✓ [Policy] section found, updating..."
    
    # Remove existing settings if they exist
    sudo sed -i '/^JustWorksRepairing=/d' "$BLUEZ_CONF"
    sudo sed -i '/^AutoEnable=/d' "$BLUEZ_CONF"
    
    # Add new settings after [Policy]
    sudo sed -i '/^\[Policy\]/a JustWorksRepairing=always' "$BLUEZ_CONF"
    sudo sed -i '/^\[Policy\]/a AutoEnable=true' "$BLUEZ_CONF"
else
    echo "✓ Adding [Policy] section..."
    echo "" | sudo tee -a "$BLUEZ_CONF" > /dev/null
    echo "[Policy]" | sudo tee -a "$BLUEZ_CONF" > /dev/null
    echo "AutoEnable=true" | sudo tee -a "$BLUEZ_CONF" > /dev/null
    echo "JustWorksRepairing=always" | sudo tee -a "$BLUEZ_CONF" > /dev/null
fi

# Also ensure device is set to be bondable
if ! grep -q "^\[General\]" "$BLUEZ_CONF"; then
    echo "" | sudo tee -a "$BLUEZ_CONF" > /dev/null
    echo "[General]" | sudo tee -a "$BLUEZ_CONF" > /dev/null
fi

if ! grep -q "^#AutoEnable" "$BLUEZ_CONF" && ! grep -q "^AutoEnable" "$BLUEZ_CONF"; then
    # Add AutoEnable in General section too
    sudo sed -i '/^\[General\]/a AutoEnable=true' "$BLUEZ_CONF"
fi

echo "✓ Configuration updated"
echo ""

# Show the relevant section
echo "📄 Current [Policy] section:"
echo "----------------------------------------"
grep -A 5 "^\[Policy\]" "$BLUEZ_CONF" || echo "(not found)"
echo "----------------------------------------"
echo ""

# Restart Bluetooth service
echo "🔄 Restarting Bluetooth service..."
sudo systemctl restart bluetooth
sleep 2

if systemctl is-active --quiet bluetooth; then
    echo "✓ Bluetooth service restarted successfully"
else
    echo "⚠️  Warning: Bluetooth service may not be running"
    echo "   Try: sudo systemctl start bluetooth"
fi

echo ""
echo "=============================================="
echo "  ✓ Configuration Complete!"
echo "=============================================="
echo ""
echo "📱 Next Steps:"
echo ""
echo "  1. Restart your virtual trainer:"
echo "     sudo systemctl restart zwiffery  # if using service"
echo "     # OR restart virtual_trainer.py manually"
echo ""
echo "  2. On your iPhone:"
echo "     - Go to Settings > Bluetooth"
echo "     - Find 'Zwiffery Trainer' and tap (i)"
echo "     - Tap 'Forget This Device' if it exists"
echo ""
echo "  3. Pair through Zwift app (not iPhone Settings)"
echo ""
echo "  4. The pairing should now persist better!"
echo ""
echo "💡 If issues persist:"
echo "   - Make sure you pair through Zwift, not iPhone Settings"
echo "   - Disable Wi-Fi Assist on iPhone (Settings > Cellular)"
echo "   - Keep devices within 3-5 feet"
echo ""
echo "=============================================="

