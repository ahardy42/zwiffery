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
import math
from typing import Optional
from scipy.optimize import fsolve
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
        self.power = 0  # Start at 0W - use 'u' command to set power
        self.cadence = 0  # Start at 0rpm - will be set when power is updated
        self.speed = 0.0  # Start at 0 km/h
        self.heart_rate = 140  # BPM (optional)
        self.target_resistance = 0  # Target resistance level from Zwift (ERG mode)
        self.current_resistance = 0  # Current resistance level
        self.is_running = False
        
        # Simulation parameters
        self.base_power = 0  # Start at 0W
        self.base_cadence = 85
        self.cadence_variation = 5
        
        # Power variance levels (as percentage of power)
        self.VARIANCE_LEVELS = {
            'chill': 0.50,      # 15% variance
            'focused': 0.10,    # 5% variance
            'standard': 0.25,   # 10% variance (default)
            'exact': 0.00        # 0% variance
        }
        self.power_variance_level = 'standard'  # Default variance level
        self.power_variance_percent = self.VARIANCE_LEVELS['standard']
        
        # ERG mode settings
        self.erg_mode_enabled = False
        self.target_power = 0
        
        # Grade/slope from Zwift (SIM mode)
        self.current_grade = 0.0  # Grade percentage (e.g., 4.78 for 4.78%)
        
        # Wind speed from Zwift (SIM mode)
        self.current_wind_speed = 0.0  # Wind speed in m/s
        
        # Default start power for keyboard commands
        self.default_start_power = 150
        
        # Stopped state - when True, power and cadence stay at 0 with no fluctuations
        self.is_stopped = True  # Start stopped
        
        # Super tuck state - when True, rider is in super tuck (power/cadence = 0)
        # Super tuck entry: speed >= 38mph (61.15 km/h) AND grade <= -8%
        # Super tuck exit: speed < 38mph OR grade >= -3%
        # This hysteresis prevents rapid toggling
        self.is_super_tuck = False
        self.super_tuck_speed_threshold = 70.0  # 43.5 mph in km/h
        self.super_tuck_grade_threshold_entry = -8.0  # -8% grade to ENTER super tuck
        self.super_tuck_grade_threshold_exit = -3.0  # -3% grade to EXIT super tuck (less strict)
        self.pre_super_tuck_base_power = 0  # Store power before super tuck to restore later
        self.super_tuck_speed = 0.0  # Speed when entering super tuck (maintained during super tuck)
        
        # Physics model parameters for speed calculation
        self.rider_weight = 80.0  # kg (rider + bike)
        self.cda = 0.3  # Coefficient of drag area (m²)
        self.crr = 0.004  # Coefficient of rolling resistance
        self.rho = 1.226  # Air density (kg/m³)
        
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
        
        # Initialize control point characteristics with empty values
        self.server.get_characteristic(FITNESS_MACHINE_CONTROL_POINT_UUID).value = bytearray()
        self.server.get_characteristic(CYCLING_POWER_CONTROL_POINT_UUID).value = bytearray()
        
        # Set up write callback for all writable characteristics
        def write_handler(characteristic: BlessGATTCharacteristic, value: bytearray):
            """Handle write requests - route to appropriate handler based on characteristic UUID"""
            char_uuid = str(characteristic.uuid).lower().replace('-', '')
            # logger.info(f"Write to characteristic {char_uuid}: {value.hex()}")
            
            # Normalize UUIDs for comparison (remove dashes, lowercase)
            ftms_cp_uuid = FITNESS_MACHINE_CONTROL_POINT_UUID.lower().replace('-', '')
            cycling_cp_uuid = CYCLING_POWER_CONTROL_POINT_UUID.lower().replace('-', '')
            
            if char_uuid == ftms_cp_uuid:
                # Handle FTMS control point commands
                self._handle_control_point_command(value)
            elif char_uuid == cycling_cp_uuid:
                # Handle Cycling Power control point commands (similar to FTMS)
                self._handle_control_point_command(value)
            else:
                logger.warning(f"Write to unknown characteristic: {char_uuid}")
        
        # Set write callback for all writable characteristics
        self.server.write_request_func = write_handler
        
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
        # logger.info(f"Control Point OpCode: 0x{opcode:02x}")
        
        if opcode == 0x00:  # Request Control
            logger.info("Zwift requested control")
            self._send_control_point_response(opcode, 0x01)  # Success
            
        elif opcode == 0x01:  # Reset
            logger.info("Zwift requested reset")
            # Disable ERG mode on reset
            self.erg_mode_enabled = False
            self.target_power = 0
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
                # Immediately override current power with target power (ERG mode takes precedence)
                if target_power > 0:
                    self.power = target_power
                    # Clear base_power so it doesn't interfere with ERG mode
                    self.base_power = 0
                else:
                    # Target power is 0, set power to 0
                    self.power = 0
                logger.info(f"Zwift set target power (ERG mode): {target_power}W (overriding current power)")
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
            # SIM mode disables ERG mode - trainer should respond to manual "u" commands
            if self.erg_mode_enabled:
                logger.info("SIM mode started - disabling ERG mode (trainer will respond to 'u' commands)")
                self.erg_mode_enabled = False
                self.target_power = 0
            if len(data) >= 7:
                wind_speed = struct.unpack('<h', data[1:3])[0]  # m/s * 1000
                grade_raw = struct.unpack('<h', data[3:5])[0]  # percentage * 100
                crr = struct.unpack('<B', data[5:6])[0]  # rolling resistance * 10000
                cw = struct.unpack('<B', data[6:7])[0]  # wind resistance * 100
                # Store raw grade as percentage (e.g., 4.78 for 4.78%)
                raw_grade = grade_raw / 100.0
                # Correct negative grades: Zwift sends negative gradients at ~50% of actual value
                # So -8% in-game comes as -4% from Zwift - we need to double negative grades
                self.current_grade = self._correct_grade(raw_grade)
                # Store wind speed in m/s
                self.current_wind_speed = wind_speed / 1000.0
                logger.info(f"Zwift SIM mode - Raw Grade: {raw_grade:.2f}%, Corrected: {self.current_grade:.2f}%, Wind: {self.current_wind_speed:.2f}m/s")
                # Grade and wind will be used in physics-based speed calculation
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
                # Then indicate clients of the update (update_value is synchronous)
                self.server.update_value(
                    FTMS_SERVICE_UUID,
                    FITNESS_MACHINE_CONTROL_POINT_UUID
                )
            except Exception as e:
                logger.error(f"Error sending control point response: {e}")
    
    def _correct_grade(self, grade: float) -> float:
        """Correct grade value from Zwift
        
        Zwift sends negative gradients at approximately 50% of the actual value.
        For example, -8% in-game is sent as -4%. We correct by doubling negative grades.
        
        Args:
            grade: Raw grade percentage from Zwift
        
        Returns:
            Corrected grade percentage
        """
        if grade < 0:
            return grade * 2.0
        return grade
    
    def _check_can_enter_super_tuck(self) -> bool:
        """Check if conditions are met to ENTER super tuck
        
        Returns True if speed >= 38mph (61.15 km/h) AND grade <= -8%
        Note: grade is already corrected when stored, so we use current_grade directly
        """
        speed_ok = self.speed >= self.super_tuck_speed_threshold
        grade_ok = self.current_grade <= self.super_tuck_grade_threshold_entry
        logger.debug(f"Super tuck entry check: Speed: {self.speed:.1f}km/h (need >= {self.super_tuck_speed_threshold:.1f}), Grade: {self.current_grade:.2f}% (need <= {self.super_tuck_grade_threshold_entry:.1f}%)")
        return speed_ok and grade_ok
    
    def _check_should_exit_super_tuck(self) -> bool:
        """Check if conditions are met to EXIT super tuck
        
        Returns True if speed < 38mph (61.15 km/h) OR grade >= -3%
        Note: grade is already corrected when stored, so we use current_grade directly
        """
        speed_too_low = self.speed < self.super_tuck_speed_threshold
        grade_too_shallow = self.current_grade >= self.super_tuck_grade_threshold_exit
        should_exit = speed_too_low or grade_too_shallow
        if should_exit:
            logger.debug(f"Super tuck exit check: Speed: {self.speed:.1f}km/h (need >= {self.super_tuck_speed_threshold:.1f}), Grade: {self.current_grade:.2f}% (need < {self.super_tuck_grade_threshold_exit:.1f}%)")
        return should_exit
    
    def _calculate_bike_speed(self, power: float, grade: float, wind: float = None) -> float:
        """Calculate bike speed using physics model
        
        Args:
            power: Power in watts
            grade: Grade percentage (e.g., 3.0 for 3%)
            wind: Wind speed in m/s (defaults to self.current_wind_speed)
        
        Returns:
            Speed in km/h
        """
        if wind is None:
            wind = self.current_wind_speed
        
        g = 9.81  # Gravitational acceleration (m/s²)
        theta = math.atan(grade / 100.0)  # Angle in radians
        m = self.rider_weight  # Mass in kg
        
        def equation(v):
            """Physics equation: power = (aerodynamic + rolling + gravitational) * velocity
            
            Note: On descents, fgrav is negative (assisting), so the net force can be negative.
            This means the rider is accelerating, not at steady state. We solve for the speed
            where the power output equals the power needed to maintain that speed.
            """
            # Ensure velocity is non-negative for calculation
            v = max(0.0, v)
            faero = 0.5 * self.rho * self.cda * (v + wind) ** 2
            froll = self.crr * m * g * math.cos(theta)
            fgrav = m * g * math.sin(theta)
            # Net force: positive = opposing motion, negative = assisting motion
            net_force = faero + froll + fgrav
            # Power = force * velocity
            # If net_force is negative (steep descent), we're accelerating
            # We solve for where power output equals power needed
            return net_force * v - power
        
        # Better initial guess based on power and grade
        if power > 0:
            # Rough estimate: higher power or steeper descent = higher speed
            # For descents, we need a higher initial guess
            if grade < 0:
                # On descent: estimate based on power and grade
                # Steeper descent = faster, more power = faster
                v_guess = max(5.0, abs(grade) * 1.5 + (power / 50.0))
            else:
                # Uphill or flat: estimate based on power
                v_guess = 5.0 + (power / 100.0)
        elif grade < 0:
            # On descent with no power, estimate terminal velocity
            # Rough estimate based on grade (steeper = faster)
            v_guess = abs(grade) * 3.0  # m/s - higher multiplier for terminal velocity
        else:
            # Uphill or flat with no power = stopped
            v_guess = 0.1
        
        v_guess = max(0.1, v_guess)  # Ensure positive initial guess
        
        try:
            # Try to solve for positive velocity
            v_solution = fsolve(equation, v_guess)[0]
            
            # If we got a negative solution, it means on this descent the power is too low
            # to maintain steady state - the rider is accelerating. We need to estimate speed differently.
            if v_solution < 0:
                logger.debug(f"Physics model returned negative velocity {v_solution:.2f}m/s for power={power}W, grade={grade}% (accelerating on descent)")
                # On descent with low power, calculate speed based on power contribution to acceleration
                # We estimate speed where power contribution + gravity gives reasonable speed
                if grade < 0 and power > 0:
                    # On descent: gravity assists, power adds to speed
                    # Estimate terminal velocity if no power, then add power contribution
                    # Terminal velocity on descent (no power): roughly proportional to sqrt(abs(grade))
                    v_terminal_no_power = math.sqrt(abs(grade)) * 8.0  # Rough estimate
                    # Power adds to speed: more power = faster
                    v_power_contribution = math.sqrt(power / 20.0)  # Diminishing returns
                    v_solution = v_terminal_no_power + v_power_contribution
                    v_solution = max(8.0, v_solution)  # Minimum reasonable speed on descent
                elif grade < 0:
                    # Pure descent, no power - terminal velocity
                    v_solution = math.sqrt(abs(grade)) * 8.0
                    v_solution = max(5.0, v_solution)
                else:
                    # Shouldn't happen on flat/uphill, but fallback
                    v_solution = max(0.1, power / 100.0)
            
            # Convert from m/s to km/h
            speed_kmh = v_solution * 3.6
            # Ensure non-negative and reasonable speed (cap at 150 km/h)
            speed_kmh = max(0.0, min(150.0, speed_kmh))
            logger.debug(f"Physics model: power={power}W, grade={grade}%, wind={wind}m/s -> v={v_solution:.2f}m/s -> {speed_kmh:.1f}km/h")
            return speed_kmh
        except Exception as e:
            logger.warning(f"Error calculating speed with physics model: {e}, using fallback")
            # Fallback to simple calculation if physics model fails
            if power > 0:
                fallback_speed = 15 + (power / 10)
                logger.debug(f"Fallback calculation: {fallback_speed:.1f}km/h")
                return fallback_speed
            elif grade < 0:
                # Rough estimate for descent
                fallback_speed = abs(grade) * 7.0  # km/h per % grade
                logger.debug(f"Fallback descent: {fallback_speed:.1f}km/h")
                return fallback_speed
            return 0.0
    
    def simulate_realistic_data(self):
        """Simulate realistic cycling data with variations"""
        
        # If stopped, keep power and cadence at 0 with no fluctuations
        if self.is_stopped:
            self.power = 0
            self.cadence = 0
            self.speed = 0
            self.is_super_tuck = False
            return
        
        # Calculate power FIRST (needed to calculate speed accurately)
        # Calculate grade multiplier: 1 + (4 * grade / 100)
        # Example: 10% grade → 1.4x, -10% grade → 0.6x
        grade_multiplier = 1.0 + (4.0 * self.current_grade / 100.0)
        
        if self.erg_mode_enabled and self.target_power > 0:
            # In ERG mode: no gradient effect, 3% variance, no super tucks, no coasting
            # Use target power directly (no grade multiplier, no base_power influence)
            # Power is set immediately when target is received, so we just maintain it with variance
            base_erg_power = self.target_power
            # Apply 3% variance in ERG mode
            variance_amount = base_erg_power * 0.03  # 3% variance
            self.power = base_erg_power + random.uniform(-variance_amount, variance_amount)
            # Ensure power never goes to 0 in ERG mode (unless target is 0)
            self.power = max(0, min(2000, self.power))
            if self.target_power > 0 and self.power < 1:
                self.power = 1  # Minimum 1W to prevent coasting
            
            # Cadence adjusts naturally with power in ERG mode
            self.cadence = self.base_cadence + random.uniform(-self.cadence_variation, self.cadence_variation)
            
            # Exit super tuck if we're in it when ERG mode is active
            if self.is_super_tuck:
                self.is_super_tuck = False
                logger.info(f"🚴 Super tuck disabled in ERG mode. Restoring power.")
        elif self.power_variance_level == 'exact':
            # Exact mode - no variance, just use the target power and calculate speed
            self.power = self.target_power
            self.cadence = self.base_cadence
            self.speed = self._calculate_bike_speed(self.power, self.current_grade, self.current_wind_speed)
            self.is_super_tuck = False
            logger.info(f"🚴 Exact mode - power: {self.power:.1f}W, cadence: {self.cadence:.1f}rpm, speed: {self.speed:.1f}km/h")
        else:
            # Normal mode - apply grade multiplier to base power, then add variance
            # If ERG mode is enabled but target_power is 0, exit super tuck
            if self.erg_mode_enabled and self.is_super_tuck:
                self.is_super_tuck = False
                logger.info(f"🚴 Super tuck disabled in ERG mode (target power is 0).")
            
            if self.base_power > 0:
                # Apply grade multiplier: base_power * (1 + 4 * grade / 100)
                effective_base_power = self.base_power * grade_multiplier
                # Then apply variance to the adjusted power
                variance_amount = effective_base_power * self.power_variance_percent
                self.power = effective_base_power + random.uniform(-variance_amount, variance_amount)
                logger.debug(f"Power calculation: base={self.base_power}W, grade_mult={grade_multiplier:.2f}, effective={effective_base_power:.1f}W, final={self.power:.1f}W")
            else:
                self.power = 0
                logger.debug(f"Power is 0 because base_power is 0")
            self.cadence = self.base_cadence + random.uniform(-self.cadence_variation, self.cadence_variation)
        
        # Ensure values stay in realistic ranges
        self.power = max(0, min(2000, self.power))
        self.cadence = max(0, min(200, self.cadence))
        
        # Calculate speed from the NEW power value using physics model
        if self.power > 0:
            calculated_speed = self._calculate_bike_speed(self.power, self.current_grade, self.current_wind_speed)
            if calculated_speed > 0:
                self.speed = calculated_speed
                logger.debug(f"Speed calculation: power={self.power:.1f}W, grade={self.current_grade:.2f}%, wind={self.current_wind_speed:.2f}m/s -> speed={self.speed:.1f}km/h")
            else:
                # Physics model returned 0 or negative - use fallback
                logger.warning(f"Physics model returned {calculated_speed:.1f}km/h for power={self.power:.1f}W, using fallback")
                self.speed = 15 + (self.power / 10)  # Simple fallback
        else:
            self.speed = 0
            if not self.is_stopped:
                logger.info(f"Speed is 0 because power is 0 (base_power={self.base_power}, erg_mode={self.erg_mode_enabled}, target_power={self.target_power})")
        
        # Check super tuck conditions with hysteresis (different thresholds for entry vs exit)
        # Skip super tuck checks in ERG mode (no super tucks allowed)
        if not self.erg_mode_enabled:
            if self.is_super_tuck:
                # Already in super tuck - check if we should exit
                should_exit = self._check_should_exit_super_tuck()
                if should_exit:
                    # Exiting super tuck - restore base power
                    self.base_power = self.pre_super_tuck_base_power
                    logger.info(f"🚴 Super tuck disengaged. Speed: {self.speed:.1f} km/h, Grade: {self.current_grade:.1f}%")
                    self.is_super_tuck = False
                else:
                    # Maintain super tuck - set power and cadence to 0
                    self.power = 0
                    self.cadence = 0
                    
                    # During super tuck, calculate speed with power=0 using physics model
                    # This simulates coasting down a descent - speed will increase on negative grades
                    self.speed = self._calculate_bike_speed(0.0, self.current_grade, self.current_wind_speed)
                    self.super_tuck_speed = self.speed  # Update stored speed
            else:
                # Not in super tuck - check if we can enter
                can_enter = self._check_can_enter_super_tuck()
                if can_enter:
                    # Entering super tuck - save current base power and speed
                    self.pre_super_tuck_base_power = self.base_power
                    self.super_tuck_speed = self.speed
                    logger.info(f"🏎️  Super tuck engaged! Speed: {self.speed:.1f} km/h, Grade: {self.current_grade:.1f}%")
                    self.is_super_tuck = True
                    # Set power and cadence to 0 during super tuck
                    self.power = 0
                    self.cadence = 0
                    
                    # During super tuck, calculate speed with power=0 using physics model
                    # This simulates coasting down a descent - speed will increase on negative grades
                    self.speed = self._calculate_bike_speed(0.0, self.current_grade, self.current_wind_speed)
                    self.super_tuck_speed = self.speed  # Update stored speed
    
    
    def start_power(self):
        """Start trainer - clears stopped state but keeps power at 0 until updated"""
        if self.is_stopped:
            self.is_stopped = False
            # Keep power and cadence at 0 - user must update power explicitly
            self.power = 0
            self.base_power = 0
            self.cadence = 0
            logger.info("🚀 Trainer started (power at 0W - use 'u <watts>' to set power)")
        else:
            logger.info(f"⚠️  Already running at {self.power}W. Use 'u' to update power.")
    
    def update_power(self, new_power: int, variance_level: Optional[str] = None):
        """Update power to a specific value, optionally set variance level
        
        Args:
            new_power: Power in watts (0-2000)
            variance_level: Optional variance level ('chill', 'focused', 'standard')
        """
        if new_power < 0 or new_power > 2000:
            logger.warning(f"⚠️  Power must be between 0 and 2000W. Got {new_power}W")
            return
        # If updating to 0, treat it as stop
        if new_power == 0:
            self.stop_power()
            return
        
        # Update variance level if provided
        if variance_level:
            variance_level_lower = variance_level.lower()
            if variance_level_lower in self.VARIANCE_LEVELS:
                self.power_variance_level = variance_level_lower
                self.power_variance_percent = self.VARIANCE_LEVELS[variance_level_lower]
                logger.info(f"📊 Variance level set to '{variance_level_lower}' ({self.power_variance_percent*100:.0f}%)")
            else:
                logger.warning(f"⚠️  Unknown variance level '{variance_level}'. Use 'chill', 'focused', 'standard', or 'exact'")
        
        # Disable ERG mode when manually setting power (manual commands take precedence)
        if self.erg_mode_enabled:
            logger.info("Manual power update - disabling ERG mode")
            self.erg_mode_enabled = False
            self.target_power = 0
        
        # Clear stopped state and update power - this enables variations
        self.is_stopped = False
        self.power = new_power
        self.base_power = new_power
        # Restore cadence when power is set
        if self.cadence == 0:
            self.cadence = self.base_cadence
        
        variance_info = f" (variance: {self.power_variance_level}, {self.power_variance_percent*100:.0f}%)"
        logger.info(f"⚡ Power updated to {new_power}W{variance_info}")
    
    def stop_power(self):
        """Stop - go to zero power and cadence, no fluctuations"""
        self.is_stopped = True
        self.power = 0
        self.base_power = 0
        self.cadence = 0
        self.speed = 0
        logger.info("🛑 Stopped: Power and cadence set to 0W/0rpm (no fluctuations)")
    
    def _keyboard_input_handler(self):
        """Handle keyboard input in a separate thread"""
        print("\n" + "=" * 60)
        print("⌨️  KEYBOARD CONTROLS:")
        print("  's' or 'start'  - Start trainer (enables, stays at 0W)")
        print("  'u <watts> [variance]' - Update power (e.g., 'u 200' or 'u 200 chill')")
        print("                    Variance levels: 'chill' (15%), 'focused' (5%), 'standard' (10%)")
        print("  'stop'           - Stop trainer (→ 0W/0rpm, no variations)")
        print("  'q' or 'quit'    - Quit trainer")
        print("=" * 60 + "\n")
        
        while True:
            try:
                line = input().strip().lower()
                
                if line in ['s', 'start']:
                    self.start_power()
                elif line.startswith('u '):
                    try:
                        parts = line.split()
                        watts = int(parts[1])
                        # Check if variance level is provided (3rd argument)
                        variance_level = parts[2] if len(parts) > 2 else None
                        self.update_power(watts, variance_level)
                    except (IndexError, ValueError):
                        print("⚠️  Usage: 'u <watts> [variance]' (e.g., 'u 200' or 'u 200 chill')")
                        print("          Variance: 'chill' (15%), 'focused' (5%), 'standard' (10%)")
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

