"""
Data models for P-Series GPU analysis results.

This module defines the core data structures used throughout the application
to represent analysis results for different AWS procurement methods:
- SpotResult: Spot instance pricing and availability
- CapacityBlockResult: Reserved capacity block offerings  
- OnDemandResult: On-demand pricing with availability indicators
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SpotResult:
    """
    Result for a single spot instance analysis.
    
    Attributes:
        instance_type: EC2 instance type (e.g., 'p4d.24xlarge')
        gpu_type: GPU configuration string (e.g., '8x A100')
        score: Spot placement score (1-10, higher = better availability)
        price: Current spot price per hour in USD
        region: AWS region code
        az_name: Availability zone name (e.g., 'us-east-1a')
        az_id: Availability zone ID (e.g., 'use1-az1')
    """
    instance_type: str
    gpu_type: str
    score: int
    price: float
    region: str
    az_name: str
    az_id: str
    
    @property
    def az_display(self) -> str:
        """
        Format AZ for display as 'suffix (az_id)'.
        
        Example: 'us-east-1a' with 'use1-az1' becomes '1a (use1-az1)'
        """
        az_suffix = self.az_name.split('-')[-1] if '-' in self.az_name else self.az_name
        return f"{az_suffix} ({self.az_id})"


@dataclass
class CapacityBlockResult:
    """
    Result for a single capacity block offering.
    
    Capacity blocks provide reserved GPU capacity for a fixed duration,
    purchased upfront at a known price.
    
    Attributes:
        instance_type: EC2 instance type (e.g., 'p5.48xlarge')
        gpu_type: GPU configuration string (e.g., '8x H100')
        available: Whether any capacity blocks are available
        start_date: Earliest available start time (UTC)
        duration_hours: Block duration in hours
        upfront_fee: Total upfront cost as string (e.g., '755.00')
        region: AWS region code
        az_name: Availability zone name
        az_id: Availability zone ID
        offering_id: AWS capacity block offering ID for purchase
    """
    instance_type: str
    gpu_type: str
    available: bool
    start_date: Optional[datetime]
    duration_hours: Optional[int]
    upfront_fee: Optional[str]
    region: str
    az_name: str
    az_id: str
    offering_id: Optional[str]
    
    @property
    def az_display(self) -> str:
        """
        Format AZ for display as 'suffix (az_id)'.
        
        Returns 'N/A' if availability zone is not set.
        """
        if not self.az_name or self.az_name == 'N/A':
            return 'N/A'
        az_suffix = self.az_name.split('-')[-1] if '-' in self.az_name else self.az_name
        return f"{az_suffix} ({self.az_id})"


@dataclass  
class OnDemandResult:
    """
    Result for a single on-demand instance analysis.
    
    On-demand instances provide guaranteed capacity at fixed hourly rates.
    Note: Most P5+ instances are NOT available on-demand (spot/CB only).
    
    Attributes:
        instance_type: EC2 instance type (e.g., 'p4d.24xlarge')
        gpu_type: GPU configuration string (e.g., '8x A100')
        available: Whether on-demand is available for this instance type
        price: Hourly price in USD (None if not available)
        region: AWS region code
        az_name: Recommended availability zone name
        az_id: Availability zone ID
        score: Spot placement score used as availability proxy (1-10)
    """
    instance_type: str
    gpu_type: str
    available: bool
    price: Optional[float]
    region: str
    az_name: str
    az_id: str
    score: int
    
    @property
    def az_display(self) -> str:
        """
        Format AZ for display as 'suffix (az_id) - Likelihood'.
        
        Converts spot score to likelihood label for on-demand recommendations.
        Returns 'N/A' if availability zone is not set.
        """
        if not self.az_name or self.az_name == 'N/A':
            return 'N/A'
        az_suffix = self.az_name.split('-')[-1] if '-' in self.az_name else self.az_name
        
        # Convert score to likelihood label
        if self.score >= 8:
            likelihood = "Likely"
        elif self.score >= 5:
            likelihood = "Possible"
        else:
            likelihood = "Unlikely"
        
        return f"{az_suffix} ({self.az_id}) - {likelihood}"
