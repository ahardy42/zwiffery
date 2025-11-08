#!/usr/bin/env python3
"""
BLE Trainer Analyzer
Scan and analyze BLE devices to understand what your real trainer is broadcasting

This tool helps you:
1. Find your real trainer's BLE advertisement
2. Discover service UUIDs it uses
3. Read characteristic values
4. Monitor data being broadcast

Use this to understand what your real trainer does, then mimic it!
"""

import asyncio
import logging
from bleak import BleakScanner, BleakClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Known FTMS UUIDs for reference
FTMS_SERVICE = "00001826-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA = "00002ad2-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_SERVICE = "00001818-0000-1000-8000-00805f9b34fb"


async def scan_for_trainers(duration=10):
    """Scan for BLE devices and identify potential trainers"""
    logger.info(f"Scanning for BLE devices for {duration} seconds...")
    logger.info("Looking for devices with FTMS, Cycling Power, or trainer-like names\n")
    
    devices = await BleakScanner.discover(duration)
    
    trainers = []
    
    print("=" * 80)
    print("DISCOVERED DEVICES")
    print("=" * 80)
    
    for device in devices:
        is_trainer = False
        reasons = []
        
        # Check if it's a likely trainer based on name
        if device.name:
            name_lower = device.name.lower()
            trainer_keywords = ['trainer', 'kickr', 'neo', 'flux', 'direto', 
                              'elite', 'tacx', 'wahoo', 'saris', 'cycleops',
                              'bike', 'smart', 'turbo']
            
            if any(keyword in name_lower for keyword in trainer_keywords):
                is_trainer = True
                reasons.append("trainer-like name")
        
        # Check for FTMS service
        if hasattr(device, 'metadata') and device.metadata and 'uuids' in device.metadata:
            uuids = device.metadata['uuids']
            if FTMS_SERVICE in uuids or '1826' in str(uuids):
                is_trainer = True
                reasons.append("FTMS service")
            if CYCLING_POWER_SERVICE in uuids or '1818' in str(uuids):
                is_trainer = True
                reasons.append("Cycling Power service")
        
        if is_trainer:
            trainers.append(device)
            print(f"\n🚴 POTENTIAL TRAINER FOUND!")
            print(f"   Name: {device.name or 'Unknown'}")
            print(f"   Address: {device.address}")
            print(f"   RSSI: {device.rssi} dBm")
            print(f"   Reasons: {', '.join(reasons)}")
            if hasattr(device, 'metadata') and device.metadata and 'uuids' in device.metadata:
                print(f"   Services: {device.metadata['uuids']}")
        elif device.name:  # Show other named devices too
            print(f"\n   Name: {device.name}")
            print(f"   Address: {device.address}")
            print(f"   RSSI: {device.rssi} dBm")
    
    print("\n" + "=" * 80)
    print(f"Found {len(trainers)} potential trainer(s)")
    print("=" * 80)
    
    return trainers


async def analyze_device(address):
    """Connect to a device and analyze its services and characteristics"""
    logger.info(f"\nConnecting to device: {address}")
    
    try:
        async with BleakClient(address) as client:
            logger.info(f"✓ Connected to {client.address}")
            
            print("\n" + "=" * 80)
            print("DEVICE ANALYSIS")
            print("=" * 80)
            
            # Get all services
            for service in client.services:
                print(f"\n📦 Service: {service.uuid}")
                print(f"   Description: {service.description}")
                
                # Get all characteristics
                for char in service.characteristics:
                    print(f"\n   📋 Characteristic: {char.uuid}")
                    print(f"      Description: {char.description}")
                    print(f"      Properties: {char.properties}")
                    
                    # Try to read value if readable
                    if "read" in char.properties:
                        try:
                            value = await client.read_gatt_char(char.uuid)
                            print(f"      Value (hex): {value.hex()}")
                            print(f"      Value (bytes): {list(value)}")
                            
                            # Try to decode as string
                            try:
                                decoded = value.decode('utf-8')
                                print(f"      Value (string): {decoded}")
                            except:
                                pass
                        except Exception as e:
                            print(f"      Could not read: {e}")
                    
                    # Show if it supports notify/indicate
                    if "notify" in char.properties:
                        print(f"      ⚡ Supports NOTIFY (will broadcast data)")
                    if "indicate" in char.properties:
                        print(f"      ⚡ Supports INDICATE (will send data with ACK)")
            
            print("\n" + "=" * 80)
            print("ANALYSIS COMPLETE")
            print("=" * 80)
            
    except Exception as e:
        logger.error(f"Error analyzing device: {e}")


async def monitor_device(address, duration=30):
    """Connect and monitor notifications from a device"""
    logger.info(f"\nConnecting to device: {address}")
    logger.info(f"Monitoring for {duration} seconds...\n")
    
    notifications_received = {}
    
    def notification_handler(sender, data):
        """Handle incoming notifications"""
        char_uuid = str(sender.uuid) if hasattr(sender, 'uuid') else str(sender)
        
        if char_uuid not in notifications_received:
            notifications_received[char_uuid] = 0
        notifications_received[char_uuid] += 1
        
        print(f"\n📨 Notification from {char_uuid}")
        print(f"   Hex: {data.hex()}")
        print(f"   Bytes: {list(data)}")
        print(f"   Length: {len(data)} bytes")
        
        # Try to decode as Indoor Bike Data
        if len(data) >= 8:
            try:
                import struct
                flags = struct.unpack('<H', data[0:2])[0]
                print(f"   Flags: 0b{flags:016b}")
                
                # Check common flag bits
                if flags & 0x0004:  # Instantaneous Cadence present
                    if len(data) >= 4:
                        cadence = struct.unpack('<H', data[2:4])[0] / 2
                        print(f"   Cadence: {cadence} RPM")
                
                if flags & 0x0040:  # Instantaneous Power present
                    if len(data) >= 6:
                        power = struct.unpack('<h', data[4:6])[0]
                        print(f"   Power: {power} W")
            except:
                pass
    
    try:
        async with BleakClient(address) as client:
            logger.info(f"✓ Connected")
            
            # Subscribe to all notify characteristics
            subscribed = 0
            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties:
                        try:
                            await client.start_notify(char.uuid, notification_handler)
                            logger.info(f"✓ Subscribed to {char.uuid}")
                            subscribed += 1
                        except Exception as e:
                            logger.warning(f"Could not subscribe to {char.uuid}: {e}")
            
            if subscribed == 0:
                logger.warning("No notify characteristics found!")
                return
            
            logger.info(f"\n📡 Listening for notifications... (Press Ctrl+C to stop)\n")
            
            # Monitor for specified duration
            await asyncio.sleep(duration)
            
            print("\n" + "=" * 80)
            print("MONITORING SUMMARY")
            print("=" * 80)
            for char_uuid, count in notifications_received.items():
                print(f"{char_uuid}: {count} notifications")
            print("=" * 80)
            
    except KeyboardInterrupt:
        logger.info("\n\nStopped by user")
    except Exception as e:
        logger.error(f"Error monitoring device: {e}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze BLE trainers to understand their protocol',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan for trainers
  python3 analyze_trainer.py scan
  
  # Analyze a specific device
  python3 analyze_trainer.py analyze AA:BB:CC:DD:EE:FF
  
  # Monitor notifications from device
  python3 analyze_trainer.py monitor AA:BB:CC:DD:EE:FF
  
  # Monitor for 60 seconds
  python3 analyze_trainer.py monitor AA:BB:CC:DD:EE:FF --duration 60
        """
    )
    
    parser.add_argument('command', choices=['scan', 'analyze', 'monitor'],
                       help='Command to run')
    parser.add_argument('address', nargs='?',
                       help='BLE device address (for analyze/monitor commands)')
    parser.add_argument('--duration', type=int, default=30,
                       help='Duration in seconds (default: 30)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("BLE TRAINER ANALYZER")
    print("=" * 80)
    print()
    
    if args.command == 'scan':
        await scan_for_trainers(duration=args.duration)
        print("\n💡 Tip: Use 'analyze' command with device address to see details")
        print("   Example: python3 analyze_trainer.py analyze AA:BB:CC:DD:EE:FF")
        
    elif args.command == 'analyze':
        if not args.address:
            print("❌ Error: address required for analyze command")
            print("   Run 'scan' first to find device address")
            return
        await analyze_device(args.address)
        print("\n💡 Tip: Use 'monitor' command to see live data")
        print("   Example: python3 analyze_trainer.py monitor AA:BB:CC:DD:EE:FF")
        
    elif args.command == 'monitor':
        if not args.address:
            print("❌ Error: address required for monitor command")
            print("   Run 'scan' first to find device address")
            return
        await monitor_device(args.address, duration=args.duration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")

