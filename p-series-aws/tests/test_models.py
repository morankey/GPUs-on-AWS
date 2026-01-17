"""Unit tests for data models"""

import unittest
from datetime import datetime, timezone
from core.models import SpotResult, CapacityBlockResult, OnDemandResult


class TestSpotResult(unittest.TestCase):
    """Test SpotResult model"""
    
    def test_az_display_format(self):
        """Test AZ display formatting"""
        result = SpotResult(
            instance_type="p4d.24xlarge",
            gpu_type="8x A100",
            score=9,
            price=6.5,
            region="us-east-1",
            az_name="us-east-1a",
            az_id="use1-az1"
        )
        self.assertEqual(result.az_display, "1a (use1-az1)")
    
    def test_az_display_no_dash(self):
        """Test AZ display when name has no dash"""
        result = SpotResult(
            instance_type="p4d.24xlarge",
            gpu_type="8x A100",
            score=9,
            price=6.5,
            region="us-east-1",
            az_name="unknown",
            az_id="use1-az1"
        )
        self.assertEqual(result.az_display, "unknown (use1-az1)")


class TestCapacityBlockResult(unittest.TestCase):
    """Test CapacityBlockResult model"""
    
    def test_available_block(self):
        """Test available capacity block"""
        start = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        result = CapacityBlockResult(
            instance_type="p5.48xlarge",
            gpu_type="8x H100",
            available=True,
            start_date=start,
            duration_hours=24,
            upfront_fee="755.00",
            region="us-east-1",
            az_name="us-east-1f",
            az_id="use1-az5",
            offering_id="cb-123456"
        )
        self.assertTrue(result.available)
        self.assertEqual(result.duration_hours, 24)
        self.assertEqual(result.az_display, "1f (use1-az5)")
    
    def test_unavailable_block(self):
        """Test unavailable capacity block"""
        result = CapacityBlockResult(
            instance_type="p5e.48xlarge",
            gpu_type="8x H200",
            available=False,
            start_date=None,
            duration_hours=None,
            upfront_fee=None,
            region="No availability",
            az_name="N/A",
            az_id="N/A",
            offering_id=None
        )
        self.assertFalse(result.available)
        self.assertIsNone(result.start_date)
        self.assertEqual(result.az_display, "N/A")


class TestOnDemandResult(unittest.TestCase):
    """Test OnDemandResult model"""
    
    def test_available_on_demand(self):
        """Test available on-demand instance"""
        result = OnDemandResult(
            instance_type="p4d.24xlarge",
            gpu_type="8x A100",
            available=True,
            price=21.95,
            region="us-west-2",
            az_name="us-west-2d",
            az_id="usw2-az4",
            score=9
        )
        self.assertTrue(result.available)
        self.assertEqual(result.price, 21.95)
        self.assertEqual(result.az_display, "2d (usw2-az4) Score:9")
    
    def test_spot_only_instance(self):
        """Test spot/CB only instance"""
        result = OnDemandResult(
            instance_type="p5.48xlarge",
            gpu_type="8x H100",
            available=False,
            price=None,
            region="Spot & CB Only",
            az_name="N/A",
            az_id="N/A",
            score=0
        )
        self.assertFalse(result.available)
        self.assertIsNone(result.price)
        self.assertEqual(result.az_display, "N/A")


if __name__ == '__main__':
    unittest.main()
