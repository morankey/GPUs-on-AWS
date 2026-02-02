"""
AWS API client for P-Series GPU instance data.
Consolidates all AWS API calls in one place.
"""

import boto3
from datetime import datetime, timedelta, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class AWSClient:
    """Handles all AWS API interactions for P-series analysis"""
    
    # GPU fallback mappings when API unavailable
    GPU_FALLBACK_MAP = {
        "p4d.24xlarge": "8x A100",
        "p4de.24xlarge": "8x A100", 
        "p5.4xlarge": "1x H100",
        "p5.48xlarge": "8x H100",
        "p5e.48xlarge": "8x H200",
        "p5en.48xlarge": "8x H200", 
        "p6-b200.48xlarge": "8x B200",
        "p6-b300.48xlarge": "8x B300"
    }
    
    # On-demand availability matrix (most P5+ are spot/CB only)
    ON_DEMAND_AVAILABILITY = {
        "us-east-1": {"p4d.24xlarge": True, "p4de.24xlarge": True},
        "us-east-2": {"p4d.24xlarge": True, "p4de.24xlarge": True},
        "us-west-1": {"p4d.24xlarge": True},
        "us-west-2": {"p4d.24xlarge": True, "p4de.24xlarge": True},
        "ap-northeast-1": {"p4d.24xlarge": True, "p4de.24xlarge": True},
        "ap-northeast-2": {"p4d.24xlarge": True},
        "ap-south-1": {"p4d.24xlarge": True},
        "ap-southeast-1": {"p4d.24xlarge": True},
        "ap-southeast-2": {"p4d.24xlarge": True},
        "ca-central-1": {"p4d.24xlarge": True},
        "eu-central-1": {"p4d.24xlarge": True, "p4de.24xlarge": True, "p5.48xlarge": True, "p5.4xlarge": True, "p5e.48xlarge": True, "p5en.48xlarge": True, "p6-b200.48xlarge": True},
        "eu-north-1": {"p4d.24xlarge": True},
        "eu-south-2": {"p4d.24xlarge": True},
        "eu-west-1": {"p4d.24xlarge": True},
        "eu-west-2": {"p4d.24xlarge": True, "p4de.24xlarge": True},
        "eu-west-3": {"p4d.24xlarge": True},
        "sa-east-1": {"p4d.24xlarge": True},
    }
    
    # Pricing API region name mapping
    PRICING_REGION_MAP = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ca-central-1': 'Canada (Central)',
        'eu-central-1': 'EU (Frankfurt)',
        'eu-north-1': 'EU (Stockholm)',
        'eu-south-2': 'Europe (Spain)',
        'eu-west-1': 'EU (Ireland)',
        'eu-west-2': 'EU (London)',
        'eu-west-3': 'EU (Paris)',
        'sa-east-1': 'South America (Sao Paulo)',
    }
    
    def __init__(self):
        self._gpu_cache = {}
        self._az_cache = {}
        self._session = boto3.Session()
    
    def get_default_region(self) -> Optional[str]:
        """
        Get the user's configured default AWS region.
        
        Returns the region from AWS_DEFAULT_REGION env var or ~/.aws/config.
        Returns None if no default is configured.
        """
        return self._session.region_name
    
    def get_active_regions(self, candidate_regions: list[str] = None) -> list[str]:
        """
        Discover regions where the user has running EC2 instances.
        
        Args:
            candidate_regions: List of regions to check. If None, checks all
                              regions in PRICING_REGION_MAP (P-series supported regions).
        
        Returns:
            List of region codes where user has running instances.
        """
        regions_to_check = candidate_regions or list(self.PRICING_REGION_MAP.keys())
        active_regions = []
        
        def check_region(region: str) -> Optional[str]:
            """Check if region has running instances"""
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}],
                    MaxResults=5  # We only need to know if any exist
                )
                if response.get('Reservations'):
                    return region
            except Exception:
                pass
            return None
        
        # Check regions in parallel for speed
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {executor.submit(check_region, r): r for r in regions_to_check}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    active_regions.append(result)
        
        return active_regions
    
    def get_suggested_regions(self) -> tuple[list[str], list[str]]:
        """
        Get suggested regions based on user's AWS activity.
        
        Returns:
            Tuple of (priority_regions, other_regions) where:
            - priority_regions: Default region + regions with running instances
            - other_regions: Remaining supported regions
        """
        all_supported = list(self.PRICING_REGION_MAP.keys())
        priority = set()
        
        # Add default region if it's in our supported list
        default = self.get_default_region()
        if default and default in all_supported:
            priority.add(default)
        
        # Add regions with running instances
        active = self.get_active_regions(all_supported)
        priority.update(active)
        
        # Split into priority and other
        priority_list = sorted(list(priority))
        other_list = [r for r in all_supported if r not in priority]
        
        return priority_list, other_list
    
    def get_gpu_info(self, instance_type: str) -> str:
        """Get GPU info for instance type with caching and fallback"""
        if instance_type in self._gpu_cache:
            return self._gpu_cache[instance_type]
        
        # Try AWS API
        for region in ['us-east-1', 'us-west-2']:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_instance_types(InstanceTypes=[instance_type])
                
                if response['InstanceTypes']:
                    info = response['InstanceTypes'][0]
                    if 'GpuInfo' in info:
                        gpus = info['GpuInfo'].get('Gpus', [])
                        if gpus:
                            gpu = gpus[0]
                            result = f"{gpu.get('Count', 1)}x {gpu.get('Name', 'Unknown')}"
                            self._gpu_cache[instance_type] = result
                            return result
            except Exception:
                continue
        
        # Fallback
        result = self.GPU_FALLBACK_MAP.get(instance_type, "Unknown GPU")
        self._gpu_cache[instance_type] = result
        return result
    
    def get_az_mapping(self, region: str) -> dict:
        """Get AZ name to ID mapping for a region"""
        if region in self._az_cache:
            return self._az_cache[region]
        
        try:
            client = boto3.client("ec2", region_name=region)
            response = client.describe_availability_zones()
            az_map = {az['ZoneName']: az['ZoneId'] for az in response['AvailabilityZones']}
            self._az_cache[region] = az_map
            return az_map
        except Exception:
            return {}
    
    def get_modern_p_series_instances(self, regions: list) -> list:
        """Discover P4+ instance types available in given regions"""
        all_instances = set()
        
        for region in regions:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_instance_type_offerings(
                    LocationType='region',
                    Filters=[{'Name': 'location', 'Values': [region]}]
                )
                
                for offering in response['InstanceTypeOfferings']:
                    itype = offering['InstanceType']
                    if itype.startswith(('p4', 'p5', 'p6')):
                        all_instances.add(itype)
            except Exception:
                all_instances.update(['p4d.24xlarge', 'p4de.24xlarge'])
        
        # Add known instances not always in API
        if 'us-west-2' in regions:
            all_instances.add('p6-b300.48xlarge')
        
        return sorted(list(all_instances))
    
    def get_spot_prices(self, region: str, instance_types: list) -> dict:
        """Get current spot prices by AZ for instance types"""
        prices = {}  # instance_type -> {az_name: price}
        
        try:
            client = boto3.client("ec2", region_name=region)
            response = client.describe_spot_price_history(
                InstanceTypes=instance_types,
                ProductDescriptions=["Linux/UNIX"],
                MaxResults=1000,
                StartTime=datetime.now(timezone.utc) - timedelta(hours=1)
            )
            
            for item in response.get("SpotPriceHistory", []):
                itype = item["InstanceType"]
                az = item["AvailabilityZone"]
                price = float(item["SpotPrice"])
                
                if itype not in prices:
                    prices[itype] = {}
                prices[itype][az] = price
        except Exception:
            pass
        
        return prices
    
    def get_spot_placement_scores(self, region: str, instance_type: str) -> list:
        """Get spot placement scores for instance type in region"""
        try:
            client = boto3.client("ec2", region_name=region)
            response = client.get_spot_placement_scores(
                InstanceTypes=[instance_type],
                TargetCapacity=1,
                TargetCapacityUnitType="units",
                RegionNames=[region],
                SingleAvailabilityZone=True
            )
            return response.get("SpotPlacementScores", [])
        except Exception:
            return []
    
    def get_capacity_block_offerings(self, region: str, instance_type: str) -> list:
        """Get capacity block offerings for instance type"""
        try:
            client = boto3.client("ec2", region_name=region)
            response = client.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=1,
                CapacityDurationHours=24,
                StartDateRange=datetime.now(timezone.utc),
                EndDateRange=datetime.now(timezone.utc) + timedelta(days=7),
                MaxResults=50
            )
            return response.get('CapacityBlockOfferings', [])
        except Exception:
            return []
    
    def get_on_demand_price(self, region: str, instance_type: str) -> Optional[float]:
        """Get on-demand price for instance type in region"""
        import json
        
        if region not in self.PRICING_REGION_MAP:
            return None
        
        location = self.PRICING_REGION_MAP[region]
        
        try:
            client = boto3.client('pricing', region_name='us-east-1')
            response = client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'}
                ],
                MaxResults=10
            )
            
            for price_item_str in response.get('PriceList', []):
                price_item = json.loads(price_item_str)
                attrs = price_item.get('product', {}).get('attributes', {})
                
                if (attrs.get('preInstalledSw', '').lower() in ['na', 'n/a', ''] and
                    attrs.get('capacitystatus', '').lower() == 'used'):
                    
                    terms = price_item.get('terms', {}).get('OnDemand', {})
                    if terms:
                        term_key = list(terms.keys())[0]
                        dims = terms[term_key].get('priceDimensions', {})
                        if dims:
                            dim_key = list(dims.keys())[0]
                            usd = dims[dim_key].get('pricePerUnit', {}).get('USD', '0')
                            if float(usd) > 0:
                                return float(usd)
        except Exception:
            pass
        
        return None
    
    def is_on_demand_available(self, region: str, instance_type: str) -> bool:
        """Check if instance type is available on-demand in region"""
        region_avail = self.ON_DEMAND_AVAILABILITY.get(region, {})
        return region_avail.get(instance_type, False)
