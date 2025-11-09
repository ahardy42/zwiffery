# 🚴 Zwiffery - Virtual Smart Bike Trainer

A Python-based virtual smart bike trainer that emulates a real trainer using Bluetooth Low Energy (BLE) and the FTMS (Fitness Machine Service) protocol. Perfect for testing Zwift integrations, development, or just having fun!

## ✨ Features

- **Full FTMS Protocol Support** - Industry-standard Fitness Machine Service
- **Power & Cadence Data** - Realistic cycling metrics with natural variations
- **ERG Mode Support** - Zwift can control your target power
- **SIM Mode Support** - Receives slope/resistance commands from Zwift
- **Configurable** - Easily adjust power, cadence, and behavior
- **Raspberry Pi Optimized** - Native Linux BLE support

## 🔧 Hardware Requirements

- **Raspberry Pi** (any model with Bluetooth)
  - Tested on: Pi 3, Pi 4, Pi Zero W
  - Requires built-in BLE or USB BLE dongle
- **OR** Linux computer with Bluetooth 4.0+

## 📦 Installation

### 1. Set Up Your Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3 and pip (usually pre-installed)
sudo apt install python3 python3-pip python3-venv -y

# Install Bluetooth dependencies
sudo apt install bluetooth bluez libbluetooth-dev -y

# Enable Bluetooth service
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
```

### 2. Clone or Download This Project

```bash
cd ~
git clone <your-repo-url> zwiffery
cd zwiffery
```

Or if you're copying files manually:
```bash
mkdir ~/zwiffery
cd ~/zwiffery
# Copy all files here
```

### 3. Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Set Up Bluetooth Permissions

The script needs permission to access Bluetooth. You have two options:

**Option A: Run with sudo (easier but less secure)**
```bash
sudo $(which python3) virtual_trainer.py
```

**Option B: Set capabilities (recommended)**
```bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))
```

## 🚀 Usage

### Basic Usage

Start the trainer with default settings (150W, 85 RPM):

```bash
python3 virtual_trainer.py
```

Or with sudo if needed:
```bash
sudo python3 virtual_trainer.py
```

### Custom Power and Cadence

```bash
python3 virtual_trainer.py --power 200 --cadence 90
```

### Change Device Name

```bash
python3 virtual_trainer.py --name "My Awesome Trainer"
```

### Enable Debug Logging

```bash
python3 virtual_trainer.py --debug
```

### All Options

```bash
python3 virtual_trainer.py --help
```

Available options:
- `--name` - BLE device name (default: "Zwiffery Trainer")
- `--power` - Base power in watts (default: 150)
- `--cadence` - Base cadence in RPM (default: 85)
- `--debug` - Enable debug logging

## 📱 Connecting to Zwift

1. **Start the Virtual Trainer**
   ```bash
   python3 virtual_trainer.py
   ```
   
   You should see:
   ```
   ============================================================
   Starting Virtual Trainer: Zwiffery Trainer
   ============================================================
   🚴 Virtual Trainer is ready!
   📱 Open Zwift and search for sensors
   🔍 Look for: 'Zwiffery Trainer'
   ⚡ Broadcasting power and cadence data...
   ```

2. **Open Zwift**
   - Go to the pairing screen
   - Look for "Zwiffery Trainer" (or your custom name)
   - Pair it as your **Power Source** and **Cadence Source**

3. **Start Riding!**
   - Zwift will receive power and cadence data
   - ERG mode workouts will work (Zwift controls your power target)
   - SIM mode will work (Zwift sends resistance based on terrain)

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Change default values
DEFAULT_POWER = 200
DEFAULT_CADENCE = 90

# Adjust realism
POWER_VARIATION = 20  # More variation = more realistic
CADENCE_VARIATION = 7

# Use workout profiles
WORKOUT_PROFILES = {
    "easy": {"power": 100, "cadence": 70},
    "hard": {"power": 250, "cadence": 95},
}
```

## 🔍 Troubleshooting

### Trainer Not Showing Up in Zwift

1. **Check Bluetooth is enabled:**
   ```bash
   sudo systemctl status bluetooth
   ```

2. **Check if BLE advertising is working:**
   ```bash
   sudo hcitool lescan
   ```
   You should see your trainer name

3. **Verify no other BLE services are interfering:**
   ```bash
   sudo systemctl stop bluetooth
   sudo systemctl start bluetooth
   ```

4. **Check permissions:**
   - Make sure you're running with `sudo` or have set capabilities
   - Some Pi models require sudo for BLE peripheral mode

### Permission Denied Errors

```bash
# Run with sudo
sudo python3 virtual_trainer.py

# Or set capabilities permanently
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))
```

### Python Module Not Found

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### iOS Connection Issues (Pairing/Disconnection)

If you're using an iPhone with Zwift and experiencing repeated pairing requests or disconnections:

1. **Pair through Zwift app, not iPhone Settings:**
   - Always pair the trainer through the Zwift app's pairing screen
   - Do NOT pair it through iPhone Settings > Bluetooth
   - This prevents connection conflicts

2. **Disable Wi-Fi Assist on iPhone:**
   - Go to Settings > Cellular
   - Scroll down and toggle off "Wi-Fi Assist"
   - This feature can disrupt BLE connections

3. **Keep devices close:**
   - Ensure iPhone and trainer are within 3-5 feet
   - Avoid physical obstructions between devices

4. **Reduce interference:**
   - Turn off other nearby Bluetooth devices
   - Reduce Wi-Fi router proximity if possible

5. **Configure BlueZ for better bonding (Linux/Raspberry Pi):**
   
   **Option A: Use the automated script (recommended):**
   ```bash
   chmod +x configure_ios_bonding.sh
   ./configure_ios_bonding.sh
   ```
   
   **Option B: Manual configuration:**
   ```bash
   # Edit BlueZ main configuration
   sudo nano /etc/bluetooth/main.conf
   
   # Add or modify these settings:
   [Policy]
   AutoEnable=true
   JustWorksRepairing=always
   
   # Restart Bluetooth service
   sudo systemctl restart bluetooth
   ```
   
   **After configuration:**
   - Restart your virtual trainer
   - On iPhone: Go to Settings > Bluetooth, find "Zwiffery Trainer", tap (i), and "Forget This Device"
   - Pair again through Zwift app (not iPhone Settings)

6. **If disconnections persist:**
   - Restart both iPhone and the trainer device
   - Unpair the trainer from Zwift, restart trainer, then re-pair
   - Check for iOS and Zwift app updates

### Bless Library Issues

If Bless doesn't work on your system, try the alternative using Bluezero:
```bash
pip install bluezero
# Use the alternative script (if provided)
```

## 🧪 Testing Without Zwift

You can test your trainer using BLE scanner apps:

**On iOS/Android:**
- nRF Connect (highly recommended)
- LightBlue

**Look for:**
- Service: `0x1826` (FTMS)
- Characteristics: Indoor Bike Data, Control Point

## 📊 Understanding the Output

When running, you'll see logs like:

```
Broadcasting - Power: 152.3W, Cadence: 86.2rpm, Speed: 27.2km/h
Control Point OpCode: 0x05
Zwift set target power (ERG mode): 200W
```

This shows:
- Real-time data being sent to Zwift
- Commands received from Zwift (ERG mode, resistance changes)

## 🔬 How It Works

### FTMS Protocol

The trainer implements the Fitness Machine Service (FTMS), a Bluetooth SIG standard:

1. **Service UUID:** `0x1826`
2. **Key Characteristics:**
   - Indoor Bike Data (`0x2AD2`) - Sends power, cadence, speed
   - Control Point (`0x2AD9`) - Receives commands from Zwift
   - Machine Features (`0x2ACC`) - Advertises capabilities
   - Status (`0x2ADA`) - Reports trainer status

### Data Format

Indoor Bike Data is sent as binary packed data:
```
[Flags: 2 bytes][Speed: 2 bytes][Cadence: 2 bytes][Power: 2 bytes]
```

- Speed: uint16, 0.01 km/h resolution
- Cadence: uint16, 0.5 RPM resolution  
- Power: sint16, 1 watt resolution

### ERG Mode

When Zwift sends a "Set Target Power" command (OpCode `0x05`):
1. Trainer receives target power (e.g., 200W)
2. Virtual trainer gradually adjusts power output
3. Simulates realistic ramp-up (not instant)

## 🛠️ Development

### Project Structure

```
zwiffery/
├── virtual_trainer.py   # Main trainer implementation
├── config.py           # Configuration and presets
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── setup_pi.sh        # Raspberry Pi setup script (optional)
```

### Analyzing Real Trainer Data

If you want to capture data from your real trainer:

1. **Install Wireshark with BLE support**
2. **Or use command line:**
   ```bash
   sudo btmon
   ```
3. **Pair your real trainer with Zwift and observe the packets**
4. **Look for:**
   - Service UUIDs
   - Characteristic UUIDs
   - Data formats and byte ordering

### Extending the Code

Want to add features? Here are some ideas:

- **Heart Rate Simulation** - Add Heart Rate Service (`0x180D`)
- **Steering Support** - Implement Zwift's steering protocol
- **ANT+ Support** - Add ANT+ broadcasting (requires additional hardware)
- **Web Dashboard** - Add Flask/FastAPI web interface to control trainer
- **Workout Recording** - Log all data to file for analysis

## 🤝 Contributing

Found a bug? Have an improvement? Feel free to:
1. Open an issue
2. Submit a pull request
3. Share your modifications

## ⚠️ Legal & Ethical Considerations

**This software is for:**
- Educational purposes
- Testing and development
- Personal use with your own Zwift account

**NOT for:**
- Cheating in Zwift races or competitions
- Fraudulent performance claims
- Any activity that violates Zwift's Terms of Service

Use responsibly! 🏆

## 📚 Resources

- [Bluetooth FTMS Specification](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/)
- [Zwift API Documentation](https://github.com/topics/zwift)
- [Bless Library](https://github.com/kevincar/bless)
- [BLE Protocol Basics](https://www.bluetooth.com/bluetooth-resources/)

## 📝 License

MIT License - Feel free to use, modify, and distribute!

## 🙏 Acknowledgments

- Bluetooth SIG for FTMS specification
- Zwift for creating an awesome platform
- The Python BLE community
- Everyone who's reverse-engineered cycling trainer protocols

---

**Happy Virtual Cycling! 🚴‍♂️💨**

Need help? Open an issue or reach out!

