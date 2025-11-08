# 🚀 Quick Start Guide

Get your virtual trainer running in 5 minutes!

## For Raspberry Pi Users

### 1️⃣ Get the Files

```bash
cd ~
# Copy all project files to ~/zwiffery
cd zwiffery
```

### 2️⃣ Run Setup Script

```bash
chmod +x setup_pi.sh
./setup_pi.sh
```

The script will:
- ✅ Install all dependencies
- ✅ Set up Bluetooth
- ✅ Configure permissions
- ✅ Create virtual environment

### 3️⃣ Start the Trainer

```bash
# If you chose capability method:
python3 virtual_trainer.py

# If you chose sudo method:
sudo python3 virtual_trainer.py
```

### 4️⃣ Connect to Zwift

1. Open Zwift
2. Go to pairing screen
3. Look for **"Zwiffery Trainer"**
4. Pair it as **Power Source** and **Cadence**
5. Ride! 🚴

---

## For Linux Users (Non-Raspberry Pi)

### Quick Install

```bash
# Install dependencies
sudo apt install bluetooth bluez python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt

# Run trainer
sudo python3 virtual_trainer.py
```

---

## For macOS Users (Limited Support)

⚠️ **Note:** macOS has limited BLE peripheral support. Raspberry Pi recommended.

```bash
# Install dependencies
pip3 install -r requirements.txt

# Try running (may not work due to macOS BLE restrictions)
sudo python3 virtual_trainer.py
```

If macOS doesn't work, use a Raspberry Pi or Linux VM.

---

## Command Line Options

### Basic Usage
```bash
python3 virtual_trainer.py
```

### Custom Power/Cadence
```bash
python3 virtual_trainer.py --power 200 --cadence 90
```

### Custom Device Name
```bash
python3 virtual_trainer.py --name "My Custom Trainer"
```

### Debug Mode
```bash
python3 virtual_trainer.py --debug
```

### All Options
```bash
python3 virtual_trainer.py --help
```

---

## Testing Without Zwift

Use a BLE scanner app to verify the trainer is working:

**Mobile Apps:**
- **nRF Connect** (iOS/Android) - Highly recommended
- **LightBlue** (iOS/macOS)

**What to look for:**
- Device Name: "Zwiffery Trainer"
- Service UUID: `0x1826` (Fitness Machine Service)
- Characteristics: Indoor Bike Data, Control Point

---

## Common Issues

### "Permission Denied" Error

**Solution:**
```bash
sudo python3 virtual_trainer.py
```

Or set capabilities:
```bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
```

### Trainer Not Showing in Zwift

**Solutions:**
1. Restart Bluetooth:
   ```bash
   sudo systemctl restart bluetooth
   ```

2. Check if trainer is advertising:
   ```bash
   sudo hcitool lescan
   ```

3. Make sure no other devices are paired to it

4. Try renaming:
   ```bash
   python3 virtual_trainer.py --name "TestTrainer"
   ```

### Module Not Found

**Solution:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## Auto-Start on Boot (Optional)

Want the trainer to start automatically when Pi boots?

### During Setup:
The `setup_pi.sh` script asks if you want auto-start.

### Manual Setup:
```bash
sudo systemctl enable zwiffery
sudo systemctl start zwiffery
```

### Check Status:
```bash
sudo systemctl status zwiffery
```

### View Logs:
```bash
sudo journalctl -u zwiffery -f
```

---

## Next Steps

- 📖 Read **README.md** for detailed documentation
- ⚙️ Edit **config.py** to customize behavior
- 🧪 Test with different power/cadence values
- 🔬 Analyze real trainer data with your actual trainer

---

## Need Help?

Check **README.md** for:
- Detailed troubleshooting
- Understanding the FTMS protocol
- How ERG mode works
- Extending the code

---

**Happy Riding! 🚴‍♂️💨**

