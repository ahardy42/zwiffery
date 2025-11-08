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


class VirtualTrainer:
    """Virtual Smart Trainer that emulates FTMS protocol for Zwift"""
    
    def __init__(self, name: str = "Zwiffery Trainer"):
        self.name = name
        self.server: Optional[BlessServer] = None
        
        # Trainer state
        self.power = 150  # Watts
        self.cadence = 85  # RPM
        self.speed = 25.0  # km/h
        self.heart_rate = 140  # BPM (optional)
        self.target_resistance = 0  # Target resistance level from Zwift (ERG mode)
        self.current_resistance = 0  # Current resistance level
        self.is_running = False
        
        # Simulation parameters
        self.base_power = 150
        self.base_cadence = 85
        self.power_variation = 15
        self.cadence_variation = 5
        
        # ERG mode settings
        self.erg_mode_enabled = False
        self.target_power = 0
        
    async def setup_server(self):
        """Initialize BLE GATT server"""
        logger.info(f"Setting up BLE server: {self.name}")
        
        # Create BLE server
        self.server = BlessServer(name=self.name, name_overwrite=True)
        
        # Add Device Information Service
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
        
        # Add FTMS Service
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
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            INDOOR_BIKE_DATA_UUID,
            GATTCharacteristicProperties.notify,
            None,
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
        
        # Fitness Machine Status
        await self.server.add_new_characteristic(
            FTMS_SERVICE_UUID,
            FITNESS_MACHINE_STATUS_UUID,
            GATTCharacteristicProperties.notify,
            None,
            GATTAttributePermissions.readable
        )
        
        # Set up write callback for control point
        def control_point_write_handler(characteristic: BlessGATTCharacteristic, value: bytearray):
            logger.info(f"Control Point Write: {value.hex()}")
            self._handle_control_point_command(value)
        
        self.server.get_characteristic(FITNESS_MACHINE_CONTROL_POINT_UUID).value = bytearray()
        self.server.update_value(FTMS_SERVICE_UUID, FITNESS_MACHINE_CONTROL_POINT_UUID)
        
        logger.info("BLE GATT server setup complete")
    
    def _encode_fitness_machine_features(self) -> bytes:
        """Encode Fitness Machine Feature characteristic
        
        Indicates what features this trainer supports:
        - Average Speed Supported
        - Cadence Supported  
        - Total Distance Supported
        - Resistance Level Supported
        - Power Measurement Supported
        - Indoor Bike Simulation Parameters Supported
        """
        # FTMS Features (8 bytes)
        # Byte 0-3: Fitness Machine Features
        # Bit 0: Average Speed Supported
        # Bit 1: Cadence Supported
        # Bit 2: Total Distance Supported
        # Bit 3: Inclination Supported
        # Bit 7: Resistance Level Supported
        # Bit 14: Power Measurement Supported
        
        features = 0b00000000000000000000000010001111  # bits 0,1,2,3,7,14
        target_features = 0b00000000000001000000000000000000  # bit 14: Indoor Bike Simulation Parameters Supported
        
        return struct.pack('<II', features, target_features)
    
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
                asyncio.create_task(
                    self.server.update_value(
                        FTMS_SERVICE_UUID,
                        FITNESS_MACHINE_CONTROL_POINT_UUID,
                        response
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
                    await self.server.update_value(
                        FTMS_SERVICE_UUID,
                        INDOOR_BIKE_DATA_UUID,
                        bike_data
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

