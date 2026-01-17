"""Integration tests for end-to-end workflows"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from core.advisor import GPUAdvisor
from core.aws_client import AWSClient


class TestIntegrationWorkflows(unittest.TestCase):
    """Test complete analysis workflows"""
    
    @patch('boto3.client')
    def test_spot_analysis_workflow(self, mock_boto):
        """Test complete spot analysis workflow"""
        # Mock EC2 client
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        
        # Mock instance type discovery
        mock_ec2.describe_instance_type_offerings.return_value = {
            'InstanceTypeOfferings': [
                {'InstanceType': 'p4d.24xlarge'}
            ]
        }
        
        # Mock AZ mapping
        mock_ec2.describe_availability_zones.return_value = {
            'AvailabilityZones': [
                {'ZoneName': 'us-east-1a', 'ZoneId': 'use1-az1'}
            ]
        }
        
        # Mock spot prices
        mock_ec2.describe_spot_price_history.return_value = {
            'SpotPriceHistory': [
                {
                    'InstanceType': 'p4d.24xlarge',
                    'AvailabilityZone': 'us-east-1a',
                    'SpotPrice': '6.5080'
                }
            ]
        }
        
        # Mock placement scores
        mock_ec2.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        
        # Mock GPU info
        mock_ec2.describe_instance_types.return_value = {
            'InstanceTypes': [{
                'GpuInfo': {
                    'Gpus': [{'Count': 8, 'Name': 'A100'}]
                }
            }]
        }
        
        # Run analysis
        advisor = GPUAdvisor(regions=["us-east-1"])
        results = advisor.get_best_spot_options()
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].instance_type, "p4d.24xlarge")
        self.assertEqual(results[0].score, 9)
        self.assertAlmostEqual(results[0].price, 6.5080, places=4)
    
    @patch('boto3.client')
    def test_capacity_block_workflow(self, mock_boto):
        """Test complete capacity block workflow"""
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        
        # Mock instance types
        mock_ec2.describe_instance_type_offerings.return_value = {
            'InstanceTypeOfferings': [
                {'InstanceType': 'p5.48xlarge'}
            ]
        }
        
        # Mock AZ mapping
        mock_ec2.describe_availability_zones.return_value = {
            'AvailabilityZones': [
                {'ZoneName': 'us-east-1f', 'ZoneId': 'use1-az5'}
            ]
        }
        
        # Mock capacity blocks
        start_date = datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc)
        mock_ec2.describe_capacity_block_offerings.return_value = {
            'CapacityBlockOfferings': [
                {
                    'StartDate': start_date,
                    'CapacityBlockDurationHours': 24,
                    'UpfrontFee': '755.00',
                    'AvailabilityZone': 'us-east-1f',
                    'CapacityBlockOfferingId': 'cb-123456'
                }
            ]
        }
        
        # Mock GPU info
        mock_ec2.describe_instance_types.return_value = {
            'InstanceTypes': [{
                'GpuInfo': {
                    'Gpus': [{'Count': 8, 'Name': 'H100'}]
                }
            }]
        }
        
        # Run analysis
        advisor = GPUAdvisor(regions=["us-east-1"])
        results = advisor.get_best_capacity_blocks()
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].available)
        self.assertEqual(results[0].duration_hours, 24)
        self.assertEqual(results[0].offering_id, 'cb-123456')
    
    @patch('boto3.client')
    def test_on_demand_workflow(self, mock_boto):
        """Test complete on-demand workflow"""
        # Create mock EC2 client
        mock_ec2 = Mock()
        mock_boto.return_value = mock_ec2
        
        # Mock instance type discovery
        mock_ec2.describe_instance_type_offerings.return_value = {
            'InstanceTypeOfferings': [
                {'InstanceType': 'p4d.24xlarge'}
            ]
        }
        
        # Mock AZ mapping
        mock_ec2.describe_availability_zones.return_value = {
            'AvailabilityZones': [
                {'ZoneName': 'us-east-1a', 'ZoneId': 'use1-az1'}
            ]
        }
        
        # Mock spot placement scores
        mock_ec2.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        
        # Mock GPU info
        mock_ec2.describe_instance_types.return_value = {
            'InstanceTypes': [{
                'GpuInfo': {
                    'Gpus': [{'Count': 8, 'Name': 'A100'}]
                }
            }]
        }
        
        # Mock pricing API
        mock_ec2.get_products.return_value = {
            'PriceList': [
                '''{
                    "product": {
                        "attributes": {
                            "preInstalledSw": "NA",
                            "capacitystatus": "Used"
                        }
                    },
                    "terms": {
                        "OnDemand": {
                            "term1": {
                                "priceDimensions": {
                                    "dim1": {
                                        "pricePerUnit": {"USD": "21.9576"}
                                    }
                                }
                            }
                        }
                    }
                }'''
            ]
        }
        
        # Run analysis
        advisor = GPUAdvisor(regions=["us-east-1"])
        results = advisor.get_best_on_demand_options()
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].available)
        self.assertIsNotNone(results[0].price)


class TestAWSClientIntegration(unittest.TestCase):
    """Test AWS client integration points"""
    
    def test_client_initialization(self):
        """Test client initializes correctly"""
        client = AWSClient()
        self.assertIsNotNone(client)
        self.assertEqual(client._gpu_cache, {})
        self.assertEqual(client._az_cache, {})
    
    def test_gpu_fallback_integration(self):
        """Test GPU fallback works for all known instances"""
        client = AWSClient()
        known_instances = [
            "p4d.24xlarge", "p4de.24xlarge",
            "p5.4xlarge", "p5.48xlarge",
            "p5e.48xlarge", "p5en.48xlarge",
            "p6-b200.48xlarge", "p6-b300.48xlarge"
        ]
        
        for instance in known_instances:
            gpu_info = client.get_gpu_info(instance)
            self.assertIsNotNone(gpu_info)
            self.assertNotEqual(gpu_info, "Unknown GPU")


if __name__ == '__main__':
    unittest.main()
