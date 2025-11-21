#!/usr/bin/env python3
"""
Read .fit files from Zwift activities using the Garmin FIT SDK.
Outputs an array of JSON objects representing data fields sorted by time.
"""

import json
import sys
import argparse
from pathlib import Path
from garmin_fit_sdk import Decoder, Stream


def read_fit_file(fit_file_path):
    """
    Read and decode a FIT file, returning messages and errors.
    
    Args:
        fit_file_path: Path to the .fit file
        
    Returns:
        tuple: (messages dict, errors list)
    """
    try:
        stream = Stream.from_file(str(fit_file_path))
        decoder = Decoder(stream)
        messages, errors = decoder.read()
        return messages, errors
    except Exception as e:
        print(f"Error reading FIT file: {e}", file=sys.stderr)
        sys.exit(1)


def message_to_dict(msg, debug=False):
    """
    Convert a FIT message object to a dictionary.
    
    Args:
        msg: FIT message object (can be dict, object with __dict__, or object with items())
        debug: If True, print debug information
        
    Returns:
        dict: Dictionary representation of the message
    """
    msg_dict = {}
    
    # Handle different message formats
    if hasattr(msg, 'items'):
        items = msg.items()
    elif hasattr(msg, '__dict__'):
        items = msg.__dict__.items()
    elif isinstance(msg, dict):
        items = msg.items()
    else:
        if debug:
            print(f"Warning: Unknown message type: {type(msg)}", file=sys.stderr)
        return None
    
    for field_name, field_value in items:
        # Convert field values to JSON-serializable types
        if hasattr(field_value, 'isoformat'):  # datetime objects
            msg_dict[field_name] = field_value.isoformat()
        elif isinstance(field_value, (int, float, str, bool, type(None))):
            msg_dict[field_name] = field_value
        else:
            # Convert other types to string
            msg_dict[field_name] = str(field_value)
    
    return msg_dict


def extract_data_fields(messages, debug=False):
    """
    Extract data fields from FIT messages, focusing on record messages
    which contain time-series data.
    
    Args:
        messages: Dictionary of messages from the FIT decoder
        debug: If True, print debug information
        
    Returns:
        list: Array of JSON objects representing data fields
    """
    json_data = []
    
    if debug:
        print(f"Available message types: {list(messages.keys())}", file=sys.stderr)
        for msg_type, msg_list in messages.items():
            print(f"  {msg_type}: {len(msg_list)} messages", file=sys.stderr)
    
    # Message types that might contain time-series data
    # The Garmin FIT SDK uses names like 'record_mesgs', 'lap_mesgs', etc.
    message_types_to_check = [
        'record_mesgs',      # Time-series data (most common)
        'record',            # Alternative name (for compatibility)
        'lap_mesgs',         # Lap summaries
        'session_mesgs',     # Session summaries
        'activity_mesgs',    # Activity summaries
        'event_mesgs',       # Events (start, stop, etc.)
        'device_info_mesgs', # Device information
        'hrv_mesgs',         # Heart rate variability
        'hrv',               # Alternative name
    ]
    
    # Process each message type
    for message_type in message_types_to_check:
        if message_type not in messages:
            continue
        
        msg_list = messages[message_type]
        if debug:
            print(f"Processing {message_type}: {len(msg_list)} messages", file=sys.stderr)
        
        for msg in msg_list:
            msg_dict = message_to_dict(msg, debug=debug)
            if msg_dict is None:
                continue
            
            # Look for timestamp in various possible field names
            timestamp = None
            timestamp_field = None
            for ts_field in ['timestamp', 'time', 'timestamp_1', 'timestamp_2', 'time_created', 'start_time', 'local_timestamp']:
                if ts_field in msg_dict:
                    timestamp = msg_dict[ts_field]
                    timestamp_field = ts_field
                    # Normalize to 'timestamp' for consistency
                    if ts_field != 'timestamp':
                        msg_dict['timestamp'] = timestamp
                    break
            
            # Add message type to the dict for reference
            msg_dict['_message_type'] = message_type.replace('_mesgs', '')
            
            # If we found a timestamp, add the record
            if timestamp is not None:
                json_data.append(msg_dict)
            elif debug:
                print(f"  Message without timestamp (fields: {list(msg_dict.keys())})", file=sys.stderr)
    
    return json_data


def sort_by_time(json_data):
    """
    Sort JSON data objects by timestamp.
    
    Args:
        json_data: List of dictionaries with timestamp fields
        
    Returns:
        list: Sorted list of dictionaries
    """
    def get_timestamp(item):
        timestamp = item.get('timestamp')
        if timestamp is None:
            return None
        # If timestamp is a string (ISO format), we can still sort it
        # If it's a datetime object, convert to string for comparison
        if hasattr(timestamp, 'isoformat'):
            return timestamp.isoformat()
        return str(timestamp)
    
    # Filter out items without timestamps and sort the rest
    items_with_timestamps = [item for item in json_data if item.get('timestamp') is not None]
    items_without_timestamps = [item for item in json_data if item.get('timestamp') is None]
    
    # Sort by timestamp
    items_with_timestamps.sort(key=get_timestamp)
    
    # Return sorted items first, then items without timestamps
    return items_with_timestamps + items_without_timestamps


def main():
    parser = argparse.ArgumentParser(
        description='Read .fit files from Zwift activities and output JSON data sorted by time'
    )
    parser.add_argument(
        'fit_file',
        type=str,
        help='Path to the .fit file to read'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file path (default: print to stdout)'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty print JSON output with indentation'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Print debug information about FIT file structure'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    fit_path = Path(args.fit_file)
    if not fit_path.exists():
        print(f"Error: File not found: {fit_path}", file=sys.stderr)
        sys.exit(1)
    
    if not fit_path.suffix.lower() == '.fit':
        print(f"Warning: File does not have .fit extension: {fit_path}", file=sys.stderr)
    
    # Read and decode FIT file
    print(f"Reading FIT file: {fit_path}", file=sys.stderr)
    messages, errors = read_fit_file(fit_path)
    
    # Report errors if any
    if errors:
        print(f"Warnings/Errors encountered: {errors}", file=sys.stderr)
    
    # Extract data fields
    print("Extracting data fields...", file=sys.stderr)
    json_data = extract_data_fields(messages, debug=args.debug)
    
    if not json_data:
        print("Warning: No data fields with timestamps found in FIT file", file=sys.stderr)
        if not args.debug:
            print("Tip: Use --debug flag to see what messages are in the file", file=sys.stderr)
        else:
            # In debug mode, show what we found
            print("\nDebug: Available message types and counts:", file=sys.stderr)
            for msg_type, msg_list in messages.items():
                print(f"  {msg_type}: {len(msg_list)} messages", file=sys.stderr)
                if msg_list and len(msg_list) > 0:
                    first_msg = msg_list[0]
                    if hasattr(first_msg, '__dict__'):
                        print(f"    First message fields: {list(first_msg.__dict__.keys())}", file=sys.stderr)
                    elif isinstance(first_msg, dict):
                        print(f"    First message fields: {list(first_msg.keys())}", file=sys.stderr)
        sys.exit(0)
    
    # Sort by time
    print(f"Sorting {len(json_data)} records by timestamp...", file=sys.stderr)
    sorted_data = sort_by_time(json_data)
    
    # Output JSON
    indent = 2 if args.pretty else None
    json_output = json.dumps(sorted_data, indent=indent, default=str, ensure_ascii=False)
    
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output, encoding='utf-8')
        print(f"Output written to: {output_path}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == '__main__':
    main()

