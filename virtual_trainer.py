#!/usr/bin/env python3
"""
Virtual Smart Bike Trainer - Zwift BLE Simulator
Emulates a smart trainer using FTMS (Fitness Machine Service) protocol
"""

import asyncio
import logging
import struct
import time
import random
import sys
import threading
from typing import Optional
from bless import BlessServer, BlessGATTCharacteristic, GATTCharacteristicProperties, GATTAttributePermissions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# BLE Service and Characteristic UUIDs (FTMS Protocol)
FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
FITNESS_MACHINE_FEATURE_UUID = "00002acc-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
TRAINING_STATUS_UUID = "00002ad3-0000-1000-8000-00805f9b34fb"
SUPPORTED_RESISTANCE_LEVEL_RANGE_UUID = "00002ad6-0000-1000-8000-00805f9b34fb"
SUPPORTED_POWER_RANGE_UUID = "00002ad8-0000-1000-8000-00805f9b34fb"
FITNESS_MACHINE_CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"
FITNESS_MACHINE_STATUS_UUID = "00002ada-0000-1000-8000-00805f9b34fb"

# Device Information Service
DEVICE_INFO_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
MANUFACTURER_NAME_UUID = "00002a29-0000-1000-8000-00805f9b34fb"
MODEL_NUMBER_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
HARDWARE_REVISION_UUID = "00002a27-0000-1000-8000-00805f9b34fb"
FIRMWARE_REVISION_UUID = "00002a26-0000-1000-8000-00805f9b34fb"
SERIAL_NUMBER_UUID = "00002a25-0000-1000-8000-00805f9b34fb"

# Cycling Power Service
CYCLING_POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_MEASUREMENT_UUID = "00002a63-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_FEATURE_UUID = "00002a65-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_CONTROL_POINT_UUID = "00002a66-0000-1000-8000-00805f9b34fb"
SENSOR_LOCATION_UUID = "00002a5d-0000-1000-8000-00805f9b34fb"


class VirtualTrainer:
    """Virtual Smart Trainer that emulates FTMS protocol for Zwift"""
    
    def __init__(self, name: str = "Zwiffery Trainer"):
        self.name = name
        self.server: Optional[BlessServer] = None
        
        # Trainer state
        self.power = 0  # Start at 0W - use 's' command to start
        self.cadence = 85  # RPM
        self.speed = 25.0  # km/h
        self.heart_rate = 140  # BPM (optional)
        self.target_resistance = 0  # Target resistance level from Zwift (ERG mode)
        self.current_resistance = 0  # Current resistance level
        self.is_running = False
        
        # Simulation parameters
        self.base_power = 0  # Start at 0W
        self.base_cadence = 85
        self.power_variation = 15
        self.cadence_variation = 5
        
        # ERG mode settings
        self.erg_mode_enabled = False
        self.target_power = 0
        
        # Default start power for keyboard commands
        self.default_start_power = 150
        
    async def setup_server(self):
        """Initialize BLE GATT server"""
        logger.info(f"Setting up BLE server: {self.name}")
        
        # Create BLE server
        self.server = BlessServer(name=self.name, name_overwrite=True)
        
        # Add FTMS Service FIRST (most important for Zwift compatibility)
        await self.server.add_new_service(FTMS_SERVICE_UUID)
        
        # Fitness Machine Feature (indicates capabilities)
        feature_bytes = self._encode_fitness_machine_features()
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            FITNESS_MACHINE_FEATURE_UUID,
            GATTCharacteristicProperties.read,
            feature_bytes,
            GATTAttributePermissions.readable
        )
        
        # Indoor Bike Data (notifies power, cadence, speed)
        # Initialize with default data (will be updated in the update loop)
        initial_bike_data = self._encode_indoor_bike_data()
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            INDOOR_BIKE_DATA_UUID,
            GATTCharacteristicProperties.notify,
            initial_bike_data,
            GATTAttributePermissions.readable
        )
        
        # Supported Resistance Level Range
        resistance_range = struct.pack('<hhh', 0, 100, 1)  # min, max, increment
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            SUPPORTED_RESISTANCE_LEVEL_RANGE_UUID,
            GATTCharacteristicProperties.read,
            resistance_range,
            GATTAttributePermissions.readable
        )
        
        # Supported Power Range
        power_range = struct.pack('<hhh', 0, 2000, 1)  # min 0W, max 2000W, 1W increments
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            SUPPORTED_POWER_RANGE_UUID,
            GATTCharacteristicProperties.read,
            power_range,
            GATTAttributePermissions.readable
        )
        
        # Fitness Machine Control Point (receives commands from Zwift)
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            FITNESS_MACHINE_CONTROL_POINT_UUID,
            GATTCharacteristicProperties.write | GATTCharacteristicProperties.indicate,
            None,
            GATTAttributePermissions.writeable
        )
        
        # Training Status (read and notify)
        training_status = bytes([0x00, 0x00])  # [0, 0] as per real trainer
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            TRAINING_STATUS_UUID,
            GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
            training_status,
            GATTAttributePermissions.readable
        )
        
        # Fitness Machine Status
        # Initialize with default status (stopped, no error)
        status_data = struct.pack('<B', 0x00)  # Status: Stopped
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            FITNESS_MACHINE_STATUS_UUID,
            GATTCharacteristicProperties.notify,
            status_data,
            GATTAttributePermissions.readable
        )
        
        # Add Cycling Power Service
        await self.server.add_new_service(CYCLING_POWER_SERVICE_UUID)
        
        # Add Device Information Service (add last, as it's less critical)
        await self.server.add_new_service(DEVICE_INFO_SERVICE_UUID)
        
        # Manufacturer Name
        await self.server.add_new_characteristic(
            DEVICE_INFO_SERVICE_UUID,
            MANUFACTURER_NAME_UUID,
            GATTCharacteristicProperties.read,
            b"Zwiffery Labs",
            GATTAttributePermissions.readable
        )
        
        # Model Number
        await self.server.add_new_characteristic(
            DEVICE_INFO_SERVICE_UUID,
            MODEL_NUMBER_UUID,
            GATTCharacteristicProperties.read,
            b"Virtual Trainer v1.0",
            GATTAttributePermissions.readable
        )
        
        # Hardware Revision
        await self.server.add_new_characteristic(
            DEVICE_INFO_SERVICE_UUID,
            HARDWARE_REVISION_UUID,
            GATTCharacteristicProperties.read,
            b"1",
            GATTAttributePermissions.readable
        )
        
        # Firmware Revision
        await self.server.add_new_characteristic(
            DEVICE_INFO_SERVICE_UUID,
            FIRMWARE_REVISION_UUID,
            GATTCharacteristicProperties.read,
            b"1.0.0",
            GATTAttributePermissions.readable
        )
        
        # Serial Number
        await self.server.add_new_characteristic(
            DEVICE_INFO_SERVICE_UUID,
            SERIAL_NUMBER_UUID,
            GATTCharacteristicProperties.read,
            b"ZWIF001",
            GATTAttributePermissions.readable
        )
        
        # Cycling Power Measurement (notify)
        initial_power_data = self._encode_cycling_power_measurement()
        await self.server.add_new_characteristic(
            CYCLING_POWER_SERVICE_UUID,
            CYCLING_POWER_MEASUREMENT_UUID,
            GATTCharacteristicProperties.notify,
            initial_power_data,
            GATTAttributePermissions.readable
        )
        
        # Cycling Power Feature (read)
        # Real trainer value: 0e12 = [14, 18]
        power_feature = bytes([0x0e, 0x12])
        await self.server.add_new_characteristic(
            CYCLING_POWER_SERVICE_UUID,
            CYCLING_POWER_FEATURE_UUID,
            GATTCharacteristicProperties.read,
            power_feature,
            GATTAttributePermissions.readable
        )
        
        # Cycling Power Control Point (write, indicate)
        await self.server.add_new_characteristic(
            CYCLING_POWER_SERVICE_UUID,
            CYCLING_POWER_CONTROL_POINT_UUID,
            GATTCharacteristicProperties.write | GATTCharacteristicProperties.indicate,
            None,
            GATTAttributePermissions.writeable
        )
        
        # Sensor Location (read)
        # Real trainer value: 00 = [0] (Other)
        sensor_location = bytes([0x00])
        await self.server.add_new_characteristic(
            CYCLING_POWER_SERVICE_UUID,
            SENSOR_LOCATION_UUID,
            GATTCharacteristicProperties.read,
            sensor_location,
            GATTAttributePermissions.readable
        )
        
        # Set up write callback for control point
        def control_point_write_handler(characteristic: BlessGATTCharacteristic, value: bytearray):
            logger.info(f"Control Point Write: {value.hex()}")
            self._handle_control_point_command(value)
        
        self.server.get_characteristic(FITNESS_MACHINE_CONTROL_POINT_UUID).value = bytearray()
        
        # Set up read callbacks for all readable characteristics
        def read_handler(characteristic: BlessGATTCharacteristic) -> bytes:
            """Handle read requests - return the current value of the characteristic"""
            char_uuid = characteristic.uuid
            char = self.server.get_characteristic(char_uuid)
            if char and char.value is not None:
                return bytes(char.value)
            return b''
        
        # Set read callback for all readable characteristics
        self.server.read_request_func = read_handler
        
        # Verify services were added correctly
        try:
            # Try to get services to verify they exist
            dev_info_char = self.server.get_characteristic(MANUFACTURER_NAME_UUID)
            ftms_char = self.server.get_characteristic(FITNESS_MACHINE_FEATURE_UUID)
            power_char = self.server.get_characteristic(CYCLING_POWER_MEASUREMENT_UUID)
            
            logger.info("✓ Verified services are registered:")
            logger.info(f"  - Device Information Service: {DEVICE_INFO_SERVICE_UUID} ({len([c for c in [dev_info_char] if c])} characteristics)")
            logger.info(f"  - Fitness Machine Service (FTMS): {FTMS_SERVICE_UUID} ({len([c for c in [ftms_char] if c])} characteristics)")
            logger.info(f"  - Cycling Power Service: {CYCLING_POWER_SERVICE_UUID} ({len([c for c in [power_char] if c])} characteristics)")
        except Exception as e:
            logger.warning(f"Could not verify services: {e}")
        
        logger.info("BLE GATT server setup complete")
    
    def _encode_fitness_machine_features(self) -> bytes:
        """Encode Fitness Machine Feature characteristic
        
        Matches real Wahoo trainer: 034000000c600000
        Value: [3, 64, 0, 0, 12, 96, 0, 0]
        """
        # Real trainer value: 034000000c600000
        # This is [3, 64, 0, 0, 12, 96, 0, 0] in little-endian
        # Features: 0x00004003, Target Features: 0x0000600c
        return bytes([0x03, 0x40, 0x00, 0x00, 0x0c, 0x60, 0x00, 0x00])
    
    def _encode_indoor_bike_data(self) -> bytes:
        """Encode Indoor Bike Data characteristic for notifications
        
        Format (all little-endian):
        Flags (2 bytes)
        Instantaneous Speed (uint16, 0.01 km/h resolution) - optional
        Instantaneous Cadence (uint16, 0.5 rpm resolution) - optional
        Instantaneous Power (sint16, 1 watt resolution) - optional
        """
        # Flags indicating which fields are present
        # Bit 0: More data (0 = no more data)
        # Bit 1: Average Speed present
        # Bit 2: Instantaneous Cadence present
        # Bit 3: Average Cadence present
        # Bit 4: Total Distance present
        # Bit 5: Resistance Level present
        # Bit 6: Instantaneous Power present
        # Bit 7: Average Power present
        # Bit 8: Expended Energy present
        # Bit 9: Heart Rate present
        # Bit 10: Metabolic Equivalent present
        # Bit 11: Elapsed Time present
        # Bit 12: Remaining Time present
        
        flags = 0b0000010001000100  # Instantaneous Cadence (bit 2) + Instantaneous Power (bit 6)
        
        # Encode values
        speed_uint16 = int(self.speed * 100)  # Convert km/h to 0.01 km/h units
        cadence_uint16 = int(self.cadence * 2)  # Convert rpm to 0.5 rpm units
        power_sint16 = int(self.power)
        
        data = struct.pack('<HHHh', flags, speed_uint16, cadence_uint16, power_sint16)
        return data
    
    def _encode_cycling_power_measurement(self) -> bytes:
        """Encode Cycling Power Measurement characteristic for notifications
        
        Format (all little-endian):
        Flags (2 bytes)
        Instantaneous Power (sint16, 1 watt resolution)
        Optional: Cumulative Wheel Revolutions, Last Wheel Event Time, etc.
        """
        # Flags indicating which fields are present
        # Bit 0: Pedal Power Balance Present
        # Bit 1: Pedal Power Balance Reference (0 = unknown)
        # Bit 2: Accumulated Torque Present
        # Bit 3: Accumulated Torque Source (0 = wheel)
        # Bit 4: Wheel Revolution Data Present
        # Bit 5: Crank Revolution Data Present
        # Bit 6: Extreme Force Magnitudes Present
        # Bit 7: Extreme Torque Magnitudes Present
        # Bit 8: Extreme Angles Present
        # Bit 9: Top Dead Spot Angle Present
        # Bit 10: Bottom Dead Spot Angle Present
        # Bit 11: Accumulated Energy Present
        # Bit 12: Offset Compensation Indicator
        
        # Simple flags: just instantaneous power
        flags = 0b0000000000000000  # No optional fields, just power
        
        # Encode instantaneous power (sint16, 1W resolution)
        power_sint16 = int(self.power)
        
        data = struct.pack('<Hh', flags, power_sint16)
        return data
    
    def _handle_control_point_command(self, data: bytearray):
        """Handle commands from Zwift via Fitness Machine Control Point
        
        OpCodes:
        0x00: Request Control
        0x01: Reset
        0x02: Set Target Speed
        0x03: Set Target Inclination
        0x04: Set Target Resistance Level
        0x05: Set Target Power
        0x07: Start or Resume
        0x08: Stop or Pause
        0x11: Set Indoor Bike Simulation Parameters
        """
        if len(data) == 0:
            return
        
        opcode = data[0]
        logger.info(f"Control Point OpCode: 0x{opcode:02x}")
        
        if opcode == 0x00:  # Request Control
            logger.info("Zwift requested control")
            self._send_control_point_response(opcode, 0x01)  # Success
            
        elif opcode == 0x01:  # Reset
            logger.info("Zwift requested reset")
            self.power = self.base_power
            self.cadence = self.base_cadence
            self._send_control_point_response(opcode, 0x01)
            
        elif opcode == 0x04:  # Set Target Resistance Level
            if len(data) >= 2:
                resistance = struct.unpack('<b', data[1:2])[0]
                self.target_resistance = resistance
                logger.info(f"Zwift set target resistance: {resistance}%")
                self._send_control_point_response(opcode, 0x01)
                
        elif opcode == 0x05:  # Set Target Power (ERG mode)
            if len(data) >= 3:
                target_power = struct.unpack('<h', data[1:3])[0]
                self.target_power = target_power
                self.erg_mode_enabled = True
                logger.info(f"Zwift set target power (ERG mode): {target_power}W")
                self._send_control_point_response(opcode, 0x01)
                
        elif opcode == 0x07:  # Start or Resume
            logger.info("Zwift started workout")
            self.is_running = True
            self._send_control_point_response(opcode, 0x01)
            
        elif opcode == 0x08:  # Stop or Pause
            logger.info("Zwift paused workout")
            self.is_running = False
            self._send_control_point_response(opcode, 0x01)
            
        elif opcode == 0x11:  # Set Indoor Bike Simulation Parameters
            # This is sent during SIM mode (slope simulation)
            if len(data) >= 7:
                wind_speed = struct.unpack('<h', data[1:3])[0]  # m/s * 1000
                grade = struct.unpack('<h', data[3:5])[0]  # percentage * 100
                crr = struct.unpack('<B', data[5:6])[0]  # rolling resistance * 10000
                cw = struct.unpack('<B', data[6:7])[0]  # wind resistance * 100
                logger.info(f"Zwift SIM mode - Grade: {grade/100}%, Wind: {wind_speed/1000}m/s")
                # In a real trainer, you'd adjust resistance based on these parameters
                self._send_control_point_response(opcode, 0x01)
        else:
            logger.warning(f"Unknown control point opcode: 0x{opcode:02x}")
            self._send_control_point_response(opcode, 0x02)  # OpCode not supported
    
    def _send_control_point_response(self, request_opcode: int, result_code: int):
        """Send response to control point command
        
        Response format:
        0x80 (Response Code)
        Request OpCode
        Result Code (0x01 = Success, 0x02 = OpCode Not Supported, etc.)
        """
        response = struct.pack('<BBB', 0x80, request_opcode, result_code)
        logger.debug(f"Sending control point response: {response.hex()}")
        
        # In Bless, we need to update the characteristic value for indication
        if self.server:
            try:
                # Set the value on the characteristic first
                self.server.get_characteristic(FITNESS_MACHINE_CONTROL_POINT_UUID).value = response
                # Then indicate clients of the update
                asyncio.create_task(
                    self.server.update_value(
                        FTMS_SERVICE_UUID,
                        FITNESS_MACHINE_CONTROL_POINT_UUID
                    )
                )
            except Exception as e:
                logger.error(f"Error sending control point response: {e}")
    
    def simulate_realistic_data(self):
        """Simulate realistic cycling data with variations"""
        
        if self.erg_mode_enabled and self.target_power > 0:
            # In ERG mode, gradually approach target power
            power_diff = self.target_power - self.power
            self.power += power_diff * 0.1  # Gradual approach
            self.power += random.uniform(-5, 5)  # Small variations
            self.power = max(0, min(2000, self.power))
            
            # Cadence adjusts naturally with power in ERG mode
            self.cadence = self.base_cadence + random.uniform(-self.cadence_variation, self.cadence_variation)
        else:
            # Normal mode - natural variations
            self.power = self.base_power + random.uniform(-self.power_variation, self.power_variation)
            self.cadence = self.base_cadence + random.uniform(-self.cadence_variation, self.cadence_variation)
        
        # Ensure values stay in realistic ranges
        self.power = max(0, min(2000, self.power))
        self.cadence = max(0, min(200, self.cadence))
        
        # Speed correlates roughly with power (simplified physics)
        # This is a very rough approximation: speed ≈ ∛(power)
        if self.power > 0:
            self.speed = 15 + (self.power / 10)  # Simplified relationship
        else:
            self.speed = 0
        
        self.speed = max(0, min(60, self.speed))
    
    def start_power(self):
        """Start power - go from 0 to default start power"""
        if self.power == 0:
            self.power = self.default_start_power
            self.base_power = self.default_start_power
            logger.info(f"🚀 Started: Power set to {self.default_start_power}W")
        else:
            logger.info(f"⚠️  Already running at {self.power}W. Use 'u' to update power.")
    
    def update_power(self, new_power: int):
        """Update power to a specific value"""
        if new_power < 0 or new_power > 2000:
            logger.warning(f"⚠️  Power must be between 0 and 2000W. Got {new_power}W")
            return
        self.power = new_power
        self.base_power = new_power
        logger.info(f"⚡ Power updated to {new_power}W")
    
    def stop_power(self):
        """Stop - go to zero power"""
        self.power = 0
        self.base_power = 0
        logger.info("🛑 Stopped: Power set to 0W")
    
    def _keyboard_input_handler(self):
        """Handle keyboard input in a separate thread"""
        print("\n" + "=" * 60)
        print("⌨️  KEYBOARD CONTROLS:")
        print("  's' or 'start'  - Start power (0 → default)")
        print("  'u <watts>'      - Update power (e.g., 'u 200')")
        print("  'stop'           - Stop power (→ 0W)")
        print("  'q' or 'quit'    - Quit trainer")
        print("=" * 60 + "\n")
        
        while True:
            try:
                line = input().strip().lower()
                
                if line in ['s', 'start']:
                    self.start_power()
                elif line.startswith('u '):
                    try:
                        watts = int(line.split()[1])
                        self.update_power(watts)
                    except (IndexError, ValueError):
                        print("⚠️  Usage: 'u <watts>' (e.g., 'u 200')")
                elif line == 'stop':
                    self.stop_power()
                elif line in ['q', 'quit', 'exit']:
                    print("\n🛑 Shutting down...")
                    # Signal shutdown by setting a flag or using os._exit
                    import os
                    os._exit(0)
                else:
                    print(f"⚠️  Unknown command: '{line}'. Type 's' to start, 'u <watts>' to update, 'stop' to stop.")
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Error in keyboard handler: {e}")
    
    async def start_advertising(self):
        """Start BLE advertising"""
        logger.info(f"Starting BLE advertising as '{self.name}'")
        await self.server.start()
        logger.info("✓ BLE advertising started - Zwift should now see the trainer")
    
    async def update_loop(self):
        """Main loop to update and broadcast trainer data"""
        logger.info("Starting data update loop")
        
        while True:
            try:
                # Simulate realistic data
                self.simulate_realistic_data()
                
                # Encode and send Indoor Bike Data
                bike_data = self._encode_indoor_bike_data()
                
                if self.server and self.server.get_characteristic(INDOOR_BIKE_DATA_UUID):
                    # Set the value on the characteristic first
                    self.server.get_characteristic(INDOOR_BIKE_DATA_UUID).value = bike_data
                    # Then notify clients of the update
                    self.server.update_value(
                        FTMS_SERVICE_UUID,
                        INDOOR_BIKE_DATA_UUID
                    )
                
                # Encode and send Cycling Power Measurement
                power_data = self._encode_cycling_power_measurement()
                
                if self.server and self.server.get_characteristic(CYCLING_POWER_MEASUREMENT_UUID):
                    # Set the value on the characteristic first
                    self.server.get_characteristic(CYCLING_POWER_MEASUREMENT_UUID).value = power_data
                    # Then notify clients of the update
                    self.server.update_value(
                        CYCLING_POWER_SERVICE_UUID,
                        CYCLING_POWER_MEASUREMENT_UUID
                    )
                    
                    logger.debug(f"Broadcasting - Power: {self.power:.1f}W, "
                               f"Cadence: {self.cadence:.1f}rpm, "
                               f"Speed: {self.speed:.1f}km/h")
                
                # Update every 1 second (1 Hz is typical for trainers)
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(1.0)
    
    async def run(self):
        """Main entry point - setup and run the virtual trainer"""
        try:
            logger.info("=" * 60)
            logger.info(f"Starting Virtual Trainer: {self.name}")
            logger.info("=" * 60)
            
            await self.setup_server()
            await self.start_advertising()
            
            logger.info("")
            logger.info("🚴 Virtual Trainer is ready!")
            logger.info("📱 Open Zwift and search for sensors")
            logger.info(f"🔍 Look for: '{self.name}'")
            logger.info("⚡ Broadcasting power and cadence data...")
            logger.info("")
            
            # Start keyboard input handler in a separate thread
            keyboard_thread = threading.Thread(target=self._keyboard_input_handler, daemon=True)
            keyboard_thread.start()
            
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 60)
            
            # Run update loop
            await self.update_loop()
            
        except KeyboardInterrupt:
            logger.info("\n\nShutting down virtual trainer...")
            if self.server:
                await self.server.stop()
            logger.info("✓ Stopped")
        except Exception as e:
            logger.error(f"Error running virtual trainer: {e}")
            raise


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Virtual Smart Bike Trainer for Zwift')
    parser.add_argument('--name', type=str, default='Zwiffery Trainer',
                      help='BLE device name (default: Zwiffery Trainer)')
    parser.add_argument('--power', type=int, default=150,
                      help='Base power in watts (default: 150)')
    parser.add_argument('--cadence', type=int, default=85,
                      help='Base cadence in RPM (default: 85)')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    trainer = VirtualTrainer(name=args.name)
    trainer.base_power = args.power
    trainer.base_cadence = args.cadence
    
    await trainer.run()


if __name__ == "__main__":
    asyncio.run(main())

