#!/usr/bin/env python3
"""
P Series Spot Instance Analysis
Comprehensive spot pricing and placement analysis for P-series GPU instances
"""

import boto3
import sys
import os
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict


def get_terminal_width():
    """Get terminal width, default to 120 if unable to detect"""
    try:
        return os.get_terminal_size().columns
    except:
        return 120


def format_table_width():
    """Determine appropriate table width based on terminal size"""
    terminal_width = get_terminal_width()
    if terminal_width >= 150:
        return 150, "full"
    elif terminal_width >= 120:
        return 120, "medium"
    else:
        # For narrow terminals, use actual width minus some padding
        return min(terminal_width - 5, 75), "compact"


def show_progress_bar(current, total, prefix="Progress", suffix="Complete", length=30):
    """Display a progress bar"""
    percent = ("{0:.0f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}%', end='', flush=True)
    if current == total:
        print()  # New line when complete


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


def get_price_and_score_summary(regions=None):
    """Show price-capacity optimized recommendations for each instance type"""
    
    # Use provided regions or default to us-east-1 and us-east-2
    if not regions:
        regions = ["us-east-1", "us-east-2"]
    
    p_series_instances = [
        "p4d.24xlarge", "p4de.24xlarge", 
        "p5.4xlarge", "p5.48xlarge", "p5e.48xlarge", "p5en.48xlarge",
        "p6-b200.48xlarge", "p6-b300.48xlarge"
    ]
    
    print(f"PRICE-CAPACITY OPTIMIZED RECOMMENDATIONS (Best Value: High Score + Low Price)")
    print(f"Regions: {', '.join(regions)}")
    print("=" * 84)
    
    # Collect all data with combined price and score info organized by region
    combined_data = {}  # region -> instance_type -> list of {price, score, az, value_ratio}
    
    total_operations = len(regions) * len(p_series_instances) * 2  # 2 operations per instance per region
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
            show_progress_bar(current_operation, total_operations, "Analyzing spot data", "")
            
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
                
        except Exception as e:
            pass
        
        current_operation += 1
        
        # Get scores and combine with prices
        for instance_type in p_series_instances:
            try:
                show_progress_bar(current_operation, total_operations, "Analyzing spot data", "")
                
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
                        
                        combined_data[region][instance_type].append({
                            'price': price,
                            'score': score,
                            'az': az_name,
                            'az_display': f"{az_name} ({az_id})",
                            'value_ratio': value_ratio
                        })
                    
            except Exception as e:
                pass
            
            current_operation += 1
    
    # Clear progress bar line
    print("\r" + " " * 80 + "\r", end="")
    
    # Display results by region
    for region in regions:
        print(f"\n{region.upper()}")
        print("-" * len(region))
        print(f"{'Instance Type':<18} {'GPU':<12} {'Score':<6} {'Price/Hour':<12} {'AZ (AZ-ID)':<20}")
        print("-" * 72)
        
        # Find best value (highest score/price ratio) for each instance type in this region
        best_values = {}
        
        for instance_type, options in combined_data[region].items():
            if options:
                # Sort by value ratio (score/price) descending, then by score descending as tiebreaker
                best_option = max(options, key=lambda x: (x['value_ratio'], x['score']))
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
    
    print("\n" + "=" * 84)
    print("Recommendations prioritize high availability at competitive prices")


if __name__ == "__main__":
    try:
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_price_and_score_summary(regions)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")