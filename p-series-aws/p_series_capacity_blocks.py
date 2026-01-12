#!/usr/bin/env python3
"""
P Series Capacity Blocks Analysis
Finds guaranteed reserved capacity for P-series GPU instances within 7 days.
"""

import boto3
import sys
import os
import time
from datetime import datetime, timedelta, timezone


def show_progress_bar(current, total, prefix="Progress", suffix="Complete", length=30):
    """Display progress bar during long operations"""
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
    """Determine table width based on terminal size"""
    terminal_width = get_terminal_width()
    if terminal_width >= 140:
        return 140, "full"
    elif terminal_width >= 110:
        return 110, "medium"
    else:
        return min(terminal_width - 5, 85), "compact"


def get_gpu_info(instance_type):
    """Get GPU information for instance types with API discovery and fallbacks"""
    
    # Module-level cache to avoid repeated API calls
    if not hasattr(get_gpu_info, 'cache'):
        get_gpu_info.cache = {}
    
    if instance_type in get_gpu_info.cache:
        return get_gpu_info.cache[instance_type]
    
    # Try AWS API first
    regions_to_try = ['us-east-1', 'us-west-2']
    
    for region in regions_to_try:
        try:
            client = boto3.client('ec2', region_name=region)
            response = client.describe_instance_types(InstanceTypes=[instance_type])
            
            if response['InstanceTypes']:
                instance_info = response['InstanceTypes'][0]
                if 'GpuInfo' in instance_info:
                    gpu_info = instance_info['GpuInfo']
                    gpus = gpu_info.get('Gpus', [])
                    if gpus:
                        gpu = gpus[0]
                        count = gpu.get('Count', 1)
                        name = gpu.get('Name', 'Unknown')
                        result = f"{count}x {name}"
                        get_gpu_info.cache[instance_type] = result
                        return result
                        
        except Exception:
            continue
    
    # Fallback to known mappings
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
    
    result = gpu_map.get(instance_type, "Unknown GPU")
    get_gpu_info.cache[instance_type] = result
    return result


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
            # Search within 7 days for immediate availability - up to 24 hours duration
            start_time = datetime.now(timezone.utc)
            end_time = datetime.now(timezone.utc) + timedelta(days=7)
            
            response = client.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=1,
                CapacityDurationHours=24,
                StartDateRange=start_time,
                EndDateRange=end_time,
                MaxResults=50
            )
            
            offerings = response.get('CapacityBlockOfferings', [])
            
            if offerings:
                # Find best offering: earliest start, shorter duration, lower price
                best = min(offerings, key=lambda x: (
                    x['StartDate'],
                    x['CapacityBlockDurationHours'],
                    float(x['UpfrontFee'])
                ))
                az_name = best.get('AvailabilityZone', 'N/A')
                az_id = az_mapping.get(az_name, 'unknown') if az_name != 'N/A' else 'N/A'
                
                # Extract AZ suffix for display
                if az_name != 'N/A':
                    az_suffix = az_name.split('-')[-1] if '-' in az_name else az_name
                    az_display = f"{az_suffix} ({az_id})"
                else:
                    az_display = 'N/A'
                
                best_offering = {
                    'start_date': best['StartDate'],
                    'end_date': best['EndDate'],
                    'upfront_fee': best['UpfrontFee'],
                    'currency_code': best['CurrencyCode'],
                    'duration_hours': best['CapacityBlockDurationHours'],
                    'availability_zone': az_name,
                    'az_id': az_id,
                    'az_display': az_display,
                    'offering_id': best.get('CapacityBlockOfferingId', 'N/A')
                }
                        
        except Exception as e:
            # Handle common errors gracefully
            error_msg = str(e)
            if "PendingVerification" in error_msg:
                pass  # Account verification pending
            elif "not supported for Capacity Blocks" in error_msg:
                pass  # Instance type not supported
            elif "CapacityBlockDescribeLimitExceeded" in error_msg:
                pass  # API rate limit
            else:
                pass  # Other errors
        
        capacity_blocks[instance_type] = best_offering
        current_operation += 1
    
    # Clear progress bar
    print("\r" + " " * 100 + "\r", end="", flush=True)
    
    return capacity_blocks


def get_modern_p_series_instances(regions):
    """Discover modern P-series instances (p4+) dynamically via AWS API with fallbacks"""
    all_modern_p_series = set()
    
    for region in regions:
        try:
            client = boto3.client('ec2', region_name=region)
            response = client.describe_instance_type_offerings(
                LocationType='region',
                Filters=[
                    {
                        'Name': 'location',
                        'Values': [region]
                    }
                ]
            )
            
            # Filter for modern P-series instances (p4, p5, p6+)
            modern_p_series = [
                offering['InstanceType'] 
                for offering in response['InstanceTypeOfferings'] 
                if offering['InstanceType'].startswith(('p4', 'p5', 'p6'))
            ]
            
            all_modern_p_series.update(modern_p_series)
            
        except Exception as e:
            # Fallback to minimal known list if API fails
            all_modern_p_series.update([
                'p4d.24xlarge', 'p4de.24xlarge'
            ])
    
    # Add known instances that might not appear in API results
    if 'us-west-2' in regions:
        all_modern_p_series.add('p6-b300.48xlarge')  # Only available in us-west-2
    
    return sorted(list(all_modern_p_series))


def get_capacity_block_summary(regions=None):
    """Show capacity block availability and pricing for specified regions"""
    
    if not regions:
        regions = ["us-east-1", "us-west-2"]
    
    # Dynamically discover modern P-series instances (p4+) via AWS API
    p_series_instances = get_modern_p_series_instances(regions)
    
    # Get table width based on terminal size
    table_width, format_type = format_table_width()
    
    print(f"CAPACITY BLOCKS - IMMEDIATE AVAILABILITY (1 Instance, ≤24 Hours)")
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
                print(f"{'Instance Type':<18} {'GPU':<8} {'Available':<9} {'Start Date':<20} {'Duration':<8} {'Total Cost':<10} {'AZ (AZ-ID)':<18} {'Offering ID':<15}")
                print("-" * 115)
            elif format_type == "medium":
                print(f"{'Instance':<16} {'GPU':<8} {'Avail':<6} {'Start Date':<20} {'Dur':<6} {'Total Cost':<10} {'AZ (AZ-ID)':<16} {'Offering ID':<12}")
                print("-" * 100)
            else:
                print(f"{'Instance':<12} {'GPU':<8} {'Avail':<5} {'Start Date':<12} {'Dur':<5} {'Total Cost':<10} {'AZ-ID':<8} {'Offering ID':<10}")
                print("-" * 80)
            
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
                        # Convert UTC to Eastern Time for display
                        from datetime import timezone as tz
                        eastern = tz(timedelta(hours=-5))  # EST (UTC-5)
                        eastern_time = block_info['start_date'].replace(tzinfo=timezone.utc).astimezone(eastern)
                        start_date = eastern_time.strftime('%Y-%m-%d %I:%M %p EST')
                    
                    duration = f"{block_info['duration_hours']}hrs"
                    upfront_fee = f"(${block_info['upfront_fee']})"
                    az_display = block_info['az_display']
                    offering_id = block_info.get('offering_id', 'N/A')
                    available = "Yes"
                    any_blocks_found = True
                else:
                    start_date = "N/A"
                    duration = "N/A"
                    upfront_fee = "N/A"
                    az_display = "N/A"
                    offering_id = "N/A"
                    available = "No"
                
                # Format output based on table width
                if format_type == "full":
                    print(f"{instance_type:<18} {gpu_info:<8} {available:<9} {start_date:<20} {duration:<8} {upfront_fee:<10} {az_display:<18} {offering_id:<15}")
                elif format_type == "medium":
                    # Truncate long fields for medium width
                    short_start = start_date[:20] if len(start_date) > 20 else start_date
                    short_az = az_display[:16] if len(az_display) > 16 else az_display
                    short_offering = offering_id[:12] if len(offering_id) > 12 else offering_id
                    print(f"{instance_type:<16} {gpu_info:<8} {available:<6} {short_start:<20} {duration:<6} {upfront_fee:<10} {short_az:<16} {short_offering:<12}")
                else:
                    # Compact format for narrow terminals
                    if start_date == "Immediate":
                        compact_start = "Now"
                    elif start_date == "N/A":
                        compact_start = "N/A"
                    else:
                        compact_start = start_date[:12]
                    
                    # Extract just AZ-ID for compact display
                    if az_display != "N/A":
                        import re
                        match = re.search(r'\(([^)]+)\)', az_display)
                        compact_az = match.group(1) if match else az_display[:8]
                    else:
                        compact_az = "N/A"
                    
                    # Truncate instance type and offering ID for compact display
                    compact_instance = instance_type[:12]
                    compact_offering = offering_id[:10] if offering_id != "N/A" else "N/A"
                    
                    print(f"{compact_instance:<12} {gpu_info:<8} {available:<5} {compact_start:<12} {duration:<5} {upfront_fee:<10} {compact_az:<8} {compact_offering:<10}")
                
        except Exception as e:
            print(f"\n{region.upper()}")
            print("-" * len(region))
            print(f"Error checking capacity blocks: {e}")
    
    print("\n" + "=" * table_width)
    if any_blocks_found:
        print("Important: Shows earliest available 24-hour blocks across all regions. Code picks most immediate availability, with shorter duration as tiebreaker.")
    else:
        print("No capacity blocks available within 7 days")



def get_best_capacity_block_summary(regions=None):
    """Show best capacity block options across all regions"""
    
    if not regions:
        regions = ["us-east-1", "us-west-2"]
    
    # If only one region, use the detailed view
    if len(regions) == 1:
        return get_capacity_block_summary(regions)
    
    p_series_instances = get_modern_p_series_instances(regions)
    
    print(f"BEST CAPACITY BLOCKS ACROSS REGIONS (Soonest Start Times)")
    print(f"Regions: {', '.join(regions)} - Within 7 Days")
    print("=" * 100)
    print(f"{'Instance':<18} {'GPU':<8} {'Available':<9} {'Start Date':<20} {'Duration':<8} {'Total Cost':<10} {'Region':<12} {'AZ (AZ-ID)':<12} {'Offering ID':<12}")
    print("-" * 100)
    
    # Collect all capacity blocks across regions
    all_blocks = {}  # instance_type -> list of blocks
    
    for region in regions:
        try:
            capacity_blocks = get_capacity_block_availability(region, p_series_instances)
            
            for instance_type, block_info in capacity_blocks.items():
                if instance_type not in all_blocks:
                    all_blocks[instance_type] = []
                
                if block_info:  # If block is available
                    block_with_region = block_info.copy()
                    block_with_region['region'] = region
                    all_blocks[instance_type].append(block_with_region)
                    
        except Exception as e:
            continue
    
    # Find best (earliest) block for each instance type
    for instance_type in p_series_instances:
        gpu_info = get_gpu_info(instance_type)
        
        if instance_type in all_blocks and all_blocks[instance_type]:
            # Sort by start date, duration, then price
            best_block = min(all_blocks[instance_type], key=lambda x: (
                x['start_date'],
                x['duration_hours'],
                float(x['upfront_fee'])
            ))
            
            # Format start date
            now = datetime.now(timezone.utc)
            start_time = best_block['start_date']
            time_diff = (start_time - now).total_seconds() / 3600
            
            if time_diff <= 1:
                start_date = "Immediate"
            else:
                from datetime import timezone as tz
                eastern = tz(timedelta(hours=-5))
                eastern_time = best_block['start_date'].replace(tzinfo=timezone.utc).astimezone(eastern)
                start_date = eastern_time.strftime('%m/%d %I:%M %p')
            
            duration = f"{best_block['duration_hours']}hrs"
            upfront_fee = f"(${best_block['upfront_fee']})"
            region_str = best_block['region']
            
            # Extract AZ suffix for display
            az_name = best_block['availability_zone']
            if az_name != 'N/A':
                az_suffix = az_name.split('-')[-1] if '-' in az_name else az_name
                az_display = f"{az_suffix} ({best_block.get('az_id', 'unknown')})"
            else:
                az_display = 'N/A'
            
            offering_id = best_block.get('offering_id', 'N/A')
            if len(offering_id) > 12:
                offering_id = offering_id[:12]
            
            available = "Yes"
        else:
            start_date = "N/A"
            duration = "N/A"
            upfront_fee = "N/A"
            region_str = "No availability"
            az_display = "N/A"
            offering_id = "N/A"
            available = "No"
        
        print(f"{instance_type:<18} {gpu_info:<8} {available:<9} {start_date:<20} {duration:<8} {upfront_fee:<10} {region_str:<12} {az_display:<12} {offering_id:<12}")
    
    print("\n" + "=" * 100)
    print("Important: Shows earliest available 24-hour blocks across all regions. Code picks most immediate availability, with shorter duration as tiebreaker.")


if __name__ == "__main__":
    try:
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_best_capacity_block_summary(regions)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")