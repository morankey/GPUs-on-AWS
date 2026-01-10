#!/usr/bin/env python3
"""
P Series Capacity Blocks Analysis
Capacity block availability and pricing analysis for P-series GPU instances
"""

import boto3
import sys
import os
import time
from datetime import datetime, timedelta, timezone


def show_progress_bar(current, total, prefix="Progress", suffix="Complete", length=30):
    """Display a progress bar"""
    percent = ("{0:.0f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}%', end='', flush=True)
    if current == total:
        print()  # New line when complete


def get_terminal_width():
    """Get terminal width, default to 120 if unable to detect"""
    try:
        return os.get_terminal_size().columns
    except:
        return 120


def format_table_width():
    """Determine appropriate table width based on terminal size"""
    terminal_width = get_terminal_width()
    if terminal_width >= 140:
        return 140, "full"
    elif terminal_width >= 110:
        return 110, "medium"
    else:
        # For narrow terminals, use actual width minus some padding
        return min(terminal_width - 5, 85), "compact"


def get_gpu_info(instance_type):
    """Get GPU information for instance types"""
    gpu_map = {
        "p4d.24xlarge": "8x A100",
        "p4de.24xlarge": "8x A100", 
        "p5.4xlarge": "1x H100",
        "p5.48xlarge": "8x H100",
        "p5e.48xlarge": "8x H200",
        "p5en.48xlarge": "8x H200", 
        "p6-b200.48xlarge": "8x B200",
        "p6-b300.48xlarge": "8x B300"
    }
    return gpu_map.get(instance_type, "Unknown")


def get_az_mapping(region):
    """Get mapping between AZ names and AZ IDs"""
    client = boto3.client("ec2", region_name=region)
    try:
        response = client.describe_availability_zones()
        az_map = {}
        for az in response['AvailabilityZones']:
            az_map[az['ZoneName']] = az['ZoneId']
        return az_map
    except Exception as e:
        print(f"Error getting AZ mapping for {region}: {e}")
        return {}


def get_capacity_block_availability(region, instance_types):
    """Get capacity block availability and pricing for instance types"""
    client = boto3.client("ec2", region_name=region)
    az_mapping = get_az_mapping(region)
    capacity_blocks = {}
    
    total_operations = len(instance_types)
    current_operation = 0
    
    for instance_type in instance_types:
        show_progress_bar(current_operation, total_operations, "Analyzing capacity blocks", "")
        
        best_offering = None
        
        try:
            # Search within 7 days for immediate availability - 24 hour duration only
            start_time = datetime.now(timezone.utc)
            end_time = datetime.now(timezone.utc) + timedelta(days=7)
            
            response = client.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=1,
                CapacityDurationHours=24,  # Fixed at 24 hours
                StartDateRange=start_time,
                EndDateRange=end_time,
                MaxResults=10
            )
            
            offerings = response.get('CapacityBlockOfferings', [])
            if offerings:
                # Find the most immediate available offering (earliest start date)
                best = min(offerings, key=lambda x: x['StartDate'])
                az_name = best.get('AvailabilityZone', 'N/A')
                az_id = az_mapping.get(az_name, 'unknown') if az_name != 'N/A' else 'N/A'
                az_display = f"{az_name} ({az_id})" if az_name != 'N/A' else 'N/A'
                
                best_offering = {
                    'start_date': best['StartDate'],
                    'end_date': best['EndDate'],
                    'upfront_fee': best['UpfrontFee'],
                    'currency_code': best['CurrencyCode'],
                    'duration_hours': best['CapacityBlockDurationHours'],
                    'availability_zone': az_name,
                    'az_display': az_display
                }
                        
        except Exception as e:
            pass
        
        capacity_blocks[instance_type] = best_offering
        current_operation += 1
    
    # Clear progress bar line completely
    print("\r" + " " * 100 + "\r", end="", flush=True)
    
    return capacity_blocks


def get_capacity_block_summary(regions=None):
    """Show capacity block availability and pricing for specified regions"""
    
    # Use provided regions or default to us-east-1 and us-east-2
    if not regions:
        regions = ["us-east-1", "us-east-2"]
    
    p_series_instances = [
        "p4d.24xlarge", "p4de.24xlarge", 
        "p5.4xlarge", "p5.48xlarge", "p5e.48xlarge", "p5en.48xlarge",
        "p6-b200.48xlarge", "p6-b300.48xlarge"
    ]
    
    # Get table width based on terminal size
    table_width, format_type = format_table_width()
    
    print(f"CAPACITY BLOCKS - IMMEDIATE AVAILABILITY (1 Instance, 24 Hours)")
    print(f"Regions: {', '.join(regions)} - Within 7 Days")
    print("=" * table_width)
    
    any_blocks_found = False
    
    for region in regions:
        try:
            capacity_blocks = get_capacity_block_availability(region, p_series_instances)
            
            # Print region header
            print(f"\n{region.upper()}")
            print("-" * len(region))
            
            # Print table headers for this region
            if format_type == "full":
                print(f"{'Instance Type':<18} {'GPU':<10} {'Available':<9} {'Start Date':<20} {'Duration':<8} {'Total Cost':<10} {'AZ (AZ-ID)':<18}")
                print("-" * 98)
            elif format_type == "medium":
                print(f"{'Instance':<16} {'GPU':<9} {'Avail':<6} {'Start Date':<20} {'Dur':<6} {'Total Cost':<10} {'AZ (AZ-ID)':<16}")
                print("-" * 88)
            else:
                print(f"{'Instance':<12} {'GPU':<8} {'Avail':<5} {'Start Date':<18} {'Dur':<5} {'Total Cost':<10} {'AZ-ID':<8}")
                print("-" * 68)
            
            for instance_type in p_series_instances:
                gpu_info = get_gpu_info(instance_type)
                
                block_info = capacity_blocks.get(instance_type)
                if block_info:
                    # Check if start date is within the next hour (immediately available)
                    now = datetime.now(timezone.utc)
                    start_time = block_info['start_date']
                    time_diff = (start_time - now).total_seconds() / 3600  # Convert to hours
                    
                    if time_diff <= 1:  # Available within 1 hour
                        start_date = "Immediate"
                    else:
                        # Convert UTC to Eastern Time for display with AM/PM and timezone
                        from datetime import timezone as tz
                        eastern = tz(timedelta(hours=-5))  # EST (UTC-5)
                        eastern_time = block_info['start_date'].replace(tzinfo=timezone.utc).astimezone(eastern)
                        start_date = eastern_time.strftime('%Y-%m-%d %I:%M %p EST')
                    
                    duration = f"{block_info['duration_hours']}hrs"
                    upfront_fee = f"(${block_info['upfront_fee']})"
                    az_display = block_info['az_display']
                    available = "Yes"
                    any_blocks_found = True
                else:
                    start_date = "N/A"
                    duration = "N/A"
                    upfront_fee = "N/A"
                    az_display = "N/A"
                    available = "No"
                
                # Format output based on table width
                if format_type == "full":
                    print(f"{instance_type:<18} {gpu_info:<10} {available:<9} {start_date:<20} {duration:<8} {upfront_fee:<10} {az_display:<18}")
                elif format_type == "medium":
                    # Truncate long fields for medium width
                    short_start = start_date[:20] if len(start_date) > 20 else start_date
                    short_az = az_display[:16] if len(az_display) > 16 else az_display
                    print(f"{instance_type:<16} {gpu_info:<9} {available:<6} {short_start:<20} {duration:<6} {upfront_fee:<10} {short_az:<16}")
                else:
                    # Compact format for narrow terminals
                    if start_date == "Immediate":
                        compact_start = "Now"
                    elif start_date == "N/A":
                        compact_start = "N/A"
                    else:
                        # Show abbreviated date for compact display
                        compact_start = start_date[:18]
                    
                    # Extract just AZ-ID for compact display
                    if az_display != "N/A":
                        import re
                        match = re.search(r'\(([^)]+)\)', az_display)
                        compact_az = match.group(1) if match else az_display[:8]
                    else:
                        compact_az = "N/A"
                    
                    # Truncate instance type for compact display
                    compact_instance = instance_type[:12]
                    
                    print(f"{compact_instance:<12} {gpu_info:<8} {available:<5} {compact_start:<12} {duration:<5} {upfront_fee:<18} {compact_az:<8}")
                
        except Exception as e:
            print(f"\n{region.upper()}")
            print("-" * len(region))
            print(f"Error checking capacity blocks: {e}")
    
    print("\n" + "=" * table_width)
    if any_blocks_found:
        print("Showing most immediate 24-hour capacity blocks available")
    else:
        print("No 24-hour capacity blocks available within 7 days")



if __name__ == "__main__":
    try:
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_capacity_block_summary(regions)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")