"""
Configuration module for Virtual Trainer
Customize your trainer's behavior here
"""

# Trainer Identity
TRAINER_NAME = "Zwiffery Trainer"
MANUFACTURER = "Zwiffery Labs"
MODEL_NUMBER = "Virtual Trainer v1.0"

# Default Cycling Parameters
DEFAULT_POWER = 150  # Watts
DEFAULT_CADENCE = 85  # RPM
DEFAULT_SPEED = 25.0  # km/h

# Variation Settings (makes data look more realistic)
POWER_VARIATION = 15  # +/- watts random variation
CADENCE_VARIATION = 5  # +/- RPM random variation

# Power and Resistance Ranges
MIN_POWER = 0
MAX_POWER = 2000  # Max watts the trainer can report
POWER_INCREMENT = 1

MIN_RESISTANCE = 0
MAX_RESISTANCE = 100  # Percentage
RESISTANCE_INCREMENT = 1

# Update Frequency
UPDATE_INTERVAL = 1.0  # seconds (1 Hz is standard for trainers)

# ERG Mode Settings
ERG_MODE_RESPONSE_RATE = 0.1  # How quickly to reach target power (0.1 = 10% per update)

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
SHOW_DATA_UPDATES = False  # Set to True to see every power/cadence update

# Advanced: Workout Profiles
# You can create preset workout profiles here
WORKOUT_PROFILES = {
    "easy": {
        "power": 100,
        "cadence": 70,
        "power_variation": 10,
        "cadence_variation": 5
    },
    "moderate": {
        "power": 150,
        "cadence": 85,
        "power_variation": 15,
        "cadence_variation": 5
    },
    "hard": {
        "power": 250,
        "cadence": 95,
        "power_variation": 20,
        "cadence_variation": 7
    },
    "sprint": {
        "power": 400,
        "cadence": 110,
        "power_variation": 30,
        "cadence_variation": 10
    }
}

