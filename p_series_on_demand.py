#!/usr/bin/env python3
"""
P Series On-Demand Instance Analysis
Shows on-demand pricing and availability for P-series GPU instances.
"""

import boto3
import sys
import json
import os
import time
from datetime import datetime


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
    if terminal_width >= 150:
        return 150, "full"
    elif terminal_width >= 120:
        return 120, "medium"
    else:
        # For narrow terminals, use actual width minus some padding
        return min(terminal_width - 5, 75), "compact"


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


def get_available_azs_for_instance(region, instance_type):
    """Get available AZs for instance type using spot placement scores as availability proxy"""
    client = boto3.client("ec2", region_name=region)
    az_mapping = get_az_mapping(region)
    id_to_name = {az_id: az_name for az_name, az_id in az_mapping.items()}
    
    try:
        response = client.get_spot_placement_scores(
            InstanceTypes=[instance_type],
            TargetCapacity=1,
            TargetCapacityUnitType="units",
            RegionNames=[region],
            SingleAvailabilityZone=True
        )
        
        available_azs = []
        for score_info in response.get("SpotPlacementScores", []):
            az_id = score_info.get("AvailabilityZoneId", "")
            score = score_info["Score"]
            az_name = id_to_name.get(az_id, f"unknown({az_id})")
            
            # Only include AZs with decent availability (score > 0)
            if score > 0:
                az_suffix = az_name.split('-')[-1] if '-' in az_name else az_name
                available_azs.append({
                    'az_name': az_name,
                    'az_id': az_id,
                    'az_display': f"{az_suffix} ({az_id})",
                    'score': score
                })
        
        # Sort by score descending (best availability first)
        available_azs.sort(key=lambda x: x['score'], reverse=True)
        return available_azs
        
    except Exception as e:
        return []


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
            
        except Exception as e:
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


def get_on_demand_pricing(regions):
    """Get real-time on-demand pricing from AWS Pricing API"""
    pricing_client = boto3.client('pricing', region_name='us-east-1')  # Pricing API only in us-east-1
    
    # Map regions to pricing API location format
    region_mapping = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-south-1': 'Asia Pacific (Mumbai)'
    }
    
    p_series_instances = get_modern_p_series_instances(regions)
    pricing_data = {}
    
    total_operations = len(regions) * len(p_series_instances)
    current_operation = 0
    
    for region in regions:
        if region not in region_mapping:
            continue
            
        location = region_mapping[region]
        pricing_data[region] = {}
        
        for instance_type in p_series_instances:
            show_progress_bar(current_operation, total_operations, "Fetching pricing data", "")
            
            try:
                response = pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                        {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'}
                    ],
                    MaxResults=10
                )
                
                if response['PriceList']:
                    # Find the right product (sometimes multiple results)
                    for price_item_str in response['PriceList']:
                        price_item = json.loads(price_item_str)
                        
                        # Check if this is the right product (on-demand, no pre-installed software)
                        attributes = price_item.get('product', {}).get('attributes', {})
                        if (attributes.get('preInstalledSw', '').lower() in ['na', 'n/a', ''] and
                            attributes.get('capacitystatus', '').lower() == 'used'):
                            
                            # Navigate the pricing structure
                            terms = price_item.get('terms', {})
                            on_demand = terms.get('OnDemand', {})
                            
                            if on_demand:
                                term_key = list(on_demand.keys())[0]
                                price_dimensions = on_demand[term_key].get('priceDimensions', {})
                                
                                if price_dimensions:
                                    price_key = list(price_dimensions.keys())[0]
                                    price_per_unit = price_dimensions[price_key].get('pricePerUnit', {})
                                    usd_price = price_per_unit.get('USD', '0')
                                    
                                    if float(usd_price) > 0:
                                        pricing_data[region][instance_type] = {
                                            'price': float(usd_price),
                                            'available': True
                                        }
                                        break
                    
                    # If no valid pricing found
                    if instance_type not in pricing_data[region]:
                        pricing_data[region][instance_type] = {'price': 0.0, 'available': False}
                else:
                    pricing_data[region][instance_type] = {'price': 0.0, 'available': False}
                    
            except Exception as e:
                pricing_data[region][instance_type] = {'price': 0.0, 'available': False}
            
            current_operation += 1
        
    # Clear progress bar
    print("\r" + " " * 80 + "\r", end="")
    
    return pricing_data


def get_availability_matrix():
    """Hard-coded availability matrix based on AWS regional availability patterns"""
    # This represents which instances are actually available for on-demand in each region
    # Based on testing and AWS documentation as of January 2026
    availability = {
        "us-east-1": {
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot & CB
            "p5.48xlarge": False,   # Only Spot & CB
            "p5e.48xlarge": False,    # Only Spot & CB
            "p5en.48xlarge": False,   # Only Spot & CB
            "p6-b200.48xlarge": False, # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        },
        "us-east-2": {
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot & CB
            "p5.48xlarge": False,   # Only Spot & CB
            "p5e.48xlarge": False,    # Only Spot & CB
            "p5en.48xlarge": False,   # Only Spot & CB
            "p6-b200.48xlarge": False, # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        },
        "us-west-1": {
            "p4d.24xlarge": False, # Only Spot & CB
            "p4de.24xlarge": False, # Only Spot & CB
            "p5.4xlarge": False,   # Only Spot & CB
            "p5.48xlarge": False,    # Only Spot & CB
            "p5e.48xlarge": False,     # Only Spot & CB
            "p5en.48xlarge": False,    # Only Spot & CB
            "p6-b200.48xlarge": False,  # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        },
        "us-west-2": {
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot & CB
            "p5.48xlarge": False,   # Only Spot & CB
            "p5e.48xlarge": False,    # Only Spot & CB
            "p5en.48xlarge": False,   # Only Spot & CB
            "p6-b200.48xlarge": False, # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        },
        "ap-northeast-1": {  # Tokyo
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot & CB
            "p5.48xlarge": False,  # Only Spot & CB
            "p5e.48xlarge": False,    # Only Spot & CB
            "p5en.48xlarge": False,   # Only Spot & CB
            "p6-b200.48xlarge": False, # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        },
        "ap-northeast-2": {  # Seoul
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot & CB
            "p5.48xlarge": False,  # Only Spot & CB
            "p5e.48xlarge": False,    # Only Spot & CB
            "p5en.48xlarge": False,   # Only Spot & CB
            "p6-b200.48xlarge": False, # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        },
        "ap-south-1": {  # Mumbai
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot & CB
            "p5.48xlarge": False,  # Only Spot & CB
            "p5e.48xlarge": False,    # Only Spot & CB
            "p5en.48xlarge": False,   # Only Spot & CB
            "p6-b200.48xlarge": False, # Only Spot & CB
            "p6-b300.48xlarge": False # Only Spot & CB
        }
    }
    return availability


def get_on_demand_analysis(regions=None):
    """Analyze on-demand pricing and availability"""
    
    if not regions:
        regions = ["us-east-1", "us-west-2"]
    
    p_series_instances = get_modern_p_series_instances(regions)
    
    # Get availability matrix and real-time pricing
    availability_matrix = get_availability_matrix()
    
    print(f"\nFetching real-time on-demand pricing...")
    pricing_data = get_on_demand_pricing(regions)
    
    # Get table width based on terminal size
    table_width, format_type = format_table_width()
    
    print(f"\nON-DEMAND PRICING & AVAILABILITY (A100+ GPUs)")
    print("=" * table_width)
    
    if format_type == "full":
        print(f"{'Instance':<18} {'GPU':<12} {'Price/Hour':<12} {'Status':<18} {'Best AZ (AZ-ID) & Score':<35} {'Region':<12}")
    elif format_type == "medium":
        print(f"{'Instance':<18} {'GPU':<12} {'Price/Hour':<12} {'Status':<15} {'Best AZ':<25} {'Region':<12}")
    else:
        print(f"{'Instance':<16} {'GPU':<10} {'Price':<8} {'Status':<12} {'Best AZ':<15} {'Region':<8}")
    
    print("-" * table_width)
    
    for region in regions:
        if region not in availability_matrix:
            print(f"No availability data for region: {region}")
            continue
            
        print(f"\n{region.upper()}:")
        print("-" * 60)
        
        for instance_type in p_series_instances:
            gpu_info = get_gpu_info(instance_type)
            
            # Check availability from matrix
            is_available = availability_matrix[region].get(instance_type, False)
            
            # Get best AZ for on-demand instances (p4d/p4de only)
            best_az_info = "N/A"
            if instance_type in ["p4d.24xlarge", "p4de.24xlarge"]:
                available_azs = get_available_azs_for_instance(region, instance_type)
                if available_azs:
                    best_az = available_azs[0]  # Already sorted by score descending
                    az_suffix = best_az['az_name'].split('-')[-1] if '-' in best_az['az_name'] else best_az['az_name']
                    best_az_info = f"{az_suffix} ({best_az['az_id']}) Score:{best_az['score']}"
                else:
                    best_az_info = "AZ lookup failed"
            
            if is_available and region in pricing_data and instance_type in pricing_data[region]:
                price_data = pricing_data[region][instance_type]
                price = price_data["price"]
                
                if price > 0:
                    price_str = f"${price:.4f}"
                    status = "Available"
                    az_list = best_az_info
                else:
                    price_str = "N/A"
                    status = "Price N/A"
                    az_list = best_az_info
            else:
                price_str = "N/A"
                status = "Spot & CB Only"
                az_list = best_az_info
            
            # Format output based on table width
            if format_type == "full":
                print(f"{instance_type:<18} {gpu_info:<12} {price_str:<12} {status:<18} {az_list:<35} {region:<12}")
            elif format_type == "medium":
                short_az_list = az_list[:25] + "..." if len(az_list) > 25 else az_list
                print(f"{instance_type:<18} {gpu_info:<12} {price_str:<12} {status:<15} {short_az_list:<25} {region:<12}")
            else:
                # Minimal format for narrow terminals
                if instance_type in ["p4d.24xlarge", "p4de.24xlarge"] and "Score:" in az_list:
                    import re
                    match = re.search(r'\(([^)]+)\).*Score:\s*(\d+)', az_list)
                    if match:
                        az_id, score = match.groups()
                        compact_az = f"{az_id}(s:{score})"
                    else:
                        compact_az = "AZ info N/A"
                else:
                    compact_az = "N/A"
                print(f"{instance_type:<16} {gpu_info:<10} {price_str:<8} {status:<12} {compact_az:<15} {region:<8}")


def get_on_demand_summary(regions=None):
    """Show best on-demand options across regions"""
    
    if not regions:
        regions = ["us-east-1", "us-west-2"]
    
    p_series_instances = get_modern_p_series_instances(regions)
    
    # Get availability matrix and real-time pricing
    availability_matrix = get_availability_matrix()
    
    pricing_data = get_on_demand_pricing(regions)
    
    print(f"BEST ON-DEMAND OPTIONS (Highest Availability + Competitive Price)")
    print("=" * 84)
    print(f"{'Instance':<18} {'GPU':<12} {'Best Price':<12} {'Region':<12} {'Best AZ (AZ-ID) & Score':<30}")
    print("-" * 84)
    
    for instance_type in p_series_instances:
        gpu_info = get_gpu_info(instance_type)
        best_option = None
        
        for region in regions:
            if (region in availability_matrix and 
                region in pricing_data and
                instance_type in availability_matrix[region] and
                instance_type in pricing_data[region]):
                
                is_available = availability_matrix[region][instance_type]
                price_data = pricing_data[region][instance_type]
                
                if is_available and price_data["price"] > 0:
                    # Get spot score for this region/instance
                    available_azs = get_available_azs_for_instance(region, instance_type)
                    if available_azs:
                        best_az_score = available_azs[0]['score']  # Already sorted by score descending
                        
                        if (best_option is None or 
                            best_az_score > best_option["score"] or
                            (best_az_score == best_option["score"] and price_data["price"] < best_option["price"])):
                            best_option = {
                                "price": price_data["price"],
                                "region": region,
                                "score": best_az_score
                            }
        
        # Get AZ info for this instance type (only if available on-demand)
        best_az_info = "N/A"
        if best_option and instance_type in ["p4d.24xlarge", "p4de.24xlarge"]:
            test_region = best_option['region']
            available_azs = get_available_azs_for_instance(test_region, instance_type)
            if available_azs:
                best_az = available_azs[0]
                az_suffix = best_az['az_name'].split('-')[-1] if '-' in best_az['az_name'] else best_az['az_name']
                best_az_info = f"{az_suffix} ({best_az['az_id']}) Score:{best_az['score']}"
            else:
                best_az_info = "AZ lookup failed"
        
        if best_option:
            price_str = f"${best_option['price']:.4f}"
            region_str = best_option['region']
        else:
            price_str = "N/A"
            region_str = "Spot & CB Only"
        
        az_list = best_az_info
        
        print(f"{instance_type:<18} {gpu_info:<12} {price_str:<12} {region_str:<12} {az_list:<30}")
    
    print("\n" + "=" * 84)
    print("Important: Shows highest availability option per instance type across all regions. Code selects highest spot score (availability indicator), with lowest price as tiebreaker.")


if __name__ == "__main__":
    try:
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_on_demand_summary(regions)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        sys.exit(1)