"""
GPUAdvisor - Business logic for P-Series GPU instance recommendations.
Separates analysis logic from display/UI concerns.
"""

from typing import Optional, Callable
from .aws_client import AWSClient
from .models import SpotResult, CapacityBlockResult, OnDemandResult


class GPUAdvisor:
    """
    Analyzes P-series GPU instance availability across AWS regions.
    
    Usage:
        advisor = GPUAdvisor(regions=["us-east-1", "us-west-2"])
        spot_results = advisor.get_best_spot_options()
        cb_results = advisor.get_best_capacity_blocks()
        od_results = advisor.get_best_on_demand_options()
    """
    
    DEFAULT_REGIONS = ["us-east-1", "us-west-2"]
    
    def __init__(self, regions: list = None, progress_callback: Callable = None):
        """
        Initialize advisor with target regions.
        
        Args:
            regions: List of AWS region codes to analyze
            progress_callback: Optional callback(current, total) for progress updates
        """
        self.regions = regions or self.DEFAULT_REGIONS
        self.client = AWSClient()
        self.progress_callback = progress_callback
        self._instance_types = None
    
    @property
    def instance_types(self) -> list:
        """Lazily discover available P-series instance types"""
        if self._instance_types is None:
            self._instance_types = self.client.get_modern_p_series_instances(self.regions)
        return self._instance_types
    
    def _report_progress(self, current: int, total: int):
        """Report progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(current, total)
    
    def get_best_spot_options(self) -> list[SpotResult]:
        """
        Get best spot option for each instance type across all regions.
        Selection: highest placement score, lowest price as tiebreaker.
        
        Returns:
            List of SpotResult, one per instance type (best option only)
        """
        all_options = {}  # instance_type -> list of options
        
        total_ops = len(self.regions) * (1 + len(self.instance_types))
        current_op = 0
        
        for region in self.regions:
            az_mapping = self.client.get_az_mapping(region)
            id_to_name = {v: k for k, v in az_mapping.items()}
            
            # Get prices for all instance types in this region
            prices = self.client.get_spot_prices(region, self.instance_types)
            current_op += 1
            self._report_progress(current_op, total_ops)
            
            # Get scores for each instance type
            for itype in self.instance_types:
                if itype not in all_options:
                    all_options[itype] = []
                
                scores = self.client.get_spot_placement_scores(region, itype)
                
                for score_info in scores:
                    az_id = score_info.get("AvailabilityZoneId", "")
                    score = score_info["Score"]
                    az_name = id_to_name.get(az_id, f"unknown({az_id})")
                    
                    # Only include if we have price data
                    if itype in prices and az_name in prices[itype]:
                        price = prices[itype][az_name]
                        all_options[itype].append({
                            'score': score,
                            'price': price,
                            'region': region,
                            'az_name': az_name,
                            'az_id': az_id
                        })
                
                current_op += 1
                self._report_progress(current_op, total_ops)
        
        # Select best option per instance type
        results = []
        for itype in self.instance_types:
            gpu_type = self.client.get_gpu_info(itype)
            
            if itype in all_options and all_options[itype]:
                # Highest score, lowest price tiebreaker
                best = max(all_options[itype], key=lambda x: (x['score'], -x['price']))
                results.append(SpotResult(
                    instance_type=itype,
                    gpu_type=gpu_type,
                    score=best['score'],
                    price=best['price'],
                    region=best['region'],
                    az_name=best['az_name'],
                    az_id=best['az_id']
                ))
            else:
                # No availability
                results.append(SpotResult(
                    instance_type=itype,
                    gpu_type=gpu_type,
                    score=0,
                    price=0.0,
                    region="No availability",
                    az_name="N/A",
                    az_id="N/A"
                ))
        
        return results
    
    def get_spot_options_by_region(self) -> dict[str, list[SpotResult]]:
        """
        Get best spot option per instance type, grouped by region.
        For single-region detailed view.
        
        Returns:
            Dict of region -> list of SpotResult
        """
        results = {}
        
        total_ops = len(self.regions) * (1 + len(self.instance_types))
        current_op = 0
        
        for region in self.regions:
            results[region] = []
            az_mapping = self.client.get_az_mapping(region)
            id_to_name = {v: k for k, v in az_mapping.items()}
            
            prices = self.client.get_spot_prices(region, self.instance_types)
            current_op += 1
            self._report_progress(current_op, total_ops)
            
            for itype in self.instance_types:
                gpu_type = self.client.get_gpu_info(itype)
                options = []
                
                scores = self.client.get_spot_placement_scores(region, itype)
                
                for score_info in scores:
                    az_id = score_info.get("AvailabilityZoneId", "")
                    score = score_info["Score"]
                    az_name = id_to_name.get(az_id, f"unknown({az_id})")
                    
                    if itype in prices and az_name in prices[itype]:
                        price = prices[itype][az_name]
                        options.append({
                            'score': score,
                            'price': price,
                            'az_name': az_name,
                            'az_id': az_id
                        })
                
                if options:
                    best = max(options, key=lambda x: (x['score'], -x['price']))
                    results[region].append(SpotResult(
                        instance_type=itype,
                        gpu_type=gpu_type,
                        score=best['score'],
                        price=best['price'],
                        region=region,
                        az_name=best['az_name'],
                        az_id=best['az_id']
                    ))
                else:
                    results[region].append(SpotResult(
                        instance_type=itype,
                        gpu_type=gpu_type,
                        score=0,
                        price=0.0,
                        region=region,
                        az_name="N/A",
                        az_id="N/A"
                    ))
                
                current_op += 1
                self._report_progress(current_op, total_ops)
        
        return results
    
    def get_best_capacity_blocks(self) -> list[CapacityBlockResult]:
        """
        Get best capacity block for each instance type across all regions.
        Selection: earliest start, shortest duration, lowest price.
        
        Returns:
            List of CapacityBlockResult, one per instance type (best option only)
        """
        all_blocks = {}  # instance_type -> list of blocks
        
        total_ops = len(self.regions) * len(self.instance_types)
        current_op = 0
        
        for region in self.regions:
            az_mapping = self.client.get_az_mapping(region)
            
            for itype in self.instance_types:
                if itype not in all_blocks:
                    all_blocks[itype] = []
                
                offerings = self.client.get_capacity_block_offerings(region, itype)
                
                for offering in offerings:
                    az_name = offering.get('AvailabilityZone', 'N/A')
                    az_id = az_mapping.get(az_name, 'unknown')
                    
                    all_blocks[itype].append({
                        'start_date': offering['StartDate'],
                        'duration_hours': offering['CapacityBlockDurationHours'],
                        'upfront_fee': offering['UpfrontFee'],
                        'region': region,
                        'az_name': az_name,
                        'az_id': az_id,
                        'offering_id': offering.get('CapacityBlockOfferingId', 'N/A')
                    })
                
                current_op += 1
                self._report_progress(current_op, total_ops)
        
        # Select best block per instance type
        results = []
        for itype in self.instance_types:
            gpu_type = self.client.get_gpu_info(itype)
            
            if itype in all_blocks and all_blocks[itype]:
                # Earliest start, shortest duration, lowest price
                best = min(all_blocks[itype], key=lambda x: (
                    x['start_date'],
                    x['duration_hours'],
                    float(x['upfront_fee'])
                ))
                results.append(CapacityBlockResult(
                    instance_type=itype,
                    gpu_type=gpu_type,
                    available=True,
                    start_date=best['start_date'],
                    duration_hours=best['duration_hours'],
                    upfront_fee=best['upfront_fee'],
                    region=best['region'],
                    az_name=best['az_name'],
                    az_id=best['az_id'],
                    offering_id=best['offering_id']
                ))
            else:
                results.append(CapacityBlockResult(
                    instance_type=itype,
                    gpu_type=gpu_type,
                    available=False,
                    start_date=None,
                    duration_hours=None,
                    upfront_fee=None,
                    region="No availability",
                    az_name="N/A",
                    az_id="N/A",
                    offering_id=None
                ))
        
        return results
    
    def get_capacity_blocks_by_region(self) -> dict[str, list[CapacityBlockResult]]:
        """
        Get best capacity block per instance type, grouped by region.
        
        Returns:
            Dict of region -> list of CapacityBlockResult
        """
        results = {}
        
        total_ops = len(self.regions) * len(self.instance_types)
        current_op = 0
        
        for region in self.regions:
            results[region] = []
            az_mapping = self.client.get_az_mapping(region)
            
            for itype in self.instance_types:
                gpu_type = self.client.get_gpu_info(itype)
                offerings = self.client.get_capacity_block_offerings(region, itype)
                
                if offerings:
                    best = min(offerings, key=lambda x: (
                        x['StartDate'],
                        x['CapacityBlockDurationHours'],
                        float(x['UpfrontFee'])
                    ))
                    az_name = best.get('AvailabilityZone', 'N/A')
                    az_id = az_mapping.get(az_name, 'unknown')
                    
                    results[region].append(CapacityBlockResult(
                        instance_type=itype,
                        gpu_type=gpu_type,
                        available=True,
                        start_date=best['StartDate'],
                        duration_hours=best['CapacityBlockDurationHours'],
                        upfront_fee=best['UpfrontFee'],
                        region=region,
                        az_name=az_name,
                        az_id=az_id,
                        offering_id=best.get('CapacityBlockOfferingId', 'N/A')
                    ))
                else:
                    results[region].append(CapacityBlockResult(
                        instance_type=itype,
                        gpu_type=gpu_type,
                        available=False,
                        start_date=None,
                        duration_hours=None,
                        upfront_fee=None,
                        region=region,
                        az_name="N/A",
                        az_id="N/A",
                        offering_id=None
                    ))
                
                current_op += 1
                self._report_progress(current_op, total_ops)
        
        return results
    
    def get_best_on_demand_options(self) -> list[OnDemandResult]:
        """
        Get best on-demand option for each instance type across all regions.
        Selection: highest spot score (availability proxy), lowest price tiebreaker.
        
        Returns:
            List of OnDemandResult, one per instance type (best option only)
        """
        all_options = {}  # instance_type -> list of options
        
        total_ops = len(self.regions) * len(self.instance_types)
        current_op = 0
        
        for region in self.regions:
            az_mapping = self.client.get_az_mapping(region)
            id_to_name = {v: k for k, v in az_mapping.items()}
            
            for itype in self.instance_types:
                if itype not in all_options:
                    all_options[itype] = []
                
                # Check if on-demand is available for this instance type
                if not self.client.is_on_demand_available(region, itype):
                    current_op += 1
                    self._report_progress(current_op, total_ops)
                    continue
                
                # Get price
                price = self.client.get_on_demand_price(region, itype)
                if not price:
                    current_op += 1
                    self._report_progress(current_op, total_ops)
                    continue
                
                # Get spot scores as availability proxy
                scores = self.client.get_spot_placement_scores(region, itype)
                
                for score_info in scores:
                    az_id = score_info.get("AvailabilityZoneId", "")
                    score = score_info["Score"]
                    az_name = id_to_name.get(az_id, f"unknown({az_id})")
                    
                    if score > 0:
                        all_options[itype].append({
                            'score': score,
                            'price': price,
                            'region': region,
                            'az_name': az_name,
                            'az_id': az_id
                        })
                
                current_op += 1
                self._report_progress(current_op, total_ops)
        
        # Select best option per instance type
        results = []
        for itype in self.instance_types:
            gpu_type = self.client.get_gpu_info(itype)
            
            if itype in all_options and all_options[itype]:
                # Highest score, lowest price tiebreaker
                best = max(all_options[itype], key=lambda x: (x['score'], -x['price']))
                results.append(OnDemandResult(
                    instance_type=itype,
                    gpu_type=gpu_type,
                    available=True,
                    price=best['price'],
                    region=best['region'],
                    az_name=best['az_name'],
                    az_id=best['az_id'],
                    score=best['score']
                ))
            else:
                # Not available on-demand
                results.append(OnDemandResult(
                    instance_type=itype,
                    gpu_type=gpu_type,
                    available=False,
                    price=None,
                    region="Spot & CB Only",
                    az_name="N/A",
                    az_id="N/A",
                    score=0
                ))
        
        return results
