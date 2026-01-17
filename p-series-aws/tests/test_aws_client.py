"""Unit tests for AWS client"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from core.aws_client import AWSClient


class TestAWSClient(unittest.TestCase):
    """Test AWSClient functionality"""
    
    def setUp(self):
        """Set up test client"""
        self.client = AWSClient()
    
    def test_gpu_fallback_map(self):
        """Test GPU fallback mapping"""
        self.assertEqual(self.client.get_gpu_info("p4d.24xlarge"), "8x A100")
        self.assertEqual(self.client.get_gpu_info("p5.48xlarge"), "8x H100")
        self.assertEqual(self.client.get_gpu_info("p6-b300.48xlarge"), "8x B300")
    
    def test_gpu_info_caching(self):
        """Test GPU info is cached"""
        result1 = self.client.get_gpu_info("p4d.24xlarge")
        result2 = self.client.get_gpu_info("p4d.24xlarge")
        self.assertEqual(result1, result2)
        self.assertIn("p4d.24xlarge", self.client._gpu_cache)
    
    def test_on_demand_availability_p4(self):
        """Test P4 instances are available on-demand in major regions"""
        # US regions
        self.assertTrue(self.client.is_on_demand_available("us-east-1", "p4d.24xlarge"))
        self.assertTrue(self.client.is_on_demand_available("us-west-2", "p4de.24xlarge"))
        # EU regions
        self.assertTrue(self.client.is_on_demand_available("eu-west-1", "p4d.24xlarge"))
        self.assertTrue(self.client.is_on_demand_available("eu-central-1", "p4d.24xlarge"))
        # APAC regions
        self.assertTrue(self.client.is_on_demand_available("ap-southeast-1", "p4d.24xlarge"))
        self.assertTrue(self.client.is_on_demand_available("ap-southeast-2", "p4d.24xlarge"))
    
    def test_on_demand_availability_p5(self):
        """Test P5+ instances are not available on-demand"""
        self.assertFalse(self.client.is_on_demand_available("us-east-1", "p5.48xlarge"))
        self.assertFalse(self.client.is_on_demand_available("us-west-2", "p6-b200.48xlarge"))
        self.assertFalse(self.client.is_on_demand_available("eu-west-1", "p5.48xlarge"))
    
    def test_pricing_region_map_coverage(self):
        """Test all major regions are in pricing map"""
        expected_regions = [
            'us-east-1', 'us-east-2', 'us-west-2',
            'eu-west-1', 'eu-central-1',
            'ap-northeast-1', 'ap-southeast-1', 'ap-southeast-2'
        ]
        for region in expected_regions:
            self.assertIn(region, self.client.PRICING_REGION_MAP)
        
        # Verify specific mappings
        self.assertEqual(self.client.PRICING_REGION_MAP["us-east-1"], "US East (N. Virginia)")
        self.assertEqual(self.client.PRICING_REGION_MAP["eu-west-1"], "EU (Ireland)")
        self.assertEqual(self.client.PRICING_REGION_MAP["eu-central-1"], "EU (Frankfurt)")
        self.assertEqual(self.client.PRICING_REGION_MAP["ap-southeast-1"], "Asia Pacific (Singapore)")
        self.assertEqual(self.client.PRICING_REGION_MAP["ap-southeast-2"], "Asia Pacific (Sydney)")
    
    def test_on_demand_availability_map_coverage(self):
        """Test all major regions are in on-demand availability map"""
        expected_regions = [
            'us-east-1', 'us-east-2', 'us-west-2',
            'eu-west-1', 'eu-central-1',
            'ap-northeast-1', 'ap-southeast-1', 'ap-southeast-2'
        ]
        for region in expected_regions:
            self.assertIn(region, self.client.ON_DEMAND_AVAILABILITY)
    
    @patch('boto3.client')
    def test_az_mapping_caching(self, mock_boto):
        """Test AZ mapping is cached"""
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        mock_ec2.describe_availability_zones.return_value = {
            'AvailabilityZones': [
                {'ZoneName': 'us-east-1a', 'ZoneId': 'use1-az1'},
                {'ZoneName': 'us-east-1b', 'ZoneId': 'use1-az2'}
            ]
        }
        
        # First call
        result1 = self.client.get_az_mapping("us-east-1")
        # Second call should use cache
        result2 = self.client.get_az_mapping("us-east-1")
        
        self.assertEqual(result1, result2)
        self.assertEqual(mock_ec2.describe_availability_zones.call_count, 1)
    
    @patch('boto3.client')
    def test_get_spot_prices_success(self, mock_boto):
        """Test spot price retrieval"""
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        mock_ec2.describe_spot_price_history.return_value = {
            'SpotPriceHistory': [
                {
                    'InstanceType': 'p4d.24xlarge',
                    'AvailabilityZone': 'us-east-1a',
                    'SpotPrice': '6.5080'
                }
            ]
        }
        
        prices = self.client.get_spot_prices("us-east-1", ["p4d.24xlarge"])
        
        self.assertIn("p4d.24xlarge", prices)
        self.assertEqual(prices["p4d.24xlarge"]["us-east-1a"], 6.5080)
    
    @patch('boto3.client')
    def test_get_spot_placement_scores(self, mock_boto):
        """Test spot placement score retrieval"""
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        mock_ec2.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'AvailabilityZoneId': 'use1-az1', 'Score': 9},
                {'AvailabilityZoneId': 'use1-az2', 'Score': 7}
            ]
        }
        
        scores = self.client.get_spot_placement_scores("us-east-1", "p4d.24xlarge")
        
        self.assertEqual(len(scores), 2)
        self.assertEqual(scores[0]['Score'], 9)


class TestAWSClientRegionDetection(unittest.TestCase):
    """Test region auto-detection features"""
    
    def setUp(self):
        self.client = AWSClient()
    
    def test_get_default_region(self):
        """Test default region retrieval"""
        # Should return a string or None, not raise
        result = self.client.get_default_region()
        self.assertTrue(result is None or isinstance(result, str))
    
    @patch('boto3.client')
    def test_get_active_regions_with_instances(self, mock_boto):
        """Test active region detection finds regions with instances"""
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{'Instances': [{'InstanceId': 'i-123'}]}]
        }
        
        result = self.client.get_active_regions(['us-east-1'])
        self.assertIn('us-east-1', result)
    
    @patch('boto3.client')
    def test_get_active_regions_empty(self, mock_boto):
        """Test active region detection with no instances"""
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        
        result = self.client.get_active_regions(['us-east-1'])
        self.assertEqual(result, [])


class TestAWSClientErrorHandling(unittest.TestCase):
    """Test AWS client error handling"""
    
    def setUp(self):
        self.client = AWSClient()
    
    @patch('boto3.client')
    def test_get_az_mapping_error(self, mock_boto):
        """Test AZ mapping handles errors gracefully"""
        mock_boto.side_effect = Exception("AWS Error")
        result = self.client.get_az_mapping("us-east-1")
        self.assertEqual(result, {})
    
    @patch('boto3.client')
    def test_get_spot_prices_error(self, mock_boto):
        """Test spot prices handles errors gracefully"""
        mock_boto.side_effect = Exception("AWS Error")
        result = self.client.get_spot_prices("us-east-1", ["p4d.24xlarge"])
        self.assertEqual(result, {})
    
    @patch('boto3.client')
    def test_get_capacity_blocks_error(self, mock_boto):
        """Test capacity blocks handles errors gracefully"""
        mock_boto.side_effect = Exception("AWS Error")
        result = self.client.get_capacity_block_offerings("us-east-1", "p5.48xlarge")
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
