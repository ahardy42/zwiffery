#!/usr/bin/env python3
"""
Create charts from .fit files showing speed, power, and altitude vs distance.
"""

import json
import sys
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
from read_fit import read_fit_file, message_to_dict, extract_data_fields


def extract_record_data(json_data):
    """
    Extract record messages and prepare data for charting.
    
    Args:
        json_data: List of JSON objects from extract_data_fields
        
    Returns:
        dict: Dictionary with lists of distance, speed, power, altitude
    """
    records = [r for r in json_data if r.get('_message_type') == 'record']
    
    distances = []
    speeds = []
    powers = []
    altitudes = []
    
    for record in records:
        # Extract distance (in meters, convert to km for display)
        distance = record.get('distance')
        if distance is not None:
            distances.append(distance / 1000.0)  # Convert to km
        else:
            continue  # Skip records without distance
        
        # Extract speed (in m/s, convert to km/h)
        speed = record.get('speed') or record.get('enhanced_speed')
        if speed is not None:
            speeds.append(speed * 3.6)  # Convert m/s to km/h
        else:
            speeds.append(None)
        
        # Extract power (in watts)
        power = record.get('power')
        if power is not None and power > 0:  # Filter out zero/None power
            powers.append(power)
        else:
            powers.append(None)
        
        # Extract altitude (in meters)
        altitude = record.get('altitude') or record.get('enhanced_altitude')
        if altitude is not None:
            altitudes.append(altitude)
        else:
            altitudes.append(None)
    
    return {
        'distances': distances,
        'speeds': speeds,
        'powers': powers,
        'altitudes': altitudes,
        'count': len(distances)
    }


def create_chart(data, output_path=None, show_plot=True):
    """
    Create a chart showing speed, power, and altitude vs distance.
    
    Args:
        data: Dictionary with distance, speed, power, altitude lists
        output_path: Optional path to save the chart
        show_plot: Whether to display the plot
    """
    distances = data['distances']
    speeds = data['speeds']
    powers = data['powers']
    altitudes = data['altitudes']
    
    if not distances:
        print("Error: No record data with distance found", file=sys.stderr)
        return
    
    # Create figure with subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle('Zwift Activity Data', fontsize=16, fontweight='bold')
    
    # Plot 1: Speed vs Distance
    ax1.plot(distances, speeds, 'b-', linewidth=1.5, alpha=0.7, label='Speed')
    ax1.set_ylabel('Speed (km/h)', fontsize=12)
    ax1.set_title('Speed vs Distance', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Plot 2: Power vs Distance
    ax2.plot(distances, powers, 'r-', linewidth=1.5, alpha=0.7, label='Power')
    ax2.set_ylabel('Power (W)', fontsize=12)
    ax2.set_title('Power vs Distance', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Plot 3: Altitude vs Distance
    ax3.plot(distances, altitudes, 'g-', linewidth=1.5, alpha=0.7, label='Altitude')
    ax3.set_xlabel('Distance (km)', fontsize=12)
    ax3.set_ylabel('Altitude (m)', fontsize=12)
    ax3.set_title('Altitude vs Distance', fontsize=14)
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    
    # Adjust layout
    plt.tight_layout()
    
    # Save if output path provided
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Chart saved to: {output_path}", file=sys.stderr)
    
    # Show plot
    if show_plot:
        plt.show()
    else:
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='Create charts from .fit files showing speed, power, and altitude vs distance'
    )
    parser.add_argument(
        'fit_file',
        type=str,
        help='Path to the .fit file to read'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file path for the chart (e.g., chart.png). If not specified, chart is only displayed.'
    )
    parser.add_argument(
        '--no-show',
        action='store_true',
        help='Do not display the chart (only save if -o is specified)'
    )
    parser.add_argument(
        '--format',
        type=str,
        default='png',
        choices=['png', 'pdf', 'svg', 'jpg'],
        help='Output format for the chart (default: png)'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    fit_path = Path(args.fit_file)
    if not fit_path.exists():
        print(f"Error: File not found: {fit_path}", file=sys.stderr)
        sys.exit(1)
    
    # Determine output path
    output_path = None
    if args.output:
        output_path = Path(args.output)
    elif args.no_show:
        # If --no-show but no output, use default name
        output_path = fit_path.with_suffix(f'.{args.format}')
    
    # Read and decode FIT file
    print(f"Reading FIT file: {fit_path}", file=sys.stderr)
    messages, errors = read_fit_file(fit_path)
    
    if errors:
        print(f"Warnings/Errors encountered: {errors}", file=sys.stderr)
    
    # Extract data fields
    print("Extracting data fields...", file=sys.stderr)
    json_data = extract_data_fields(messages, debug=False)
    
    # Extract record data
    print("Extracting record data...", file=sys.stderr)
    chart_data = extract_record_data(json_data)
    
    if chart_data['count'] == 0:
        print("Error: No record messages with distance data found in FIT file", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {chart_data['count']} record points", file=sys.stderr)
    
    # Create chart
    print("Creating chart...", file=sys.stderr)
    create_chart(chart_data, output_path=output_path, show_plot=not args.no_show)


if __name__ == '__main__':
    main()


