#!/usr/bin/env python3
"""
P Series Spot Instance Analysis
Spot pricing and placement analysis for P-series GPU instances.
"""

import boto3
import sys
import os
from datetime import datetime, timedelta, timezone

# Terminal display constants
DEFAULT_TERMINAL_WIDTH = 120
FULL_WIDTH_THRESHOLD = 150
MEDIUM_WIDTH_THRESHOLD = 120
COMPACT_WIDTH_MINIMUM = 75
TERMINAL_PADDING = 5

# Table formatting constants
PROGRESS_BAR_LENGTH = 30
PROGRESS_BAR_CLEAR_WIDTH = 80
SPOT_ANALYSIS_TABLE_WIDTH = 84
SPOT_SUMMARY_TABLE_WIDTH = 94


def get_terminal_width():
    """Get terminal width, default to DEFAULT_TERMINAL_WIDTH if unable to detect"""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return DEFAULT_TERMINAL_WIDTH


def format_table_width():
    """Determine table width based on terminal size"""
    terminal_width = get_terminal_width()
    if terminal_width >= FULL_WIDTH_THRESHOLD:
        return FULL_WIDTH_THRESHOLD, "full"
    elif terminal_width >= MEDIUM_WIDTH_THRESHOLD:
        return MEDIUM_WIDTH_THRESHOLD, "medium"
    else:
        # For narrow terminals, use actual width minus some padding
        return min(terminal_width - TERMINAL_PADDING, COMPACT_WIDTH_MINIMUM), "compact"


def show_progress_bar(current, total, prefix="Progress", length=PROGRESS_BAR_LENGTH):
    """Display progress bar during long operations"""
    if total == 0:
        return
    percent = ("{0:.0f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}%', end='', flush=True)
    if current == total:
        print()  # New line when complete


def get_gpu_info(instance_type):
    """Get GPU information for instance types with API discovery and fallbacks"""
    
    # Module-level cache to avoid repeated API calls for same instance type
    if not hasattr(get_gpu_info, 'cache'):
        get_gpu_info.cache = {}
    
    # Return cached result if available
    if instance_type in get_gpu_info.cache:
        return get_gpu_info.cache[instance_type]
    
    # Try to get GPU info from AWS API first
    # Use us-west-2 for newer instance types that might not be available in us-east-1
    regions_to_try = ['us-east-1', 'us-west-2']
    
    for region in regions_to_try:
        try:
            client = boto3.client('ec2', region_name=region)
            response = client.describe_instance_types(
                InstanceTypes=[instance_type]
            )
            
            if response['InstanceTypes']:
                instance_info = response['InstanceTypes'][0]
                if 'GpuInfo' in instance_info:
                    gpu_info = instance_info['GpuInfo']
                    gpus = gpu_info.get('Gpus', [])
                    if gpus:
                        gpu = gpus[0]  # Take first GPU type (P-series typically have one GPU type)
                        count = gpu.get('Count', 1)
                        name = gpu.get('Name', 'Unknown')
                        
                        # Format the result
                        result = f"{count}x {name}"
                        
                        # Cache the result
                        get_gpu_info.cache[instance_type] = result
                        return result
                        
        except Exception:
            # Try next region
            continue
    
    # Fallback to known mappings for reliability and common instance types
    # Based on AWS instance type specifications as of January 2026
    # This ensures the tool works even when APIs are unavailable
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
    
    # Cache the fallback result too
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
            # Excludes p3 (older generation with K80/V100 GPUs)
            modern_p_series = [
                offering['InstanceType'] 
                for offering in response['InstanceTypeOfferings'] 
                if offering['InstanceType'].startswith(('p4', 'p5', 'p6'))
            ]
            
            all_modern_p_series.update(modern_p_series)
            
        except Exception:
            # Graceful fallback to minimal known list if API fails
            # This ensures the tool still works even with API issues
            all_modern_p_series.update([
                'p4d.24xlarge', 'p4de.24xlarge'  # Minimal fallback
            ])
    
    # Add known instances that might not appear in DescribeInstanceTypeOfferings
    # but are actually available (discovered through testing and AWS documentation)
    # Based on AWS availability chart as of January 2026
    if 'us-west-2' in regions:
        all_modern_p_series.add('p6-b300.48xlarge')  # Only available in us-west-2 (Oregon)
    
    return sorted(list(all_modern_p_series))


def get_price_and_score_summary(regions=None):
    """Show price-capacity optimized recommendations for each instance type"""
    
    if not regions:
        regions = ["us-east-1", "us-west-2"]
    
    p_series_instances = get_modern_p_series_instances(regions)
    
    print(f"SPOT PRICING - BEST AVAILABILITY (Highest Score, Lowest Price Tiebreaker)")
    print(f"Regions: {', '.join(regions)}")
    print("=" * SPOT_ANALYSIS_TABLE_WIDTH)
    
    # Data structure: region -> instance_type -> list of {price, score, az, value_ratio}
    combined_data = {}  
    
    total_operations = len(regions) * len(p_series_instances) * 2  # 2 API calls per instance per region
    current_operation = 0
    
    for region in regions:
        combined_data[region] = {}
        client = boto3.client("ec2", region_name=region)
        az_mapping = get_az_mapping(region)
        id_to_name = {az_id: az_name for az_name, az_id in az_mapping.items()}
        
        # Initialize data structure for this region
        for instance_type in p_series_instances:
            combined_data[region][instance_type] = []
        
        # Get prices by AZ
        prices_by_az = {}
        try:
            show_progress_bar(current_operation, total_operations, "Analyzing spot data")
            
            price_response = client.describe_spot_price_history(
                InstanceTypes=p_series_instances,
                ProductDescriptions=["Linux/UNIX"],
                MaxResults=1000,
                StartTime=datetime.now(timezone.utc) - timedelta(hours=1)
            )
            
            for price_info in price_response.get("SpotPriceHistory", []):
                az_name = price_info["AvailabilityZone"]
                instance_type = price_info["InstanceType"]
                price = float(price_info["SpotPrice"])
                
                if instance_type not in prices_by_az:
                    prices_by_az[instance_type] = {}
                prices_by_az[instance_type][az_name] = price
                
        except Exception:
            pass
        
        current_operation += 1
        
        # Get scores and combine with prices
        for instance_type in p_series_instances:
            try:
                show_progress_bar(current_operation, total_operations, "Analyzing spot data")
                
                score_response = client.get_spot_placement_scores(
                    InstanceTypes=[instance_type],
                    TargetCapacity=1,
                    TargetCapacityUnitType="units",
                    RegionNames=[region],
                    SingleAvailabilityZone=True
                )
                
                for score_info in score_response.get("SpotPlacementScores", []):
                    az_id = score_info.get("AvailabilityZoneId", "")
                    score = score_info["Score"]
                    az_name = id_to_name.get(az_id, f"unknown({az_id})")
                    
                    # Get price for this AZ if available
                    if (instance_type in prices_by_az and 
                        az_name in prices_by_az[instance_type]):
                        price = prices_by_az[instance_type][az_name]
                        
                        # Calculate value ratio: score/price (higher is better)
                        value_ratio = score / price if price > 0 else 0
                        
                        # Extract AZ suffix for display
                        az_suffix = az_name.split('-')[-1] if '-' in az_name else az_name
                        
                        combined_data[region][instance_type].append({
                            'price': price,
                            'score': score,
                            'az': az_name,
                            'az_display': f"{az_suffix} ({az_id})",
                            'value_ratio': value_ratio
                        })
                    
            except Exception:
                pass
            
            current_operation += 1
    
    # Clear progress bar
    print("\r" + " " * PROGRESS_BAR_CLEAR_WIDTH + "\r", end="")
    
    # Display results by region
    for region in regions:
        print(f"\n{region.upper()}")
        print("-" * len(region))
        print(f"{'Instance Type':<18} {'GPU':<12} {'Score':<6} {'Price/Hour':<12} {'AZ (AZ-ID)':<20}")
        print("-" * 72)
        
        # Find best value (highest score, lowest price as tiebreaker) for each instance type
        best_values = {}
        
        for instance_type, options in combined_data[region].items():
            if options:
                # Sort by score descending, then by price ascending as tiebreaker
                best_option = max(options, key=lambda x: (x['score'], -x['price']))
                best_values[instance_type] = best_option
        
        # Display results for this region
        for instance_type in sorted(p_series_instances):
            gpu_info = get_gpu_info(instance_type)
            
            if instance_type in best_values:
                best = best_values[instance_type]
                price_str = f"${best['price']:.4f}"
                az_display = best['az_display']
                score_str = str(best['score'])
            else:
                price_str = "N/A"
                az_display = "N/A"
                score_str = "N/A"
            
            print(f"{instance_type:<18} {gpu_info:<12} {score_str:<6} {price_str:<12} {az_display:<20}")
    
    print("\n" + "=" * SPOT_ANALYSIS_TABLE_WIDTH)
    print("Important: Shows highest placement score per instance type, with lowest price as tiebreaker.")


def get_best_spot_summary(regions=None):
    """Show best spot options across all regions"""
    
    if not regions:
        regions = ["us-east-1", "us-west-2"]
    
    # If only one region, use the detailed view
    if len(regions) == 1:
        return get_price_and_score_summary(regions)
    
    # Dynamically discover modern P-series instances (p4+) via AWS API
    p_series_instances = get_modern_p_series_instances(regions)
    
    print(f"BEST SPOT OPTIONS ACROSS REGIONS (Highest Score + Competitive Price)")
    print(f"Regions: {', '.join(regions)}")
    print("=" * SPOT_ANALYSIS_TABLE_WIDTH)
    print(f"{'Instance':<18} {'GPU':<12} {'Best Score':<10} {'Price/Hour':<12} {'Region':<12} {'AZ (AZ-ID)':<20}")
    print("-" * SPOT_SUMMARY_TABLE_WIDTH)
    
    # Collect all data across regions
    all_data = {}  # instance_type -> list of options
    
    total_operations = len(regions) * len(p_series_instances) * 2
    current_operation = 0
    
    for region in regions:
        client = boto3.client("ec2", region_name=region)
        az_mapping = get_az_mapping(region)
        id_to_name = {az_id: az_name for az_name, az_id in az_mapping.items()}
        
        # Get prices by AZ
        prices_by_az = {}
        try:
            show_progress_bar(current_operation, total_operations, "Analyzing spot data")
            
            price_response = client.describe_spot_price_history(
                InstanceTypes=p_series_instances,
                ProductDescriptions=["Linux/UNIX"],
                MaxResults=1000,
                StartTime=datetime.now(timezone.utc) - timedelta(hours=1)
            )
            
            for price_info in price_response.get("SpotPriceHistory", []):
                az_name = price_info["AvailabilityZone"]
                instance_type = price_info["InstanceType"]
                price = float(price_info["SpotPrice"])
                
                if instance_type not in prices_by_az:
                    prices_by_az[instance_type] = {}
                prices_by_az[instance_type][az_name] = price
                
        except Exception:
            pass
        
        current_operation += 1
        
        # Get scores and combine with prices
        for instance_type in p_series_instances:
            if instance_type not in all_data:
                all_data[instance_type] = []
                
            try:
                show_progress_bar(current_operation, total_operations, "Analyzing spot data")
                
                score_response = client.get_spot_placement_scores(
                    InstanceTypes=[instance_type],
                    TargetCapacity=1,
                    TargetCapacityUnitType="units",
                    RegionNames=[region],
                    SingleAvailabilityZone=True
                )
                
                for score_info in score_response.get("SpotPlacementScores", []):
                    az_id = score_info.get("AvailabilityZoneId", "")
                    score = score_info["Score"]
                    az_name = id_to_name.get(az_id, f"unknown({az_id})")
                    
                    # Get price for this AZ if available
                    if (instance_type in prices_by_az and 
                        az_name in prices_by_az[instance_type]):
                        price = prices_by_az[instance_type][az_name]
                        
                        # Extract just the AZ letter/suffix for cleaner display
                        az_suffix = az_name.split('-')[-1] if '-' in az_name else az_name
                        
                        all_data[instance_type].append({
                            'price': price,
                            'score': score,
                            'region': region,
                            'az_display': f"{az_suffix} ({az_id})",
                            'value_ratio': score / price if price > 0 else 0
                        })
                    
            except Exception:
                pass
            
            current_operation += 1
    
    # Clear progress bar line
    print("\r" + " " * PROGRESS_BAR_CLEAR_WIDTH + "\r", end="")
    
    # Find best option for each instance type across all regions
    for instance_type in p_series_instances:
        gpu_info = get_gpu_info(instance_type)
        
        if instance_type in all_data and all_data[instance_type]:
            # Sort by score first (descending), then by price (ascending) as tiebreaker
            best_option = max(all_data[instance_type], key=lambda x: (x['score'], -x['price']))
            
            score_str = str(best_option['score'])
            price_str = f"${best_option['price']:.4f}"
            region_str = best_option['region']
            az_str = best_option['az_display']
        else:
            score_str = "N/A"
            price_str = "N/A"
            region_str = "No availability"
            az_str = "N/A"
        
        print(f"{instance_type:<18} {gpu_info:<12} {score_str:<10} {price_str:<12} {region_str:<12} {az_str:<20}")
    
    print("\n" + "=" * SPOT_ANALYSIS_TABLE_WIDTH)
    print("Important: Shows the single best AZ per instance type across all regions. Code selects highest placement score (availability indicator), with price as tiebreaker.")


if __name__ == "__main__":
    try:
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_best_spot_summary(regions)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")