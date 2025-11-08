# 📡 FTMS Protocol Reference

This document explains the Fitness Machine Service (FTMS) protocol used by smart trainers to communicate with apps like Zwift.

## Overview

FTMS is a Bluetooth SIG standard protocol that defines how fitness equipment communicates over BLE. It's standardized, meaning most modern smart trainers use the same protocol.

## Service UUID

- **Service:** `0x1826` (Fitness Machine Service)

## Key Characteristics

### 1. Fitness Machine Feature (0x2ACC)

**Purpose:** Advertises what features the trainer supports

**Properties:** Read

**Value:** 8 bytes describing capabilities

**Example:**
```
Features bitmap (bytes 0-3):
  Bit 0: Average Speed Supported
  Bit 1: Cadence Supported
  Bit 2: Total Distance Supported
  Bit 7: Resistance Level Supported
  Bit 14: Power Measurement Supported

Target Settings bitmap (bytes 4-7):
  Bit 14: Indoor Bike Simulation Parameters Supported
```

### 2. Indoor Bike Data (0x2AD2)

**Purpose:** Broadcasts real-time cycling data to Zwift

**Properties:** Notify

**Update Rate:** Typically 1 Hz (once per second)

**Format:**
```
Byte 0-1: Flags (uint16, little-endian)
Byte 2-3: Instantaneous Speed (uint16, 0.01 km/h resolution) [optional]
Byte 4-5: Instantaneous Cadence (uint16, 0.5 RPM resolution) [optional]
Byte 6-7: Instantaneous Power (sint16, 1 W resolution) [optional]
... additional fields based on flags
```

**Flag Bits:**
- Bit 2: Instantaneous Cadence present
- Bit 6: Instantaneous Power present
- Bit 9: Heart Rate present
- Bit 11: Elapsed Time present

**Example Data Packet:**

```
44 00 E8 03 AA 00 96 00
```

Decoded:
- Flags: `0x0044` (0b0000000001000100)
  - Bit 2 set: Cadence present
  - Bit 6 set: Power present
- Speed: `0x03E8` = 1000 → 10.00 km/h
- Cadence: `0x00AA` = 170 → 85.0 RPM (170 * 0.5)
- Power: `0x0096` = 150 → 150 W

### 3. Fitness Machine Control Point (0x2AD9)

**Purpose:** Receives commands from Zwift

**Properties:** Write, Indicate

**Format:** Variable length, first byte is OpCode

**Common OpCodes:**

| OpCode | Name | Description |
|--------|------|-------------|
| 0x00 | Request Control | Zwift requests permission to control trainer |
| 0x01 | Reset | Reset trainer state |
| 0x04 | Set Target Resistance Level | Set resistance (0-100%) |
| 0x05 | Set Target Power | Set target power for ERG mode |
| 0x07 | Start or Resume | Start workout |
| 0x08 | Stop or Pause | Pause workout |
| 0x11 | Set Indoor Bike Simulation Parameters | SIM mode (slope, wind, etc.) |

**Response Format:**
```
Byte 0: 0x80 (Response OpCode)
Byte 1: Request OpCode being responded to
Byte 2: Result Code
  0x01 = Success
  0x02 = OpCode Not Supported
  0x03 = Invalid Parameter
  0x04 = Operation Failed
```

**Example: Set Target Power (ERG Mode)**

Command from Zwift:
```
05 C8 00
```
- OpCode: 0x05 (Set Target Power)
- Power: 0x00C8 = 200 W

Response from Trainer:
```
80 05 01
```
- Response OpCode: 0x80
- Request OpCode: 0x05
- Result: 0x01 (Success)

### 4. Set Indoor Bike Simulation Parameters (OpCode 0x11)

**Purpose:** Used in SIM mode when Zwift wants to simulate terrain

**Format:**
```
Byte 0: 0x11 (OpCode)
Byte 1-2: Wind Speed (sint16, m/s * 1000)
Byte 3-4: Grade (sint16, percentage * 100)
Byte 5: Rolling Resistance Coefficient (uint8, coefficient * 10000)
Byte 6: Wind Resistance Coefficient (uint8, kg/m * 100)
```

**Example:**
```
11 00 00 F4 01 50 50
```
- OpCode: 0x11
- Wind Speed: 0x0000 = 0 m/s
- Grade: 0x01F4 = 500 → 5.00% incline
- Rolling Resistance: 0x50 = 80 → 0.0080
- Wind Resistance: 0x50 = 80 → 0.80 kg/m

### 5. Fitness Machine Status (0x2ADA)

**Purpose:** Notify Zwift of status changes

**Properties:** Notify

**Format:**
```
Byte 0: OpCode
Byte 1+: Parameters (varies by OpCode)
```

**Status OpCodes:**
- 0x01: Reset
- 0x02: Stopped or Paused by User
- 0x04: Stopped by Safety Key
- 0x07: Started or Resumed by User

### 6. Supported Resistance Level Range (0x2AD6)

**Purpose:** Tells Zwift the resistance range

**Properties:** Read

**Format:**
```
Byte 0-1: Minimum Resistance (sint16, 0.1% resolution)
Byte 2-3: Maximum Resistance (sint16, 0.1% resolution)
Byte 4-5: Minimum Increment (uint16, 0.1% resolution)
```

**Example:**
```
00 00 E8 03 0A 00
```
- Min: 0 (0%)
- Max: 1000 (100%)
- Increment: 10 (1%)

### 7. Supported Power Range (0x2AD8)

**Purpose:** Tells Zwift the power range

**Properties:** Read

**Format:**
```
Byte 0-1: Minimum Power (sint16, watts)
Byte 2-3: Maximum Power (sint16, watts)
Byte 4-5: Minimum Increment (uint16, watts)
```

**Example:**
```
00 00 D0 07 01 00
```
- Min: 0 W
- Max: 2000 W
- Increment: 1 W

## Zwift Connection Flow

### 1. Discovery Phase
```
Trainer → BLE Advertisement
  - Name: "Smart Trainer"
  - Services: [0x1826]
```

### 2. Connection Phase
```
Zwift → Connect to trainer
Zwift → Read Fitness Machine Feature (0x2ACC)
Zwift → Read Supported Power Range (0x2AD8)
Zwift → Read Supported Resistance Range (0x2AD6)
Zwift → Subscribe to Indoor Bike Data (0x2AD2)
Zwift → Subscribe to Fitness Machine Status (0x2ADA)
```

### 3. Control Phase
```
Zwift → Write Control Point: Request Control (0x00)
Trainer → Indicate Response: Success (0x80 0x00 0x01)

Zwift → Write Control Point: Start (0x07)
Trainer → Indicate Response: Success (0x80 0x07 0x01)
```

### 4. Data Phase (Continuous)
```
Trainer → Notify Indoor Bike Data (every 1 second)
  - Power, Cadence, Speed

Zwift → Write Control Point: Set Target Power (ERG mode)
  OR
Zwift → Write Control Point: Set Simulation Parameters (SIM mode)

Trainer → Indicate Response: Success
```

### 5. Workout Phase (ERG Mode Example)
```
Zwift → Set Target Power: 200W (0x05 0xC8 0x00)
Trainer → Response: Success (0x80 0x05 0x01)
Trainer → Notify: Power gradually increases to 200W

... 2 minutes later ...

Zwift → Set Target Power: 250W (0x05 0xFA 0x00)
Trainer → Response: Success
Trainer → Notify: Power gradually increases to 250W
```

### 6. Workout Phase (SIM Mode Example)
```
Zwift → Set Simulation: 5% grade, no wind
  (0x11 0x00 0x00 0xF4 0x01 0x50 0x50)
Trainer → Response: Success
Trainer → Adjusts resistance to simulate 5% climb

... rider crests hill ...

Zwift → Set Simulation: -2% grade (descent)
  (0x11 0x00 0x00 0x38 0xFF 0x50 0x50)
Trainer → Response: Success
Trainer → Reduces resistance for descent
```

## Data Encoding Examples

### Power: 150W
```
Power (sint16): 150
Hex: 96 00 (little-endian)
```

### Cadence: 85 RPM
```
Cadence value: 85 * 2 = 170 (0.5 RPM resolution)
Cadence (uint16): 170
Hex: AA 00 (little-endian)
```

### Speed: 25.5 km/h
```
Speed value: 25.5 * 100 = 2550 (0.01 km/h resolution)
Speed (uint16): 2550
Hex: F6 09 (little-endian)
```

## Tips for Implementation

1. **Always use little-endian byte order** - Multi-byte values are sent least significant byte first

2. **Update rate is important** - Most trainers send data at 1 Hz (once per second). Too fast or too slow may confuse Zwift.

3. **Respond to control point commands** - Always send a response (0x80) when Zwift writes to control point

4. **ERG mode transition** - When Zwift sets a new target power, gradually ramp to that power over 2-3 seconds (don't jump instantly)

5. **Realistic variations** - Add small random variations to power (±5W) and cadence (±2 RPM) to look more realistic

6. **Flag bits matter** - Set the correct flags in Indoor Bike Data to indicate which fields are present

7. **Service must be in advertisement** - Include FTMS UUID (0x1826) in BLE advertisement so Zwift can find your trainer

## Additional Services (Optional)

### Cycling Power Service (0x1818)
Alternative to FTMS for power-only meters. Most trainers use FTMS instead.

### Heart Rate Service (0x180D)
Can broadcast heart rate data separately.

### Device Information Service (0x180A)
Provides manufacturer name, model number, serial number, etc.

## References

- [Bluetooth FTMS Specification](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/)
- [GATT Specification Supplement](https://www.bluetooth.com/specifications/gss/)
- [Assigned Numbers](https://www.bluetooth.com/specifications/assigned-numbers/)

## Debugging Tips

### Use nRF Connect App
1. Scan for your trainer
2. Connect and explore services
3. Subscribe to Indoor Bike Data
4. Watch notifications in real-time
5. Write commands to Control Point

### Use btmon on Linux
```bash
sudo btmon
# Then connect Zwift to your trainer
# Watch all BLE packets in real-time
```

### Log Everything
Enable debug logging in your code to see:
- When Zwift connects
- What it reads
- What commands it sends
- What responses you send
- What data you notify

This helps identify protocol issues quickly!

