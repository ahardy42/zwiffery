# 📋 Zwiffery Project Summary

## What Is This Project?

Zwiffery is a virtual smart bike trainer that mimics a real trainer's Bluetooth Low Energy (BLE) signals, allowing you to connect to Zwift without actual hardware. It's perfect for:

- **Testing** - Develop Zwift integrations without physical hardware
- **Learning** - Understand how BLE fitness equipment works
- **Development** - Build your own cycling apps
- **Fun** - Experiment with different power/cadence profiles

## 🗂️ Project Files

### Core Files

| File | Purpose |
|------|---------|
| `virtual_trainer.py` | Main trainer implementation with full FTMS protocol |
| `config.py` | Configuration settings and workout profiles |
| `requirements.txt` | Python dependencies |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Complete project documentation |
| `QUICKSTART.md` | Fast setup guide (5 minutes) |
| `PROTOCOL.md` | Technical FTMS protocol reference |
| `PROJECT_SUMMARY.md` | This file - project overview |

### Utilities

| File | Purpose |
|------|---------|
| `setup_pi.sh` | Automated Raspberry Pi setup script |
| `analyze_trainer.py` | Tool to analyze real trainer BLE data |
| `.gitignore` | Git ignore patterns |

## 🚀 Quick Start (TL;DR)

### On Raspberry Pi:

```bash
cd ~/zwiffery
./setup_pi.sh              # Automated setup
python3 virtual_trainer.py  # Start trainer
# Open Zwift → Pair with "Zwiffery Trainer"
```

### Custom Power/Cadence:

```bash
python3 virtual_trainer.py --power 200 --cadence 90
```

## 🏗️ Architecture

### FTMS Protocol Implementation

The trainer implements the **Fitness Machine Service (FTMS)** protocol:

**Services:**
- Device Information Service (`0x180A`)
- Fitness Machine Service (`0x1826`)

**Key Characteristics:**
- **Indoor Bike Data** (`0x2AD2`) - Broadcasts power, cadence, speed
- **Control Point** (`0x2AD9`) - Receives commands from Zwift
- **Machine Features** (`0x2ACC`) - Advertises capabilities
- **Power/Resistance Ranges** - Tells Zwift what's supported

### Features Implemented

✅ **Power Broadcasting** - Sends realistic power data  
✅ **Cadence Broadcasting** - Sends realistic cadence data  
✅ **Speed Calculation** - Calculates speed based on power  
✅ **ERG Mode Support** - Zwift can set target power  
✅ **SIM Mode Support** - Zwift can send slope/resistance  
✅ **Realistic Variations** - Data has natural fluctuations  
✅ **Control Point Handling** - Responds to all Zwift commands  
✅ **Status Notifications** - Reports trainer status changes  

### Data Flow

```
┌─────────────┐         BLE FTMS Protocol          ┌─────────┐
│   Zwift     │◄────────────────────────────────────┤ Virtual │
│             │                                     │ Trainer │
│             │  1. Request Control (OpCode 0x00)  │         │
│             ├────────────────────────────────────►│         │
│             │◄─ Response: Success ────────────────┤         │
│             │                                     │         │
│             │  2. Start Workout (OpCode 0x07)    │         │
│             ├────────────────────────────────────►│         │
│             │◄─ Response: Success ────────────────┤         │
│             │                                     │         │
│             │◄─ Notify: Power/Cadence (every 1s) ┤         │
│             │◄─ Notify: Power/Cadence ───────────┤         │
│             │◄─ Notify: Power/Cadence ───────────┤         │
│             │                                     │         │
│ ERG Mode:   │  3. Set Target Power: 200W         │         │
│             ├────────────────────────────────────►│         │
│             │◄─ Response: Success ────────────────┤         │
│             │◄─ Notify: Power ramping to 200W ───┤         │
└─────────────┘                                     └─────────┘
```

## 🔬 How to Analyze Your Real Trainer

Use the included analyzer tool to understand what your real trainer broadcasts:

### 1. Scan for Trainers
```bash
python3 analyze_trainer.py scan
```

### 2. Analyze Services
```bash
python3 analyze_trainer.py analyze AA:BB:CC:DD:EE:FF
```

### 3. Monitor Live Data
```bash
python3 analyze_trainer.py monitor AA:BB:CC:DD:EE:FF --duration 60
```

This helps you:
- Identify service UUIDs your trainer uses
- See what characteristics it implements
- Decode the data format it sends
- Understand timing and update rates

## ⚙️ Configuration Options

### Command Line Arguments

```bash
--name "Custom Name"    # Change BLE device name
--power 200            # Set base power (watts)
--cadence 90           # Set base cadence (RPM)
--debug                # Enable debug logging
```

### config.py Settings

```python
# Trainer identity
TRAINER_NAME = "Zwiffery Trainer"

# Default values
DEFAULT_POWER = 150        # Base power
DEFAULT_CADENCE = 85       # Base cadence

# Realism settings
POWER_VARIATION = 15       # +/- watts
CADENCE_VARIATION = 5      # +/- RPM

# ERG mode responsiveness
ERG_MODE_RESPONSE_RATE = 0.1  # How fast to reach target

# Workout profiles
WORKOUT_PROFILES = {
    "easy": {"power": 100, "cadence": 70},
    "moderate": {"power": 150, "cadence": 85},
    "hard": {"power": 250, "cadence": 95},
    "sprint": {"power": 400, "cadence": 110}
}
```

## 🧪 Testing Strategy

### 1. Unit Testing (Without Zwift)

**Test BLE advertising:**
```bash
# On Linux
sudo hcitool lescan

# Should show "Zwiffery Trainer"
```

**Test with BLE app:**
- Download nRF Connect (iOS/Android)
- Scan for devices
- Connect to "Zwiffery Trainer"
- Explore services (should see 0x1826)
- Subscribe to Indoor Bike Data
- Watch notifications

### 2. Integration Testing (With Zwift)

**Test pairing:**
1. Start virtual trainer
2. Open Zwift
3. Go to pairing screen
4. Look for "Zwiffery Trainer"
5. Should appear as both Power and Cadence source

**Test free ride:**
1. Pair trainer
2. Start free ride
3. Verify power/cadence appears in Zwift
4. Change base values, see Zwift update

**Test ERG mode:**
1. Start an ERG workout in Zwift
2. Watch logs for "Set Target Power" commands
3. Verify trainer adjusts power to match target
4. Check Zwift shows correct power

**Test SIM mode:**
1. Do a free ride with hills
2. Watch logs for "Set Indoor Bike Simulation Parameters"
3. Verify resistance commands received
4. Zwift should show grade percentage

### 3. Performance Testing

**Stability test:**
```bash
# Run for extended period
python3 virtual_trainer.py &
# Let run for 1+ hours, check for crashes/disconnects
```

**Connection test:**
```bash
# Test reconnection
# Start trainer → connect Zwift → stop trainer → restart → reconnect
```

## 🐛 Common Issues & Solutions

### Issue: Permission Denied

**Solution:**
```bash
sudo python3 virtual_trainer.py
# Or set capabilities:
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
```

### Issue: Trainer Not Found in Zwift

**Causes:**
- Bluetooth not enabled
- Another app using the trainer
- BLE advertising failed

**Solutions:**
```bash
sudo systemctl restart bluetooth
sudo hciconfig hci0 up
# Check if advertising:
sudo hcitool lescan
```

### Issue: Zwift Disconnects

**Causes:**
- Update interval too slow/fast
- Missing responses to control point
- BLE adapter issues

**Solutions:**
- Check logs for errors
- Verify 1-second update interval
- Try different BLE adapter

### Issue: Power/Cadence Not Updating

**Causes:**
- Notification subscription failed
- Flag bits incorrect
- Data encoding wrong

**Solutions:**
- Enable debug mode: `--debug`
- Check notification count in logs
- Verify flags match data sent

## 📊 Understanding the Logs

### Normal Operation:
```
INFO - Starting Virtual Trainer: Zwiffery Trainer
INFO - ✓ BLE advertising started
DEBUG - Broadcasting - Power: 152.3W, Cadence: 86.2rpm
```

### When Zwift Connects:
```
INFO - Control Point OpCode: 0x00
INFO - Zwift requested control
INFO - Sending control point response: 800001
```

### ERG Mode:
```
INFO - Control Point OpCode: 0x05
INFO - Zwift set target power (ERG mode): 200W
DEBUG - Broadcasting - Power: 185.4W (ramping to 200W)
```

### SIM Mode:
```
INFO - Control Point OpCode: 0x11
INFO - Zwift SIM mode - Grade: 5.00%, Wind: 0.00m/s
```

## 🔮 Future Enhancement Ideas

### Additional Features:
- ❑ Heart Rate Service implementation
- ❑ Steering support (Zwift Play simulation)
- ❑ Web dashboard for real-time control
- ❑ ANT+ broadcasting (requires hardware)
- ❑ Workout file playback (.erg, .mrc files)
- ❑ Multiple trainer profiles
- ❑ Data logging to CSV/SQLite
- ❑ Gradient resistance simulation
- ❑ Group ride mode (multiple trainers)

### Advanced Features:
- ❑ Physics-based power calculation
- ❑ Fatigue modeling (power decreases over time)
- ❑ Sprint detection and response
- ❑ Auto-calibration simulation
- ❑ Temperature simulation
- ❑ Wear/maintenance simulation

### Integration:
- ❑ TrainerRoad integration
- ❑ Rouvy integration
- ❑ Golden Cheetah integration
- ❑ Strava webhook support
- ❑ MQTT/Home Assistant integration

## 📚 Learning Resources

### BLE Protocol:
- [Bluetooth FTMS Spec](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/)
- [BLE GATT Tutorial](https://www.bluetooth.com/bluetooth-resources/)
- See `PROTOCOL.md` for detailed breakdown

### Python BLE:
- [Bless Documentation](https://github.com/kevincar/bless)
- [Bleak Documentation](https://bleak.readthedocs.io/)
- [Python asyncio Guide](https://docs.python.org/3/library/asyncio.html)

### Zwift API:
- [Zwift API Community Docs](https://github.com/topics/zwift-api)
- Search YouTube: "Zwift protocol reverse engineering"

## 🎯 Success Criteria

Your virtual trainer is working correctly if:

✅ Shows up in Zwift pairing screen  
✅ Can be paired as Power and Cadence source  
✅ Power and cadence values update in Zwift  
✅ ERG workouts control your power target  
✅ Free rides show realistic variations  
✅ Connection is stable for 60+ minutes  
✅ Zwift sees the trainer as a standard FTMS device  

## 🤝 Contributing

Want to improve Zwiffery?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

**Areas that need help:**
- Testing on different platforms
- Additional protocol support (ANT+)
- UI/Dashboard development
- Documentation improvements
- Bug fixes

## ⚖️ Legal & Ethics

**Intended Use:**
- ✅ Personal testing and development
- ✅ Learning BLE protocols
- ✅ Building training apps
- ✅ Research and education

**NOT Intended For:**
- ❌ Cheating in Zwift races
- ❌ Fraudulent performance claims
- ❌ Violating Zwift Terms of Service
- ❌ Commercial use without proper testing

**Disclaimer:**
This software is provided "as-is" for educational purposes. Use responsibly and ethically. Don't use this to cheat or misrepresent your cycling performance.

## 📞 Support

**Need Help?**
1. Check `README.md` for detailed documentation
2. Review `QUICKSTART.md` for setup issues
3. Read `PROTOCOL.md` for protocol questions
4. Open an issue on GitHub
5. Check logs with `--debug` flag

**Found a Bug?**
1. Enable debug logging: `--debug`
2. Capture full error output
3. Note your system (OS, Python version)
4. Note steps to reproduce
5. Open an issue with details

## 🏆 Acknowledgments

**Thanks to:**
- Bluetooth SIG for FTMS specification
- Zwift for creating an amazing platform
- Python BLE community (Bless, Bleak authors)
- Everyone who's reverse-engineered cycling protocols
- The open-source community

## 📄 License

MIT License - See LICENSE file for details

Free to use, modify, and distribute!

---

**Built with ❤️ for the cycling community**

*Version 1.0 - November 2025*

