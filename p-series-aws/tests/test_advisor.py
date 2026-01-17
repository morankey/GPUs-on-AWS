"""Unit tests for GPUAdvisor"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from core.advisor import GPUAdvisor
from core.models import SpotResult, CapacityBlockResult, OnDemandResult


class TestGPUAdvisor(unittest.TestCase):
    """Test GPUAdvisor business logic"""
    
    def setUp(self):
        """Set up test advisor with mocked client"""
        self.advisor = GPUAdvisor(regions=["us-east-1"])
        self.advisor.client = Mock()
    
    def test_default_regions(self):
        """Test default regions are set"""
        advisor = GPUAdvisor()
        self.assertEqual(advisor.regions, ["us-east-1", "us-west-2"])
    
    def test_custom_regions(self):
        """Test custom regions are used"""
        advisor = GPUAdvisor(regions=["us-west-2", "ap-northeast-1"])
        self.assertEqual(advisor.regions, ["us-west-2", "ap-northeast-1"])
    
    def test_progress_callback(self):
        """Test progress callback is called"""
        progress_calls = []
        
        def callback(current, total):
            progress_calls.append((current, total))
        
        advisor = GPUAdvisor(regions=["us-east-1"], progress_callback=callback)
        advisor._report_progress(1, 10)
        advisor._report_progress(5, 10)
        
        self.assertEqual(len(progress_calls), 2)
        self.assertEqual(progress_calls[0], (1, 10))
        self.assertEqual(progress_calls[1], (5, 10))
    
    def test_instance_types_lazy_loading(self):
        """Test instance types are lazily loaded"""
        self.advisor.client.get_modern_p_series_instances.return_value = [
            "p4d.24xlarge", "p5.48xlarge"
        ]
        
        # First access
        types1 = self.advisor.instance_types
        # Second access should use cached value
        types2 = self.advisor.instance_types
        
        self.assertEqual(types1, types2)
        self.advisor.client.get_modern_p_series_instances.assert_called_once()
    
    def test_get_best_spot_options_selection(self):
        """Test spot option selection logic (highest score, lowest price)"""
        self.advisor.client.get_modern_p_series_instances.return_value = ["p4d.24xlarge"]
        self.advisor.client.get_gpu_info.return_value = "8x A100"
        self.advisor.client.get_az_mapping.return_value = {
            "us-east-1a": "use1-az1",
            "us-east-1b": "use1-az2"
        }
        self.advisor.client.get_spot_prices.return_value = {
            "p4d.24xlarge": {
                "us-east-1a": 6.5,
                "us-east-1b": 7.0
            }
        }
        self.advisor.client.get_spot_placement_scores.return_value = [
            {"AvailabilityZoneId": "use1-az1", "Score": 9},
            {"AvailabilityZoneId": "use1-az2", "Score": 9}
        ]
        
        results = self.advisor.get_best_spot_options()
        
        self.assertEqual(len(results), 1)
        # Should pick az1 (score 9, price 6.5) over az2 (score 9, price 7.0)
        self.assertEqual(results[0].az_id, "use1-az1")
        self.assertEqual(results[0].price, 6.5)
        self.assertEqual(results[0].score, 9)
    
    def test_get_best_spot_options_no_availability(self):
        """Test spot options when no availability"""
        self.advisor.client.get_modern_p_series_instances.return_value = ["p5.4xlarge"]
        self.advisor.client.get_gpu_info.return_value = "1x H100"
        self.advisor.client.get_az_mapping.return_value = {}
        self.advisor.client.get_spot_prices.return_value = {}
        self.advisor.client.get_spot_placement_scores.return_value = []
        
        results = self.advisor.get_best_spot_options()
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].region, "No availability")
        self.assertEqual(results[0].score, 0)
    
    def test_get_best_capacity_blocks_selection(self):
        """Test capacity block selection (earliest, shortest, cheapest)"""
        self.advisor.client.get_modern_p_series_instances.return_value = ["p5.48xlarge"]
        self.advisor.client.get_gpu_info.return_value = "8x H100"
        self.advisor.client.get_az_mapping.return_value = {"us-east-1f": "use1-az5"}
        
        early_date = datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc)
        late_date = datetime(2026, 1, 16, 6, 30, tzinfo=timezone.utc)
        
        self.advisor.client.get_capacity_block_offerings.return_value = [
            {
                'StartDate': late_date,
                'CapacityBlockDurationHours': 24,
                'UpfrontFee': '800.00',
                'AvailabilityZone': 'us-east-1f',
                'CapacityBlockOfferingId': 'cb-late'
            },
            {
                'StartDate': early_date,
                'CapacityBlockDurationHours': 24,
                'UpfrontFee': '755.00',
                'AvailabilityZone': 'us-east-1f',
                'CapacityBlockOfferingId': 'cb-early'
            }
        ]
        
        results = self.advisor.get_best_capacity_blocks()
        
        self.assertEqual(len(results), 1)
        # Should pick earliest start date
        self.assertEqual(results[0].offering_id, 'cb-early')
        self.assertEqual(results[0].start_date, early_date)
    
    def test_get_best_on_demand_options_available(self):
        """Test on-demand options for available instances"""
        self.advisor.client.get_modern_p_series_instances.return_value = ["p4d.24xlarge"]
        self.advisor.client.get_gpu_info.return_value = "8x A100"
        self.advisor.client.is_on_demand_available.return_value = True
        self.advisor.client.get_on_demand_price.return_value = 21.95
        self.advisor.client.get_az_mapping.return_value = {"us-east-1a": "use1-az1"}
        self.advisor.client.get_spot_placement_scores.return_value = [
            {"AvailabilityZoneId": "use1-az1", "Score": 9}
        ]
        
        results = self.advisor.get_best_on_demand_options()
        
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].available)
        self.assertEqual(results[0].price, 21.95)
        self.assertEqual(results[0].score, 9)
    
    def test_get_best_on_demand_options_spot_only(self):
        """Test on-demand options for spot-only instances"""
        self.advisor.client.get_modern_p_series_instances.return_value = ["p5.48xlarge"]
        self.advisor.client.get_gpu_info.return_value = "8x H100"
        self.advisor.client.is_on_demand_available.return_value = False
        self.advisor.client.get_az_mapping.return_value = {}
        
        results = self.advisor.get_best_on_demand_options()
        
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].available)
        self.assertIsNone(results[0].price)
        self.assertEqual(results[0].region, "Spot & CB Only")


class TestGPUAdvisorMultiRegion(unittest.TestCase):
    """Test multi-region analysis"""
    
    def setUp(self):
        """Set up multi-region advisor"""
        self.advisor = GPUAdvisor(regions=["us-east-1", "us-west-2"])
        self.advisor.client = Mock()
    
    def test_spot_options_by_region(self):
        """Test spot options grouped by region"""
        self.advisor.client.get_modern_p_series_instances.return_value = ["p4d.24xlarge"]
        self.advisor.client.get_gpu_info.return_value = "8x A100"
        self.advisor.client.get_az_mapping.return_value = {"us-east-1a": "use1-az1"}
        self.advisor.client.get_spot_prices.return_value = {
            "p4d.24xlarge": {"us-east-1a": 6.5}
        }
        self.advisor.client.get_spot_placement_scores.return_value = [
            {"AvailabilityZoneId": "use1-az1", "Score": 9}
        ]
        
        results = self.advisor.get_spot_options_by_region()
        
        self.assertIn("us-east-1", results)
        self.assertIn("us-west-2", results)
        self.assertEqual(len(results["us-east-1"]), 1)


if __name__ == '__main__':
    unittest.main()
