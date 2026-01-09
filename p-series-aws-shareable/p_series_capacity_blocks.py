#!/usr/bin/env python3
"""
P Series Capacity Blocks Analysis
Capacity block availability and pricing analysis for P-series GPU instances
"""

import boto3
import sys
import os
from datetime import datetime, timedelta, timezone


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
    
    # Focus on immediate availability - check shorter durations first
    duration_options = [1, 24, 168]  # 1 hour, 1 day, 1 week
    
    for instance_type in instance_types:
        best_offering = None
        
        # Try different durations, prioritizing immediate availability
        for duration in duration_options:
            try:
                response = client.describe_capacity_block_offerings(
                    InstanceType=instance_type,
                    InstanceCount=1,
                    CapacityDurationHours=duration,
                    StartDateRange=datetime.now(timezone.utc),
                    EndDateRange=datetime.now(timezone.utc) + timedelta(days=7),  # Only check next 7 days for immediate availability
                    MaxResults=10
                )
                
                offerings = response.get('CapacityBlockOfferings', [])
                if offerings:
                    # Find the earliest available offering
                    earliest = min(offerings, key=lambda x: x['StartDate'])
                    az_name = earliest.get('AvailabilityZone', 'N/A')
                    az_id = az_mapping.get(az_name, 'unknown') if az_name != 'N/A' else 'N/A'
                    az_display = f"{az_name} ({az_id})" if az_name != 'N/A' else 'N/A'
                    
                    best_offering = {
                        'start_date': earliest['StartDate'],
                        'end_date': earliest['EndDate'],
                        'upfront_fee': earliest['UpfrontFee'],
                        'currency_code': earliest['CurrencyCode'],
                        'duration_hours': earliest['CapacityBlockDurationHours'],
                        'availability_zone': az_name,
                        'az_display': az_display
                    }
                    break  # Found one, use the earliest
                            
            except Exception as e:
                continue
        
        capacity_blocks[instance_type] = best_offering
    
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
    
    print(f"CAPACITY BLOCKS AVAILABILITY & PRICING (A100-B300 GPUs)")
    print(f"Regions: {', '.join(regions)} - Immediate Availability Focus")
    print("=" * table_width)
    
    if format_type == "full":
        print(f"{'Region':<10} {'Instance Type':<18} {'GPU':<10} {'Available':<9} {'Start Date':<16} {'Duration':<8} {'Upfront Fee':<11} {'AZ (AZ-ID)':<20}")
    elif format_type == "medium":
        print(f"{'Region':<9} {'Instance':<16} {'GPU':<9} {'Avail':<6} {'Start Date':<16} {'Dur':<6} {'Fee':<9} {'AZ (AZ-ID)':<16}")
    else:
        print(f"{'Region':<8} {'Instance':<12} {'GPU':<8} {'Avail':<5} {'Start Date':<16} {'Dur':<5} {'Fee':<8} {'AZ-ID':<8}")
    
    print("-" * table_width)
    
    any_blocks_found = False
    
    for region in regions:
        try:
            capacity_blocks = get_capacity_block_availability(region, p_series_instances)
            
            region_printed = False
            for instance_type in p_series_instances:
                region_col = region if not region_printed else ""
                gpu_info = get_gpu_info(instance_type)
                
                block_info = capacity_blocks.get(instance_type)
                if block_info:
                    # Check if start date is within the next hour (immediately available)
                    now = datetime.now(timezone.utc)
                    start_time = block_info['start_date']
                    time_diff = (start_time - now).total_seconds() / 3600  # Convert to hours
                    
                    if time_diff <= 1:  # Available within 1 hour
                        start_date = "Immediately Available"
                    else:
                        start_date = block_info['start_date'].strftime('%Y-%m-%d %H:%M')
                    
                    duration = f"{block_info['duration_hours']}hrs"
                    upfront_fee = f"${block_info['upfront_fee']}"
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
                    print(f"{region_col:<10} {instance_type:<18} {gpu_info:<10} {available:<9} {start_date:<16} {duration:<8} {upfront_fee:<11} {az_display:<20}")
                elif format_type == "medium":
                    # Truncate long fields for medium width
                    short_start = start_date[:16] + "..." if len(start_date) > 16 else start_date
                    short_az = az_display[:16] + "..." if len(az_display) > 16 else az_display
                    print(f"{region_col:<9} {instance_type:<16} {gpu_info:<9} {available:<6} {short_start:<16} {duration:<6} {upfront_fee:<9} {short_az:<16}")
                else:
                    # Compact format for narrow terminals
                    if start_date == "Immediately Available":
                        compact_start = "Now"
                    elif start_date == "N/A":
                        compact_start = "N/A"
                    else:
                        # Show full date but truncate if too long
                        compact_start = start_date[:16] + "..." if len(start_date) > 16 else start_date
                    
                    # Extract just AZ-ID for compact display
                    if az_display != "N/A":
                        import re
                        match = re.search(r'\(([^)]+)\)', az_display)
                        compact_az = match.group(1) if match else az_display[:8]
                    else:
                        compact_az = "N/A"
                    
                    # Truncate instance type for compact display
                    compact_instance = instance_type[:12]
                    
                    print(f"{region_col:<8} {compact_instance:<12} {gpu_info:<8} {available:<5} {compact_start:<16} {duration:<5} {upfront_fee:<8} {compact_az:<8}")
                
                region_printed = True
                
        except Exception as e:
            continue
    
    print("-" * table_width)
    if any_blocks_found:
        print("Note: Showing earliest available CAPACITY BLOCKS within next 90 days")
    else:
        print("Note: No CAPACITY BLOCKS found for any instance types in specified regions")
        print("      Try checking AWS Console directly or specific regions where you saw availability")



if __name__ == "__main__":
    try:
        print("🚀 Starting P Series CAPACITY BLOCKS Analysis...")
        print()
        
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_capacity_block_summary(regions)
        
        print("\n✅ CAPACITY BLOCKS Analysis Complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")