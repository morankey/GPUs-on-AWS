#!/usr/bin/env python3
"""
P Series On-Demand Instance Analysis
On-demand pricing and availability analysis for P-series GPU instances
"""

import boto3
import sys
import json
import os
from datetime import datetime


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


def get_available_azs_for_instance(region, instance_type):
    """Get available AZs for an instance type using spot placement scores"""
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
                available_azs.append({
                    'az_name': az_name,
                    'az_id': az_id,
                    'az_display': f"{az_name} ({az_id})",
                    'score': score
                })
        
        # Sort by score descending (best availability first)
        available_azs.sort(key=lambda x: x['score'], reverse=True)
        return available_azs
        
    except Exception as e:
        return []


def get_on_demand_pricing(regions):
    """Get real-time on-demand pricing from AWS Pricing API"""
    pricing_client = boto3.client('pricing', region_name='us-east-1')  # Pricing API is only available in us-east-1
    
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
    
    p_series_instances = [
        "p4d.24xlarge", "p4de.24xlarge", 
        "p5.4xlarge", "p5.48xlarge", "p5e.48xlarge", "p5en.48xlarge",
        "p6-b200.48xlarge", "p6-b300.48xlarge"
    ]
    
    pricing_data = {}
    
    for region in regions:
        if region not in region_mapping:
            continue
            
        location = region_mapping[region]
        pricing_data[region] = {}
        
        for instance_type in p_series_instances:
            try:
                # Try with minimal filters first
                response = pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'instanceType',
                            'Value': instance_type
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'location',
                            'Value': location
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'tenancy',
                            'Value': 'Shared'
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'operatingSystem',
                            'Value': 'Linux'
                        }
                    ],
                    MaxResults=10
                )
                
                if response['PriceList']:
                    # Try to find the right product (sometimes multiple results)
                    for price_item_str in response['PriceList']:
                        price_item = json.loads(price_item_str)
                        
                        # Check if this is the right product (on-demand, no pre-installed software)
                        attributes = price_item.get('product', {}).get('attributes', {})
                        if (attributes.get('preInstalledSw', '').lower() in ['na', 'n/a', ''] and
                            attributes.get('capacitystatus', '').lower() == 'used'):
                            
                            # Navigate the complex pricing structure
                            terms = price_item.get('terms', {})
                            on_demand = terms.get('OnDemand', {})
                            
                            if on_demand:
                                # Get the first (and usually only) on-demand term
                                term_key = list(on_demand.keys())[0]
                                price_dimensions = on_demand[term_key].get('priceDimensions', {})
                                
                                if price_dimensions:
                                    # Get the first price dimension
                                    price_key = list(price_dimensions.keys())[0]
                                    price_per_unit = price_dimensions[price_key].get('pricePerUnit', {})
                                    usd_price = price_per_unit.get('USD', '0')
                                    
                                    if float(usd_price) > 0:
                                        pricing_data[region][instance_type] = {
                                            'price': float(usd_price),
                                            'available': True
                                        }
                                        break  # Found valid pricing, stop looking
                    
                    # If we didn't find valid pricing above
                    if instance_type not in pricing_data[region]:
                        pricing_data[region][instance_type] = {
                            'price': 0.0,
                            'available': False
                        }
                else:
                    # No pricing data found - likely not available in this region
                    pricing_data[region][instance_type] = {
                        'price': 0.0,
                        'available': False
                    }
                    
            except Exception as e:
                pricing_data[region][instance_type] = {
                    'price': 0.0,
                    'available': False
                }
        
    return pricing_data


def get_availability_matrix():
    """Hard-coded availability matrix based on AWS regional availability"""
    # This represents which instances are actually available for on-demand in each region
    # Based on the availability matrix provided
    availability = {
        "us-east-1": {
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot
            "p5.48xlarge": False,   # Only Spot
            "p5e.48xlarge": False,    # Only Spot
            "p5en.48xlarge": False,   # Only Spot
            "p6-b200.48xlarge": False, # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        },
        "us-east-2": {
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot
            "p5.48xlarge": False,   # Only Spot
            "p5e.48xlarge": False,    # Only Spot
            "p5en.48xlarge": False,   # Only Spot
            "p6-b200.48xlarge": False, # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        },
        "us-west-1": {
            "p4d.24xlarge": False, # Only Spot
            "p4de.24xlarge": False, # Only Spot
            "p5.4xlarge": False,   # Only Spot
            "p5.48xlarge": False,    # Only Spot
            "p5e.48xlarge": False,     # Only Spot
            "p5en.48xlarge": False,    # Only Spot
            "p6-b200.48xlarge": False,  # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        },
        "us-west-2": {
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot
            "p5.48xlarge": False,   # Only Spot
            "p5e.48xlarge": False,    # Only Spot
            "p5en.48xlarge": False,   # Only Spot
            "p6-b200.48xlarge": False, # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        },
        "ap-northeast-1": {  # Tokyo
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot
            "p5.48xlarge": False,  # Only Spot
            "p5e.48xlarge": False,    # Only Spot
            "p5en.48xlarge": False,   # Only Spot
            "p6-b200.48xlarge": False, # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        },
        "ap-northeast-2": {  # Seoul
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot
            "p5.48xlarge": False,  # Only Spot
            "p5e.48xlarge": False,    # Only Spot
            "p5en.48xlarge": False,   # Only Spot
            "p6-b200.48xlarge": False, # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        },
        "ap-south-1": {  # Mumbai
            "p4d.24xlarge": True,
            "p4de.24xlarge": True,
            "p5.4xlarge": False,  # Only Spot
            "p5.48xlarge": False,  # Only Spot
            "p5e.48xlarge": False,    # Only Spot
            "p5en.48xlarge": False,   # Only Spot
            "p6-b200.48xlarge": False, # Only Spot
            "p6-b300.48xlarge": False # Only Spot
        }
    }
    return availability


def get_on_demand_analysis(regions=None):
    """Analyze on-demand pricing and availability"""
    
    # Use provided regions or default to us-east-1 and us-east-2
    if not regions:
        regions = ["us-east-1", "us-east-2"]
    
    p_series_instances = [
        "p4d.24xlarge", "p4de.24xlarge", 
        "p5.4xlarge", "p5.48xlarge", "p5e.48xlarge", "p5en.48xlarge",
        "p6-b200.48xlarge", "p6-b300.48xlarge"
    ]
    
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
            
            # Get best AZ for on-demand instances (p4d/p4de only) regardless of pricing success
            best_az_info = "N/A"
            if instance_type in ["p4d.24xlarge", "p4de.24xlarge"]:
                available_azs = get_available_azs_for_instance(region, instance_type)
                if available_azs:
                    # Show the best AZ (highest score) for on-demand - just AZ-ID
                    best_az = available_azs[0]  # Already sorted by score descending
                    best_az_info = f"Best: {best_az['az_id']} (score: {best_az['score']})"
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
                # Truncate AZ list for medium width
                short_az_list = az_list[:25] + "..." if len(az_list) > 25 else az_list
                print(f"{instance_type:<18} {gpu_info:<12} {price_str:<12} {status:<15} {short_az_list:<25} {region:<12}")
            else:
                # Minimal format for narrow terminals - show condensed AZ info
                if instance_type in ["p4d.24xlarge", "p4de.24xlarge"] and "Best:" in az_list:
                    # Extract just the AZ-ID and score for compact display
                    import re
                    match = re.search(r'\(([^)]+)\).*score:\s*(\d+)', az_list)
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
    
    # Use provided regions or default to us-east-1 and us-east-2
    if not regions:
        regions = ["us-east-1", "us-east-2"]
    
    p_series_instances = [
        "p4d.24xlarge", "p4de.24xlarge", 
        "p5.4xlarge", "p5.48xlarge", "p5e.48xlarge", "p5en.48xlarge",
        "p6-b200.48xlarge", "p6-b300.48xlarge"
    ]
    
    # Get availability matrix and real-time pricing
    availability_matrix = get_availability_matrix()
    
    pricing_data = get_on_demand_pricing(regions)
    
    print(f"BEST ON-DEMAND OPTIONS (Lowest Price + Available)")
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
                    if (best_option is None or 
                        price_data["price"] < best_option["price"]):
                        best_option = {
                            "price": price_data["price"],
                            "region": region
                        }
        
        # Get AZ info for this instance type (regardless of pricing availability)
        best_az_info = "N/A"
        if instance_type in ["p4d.24xlarge", "p4de.24xlarge"]:
            # Use best pricing region if available, otherwise use first region
            test_region = best_option['region'] if best_option else (regions[0] if regions else "us-east-1")
            available_azs = get_available_azs_for_instance(test_region, instance_type)
            if available_azs:
                best_az = available_azs[0]
                best_az_info = f"Best: {best_az['az_id']} (score: {best_az['score']})"
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


if __name__ == "__main__":
    try:
        print("🚀 Starting P Series ON-DEMAND Analysis...")
        print()
        
        # Parse command line arguments properly
        args = sys.argv[1:]  # Get all arguments except script name
        
        # All arguments are regions (no more flags)
        regions = args if args else None
        
        get_on_demand_summary(regions)
        
        print("\n✅ ON-DEMAND Analysis Complete!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        sys.exit(1)