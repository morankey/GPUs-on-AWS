# P-Series Immediate Short Term Single Instance Analyzer

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-EC2-orange.svg)](https://aws.amazon.com/ec2/)

## Summary

**Teams want immediate, single instance, short-term access to high-end GPU compute for adhoc AI and ML training jobs. This tool helps you find your P-series at the earliest date available by analyzing Nvidia P-Series instances on AWS right now.**

**Single Instance, Immediate Access, <1 Day Duration**

This tool analyzes your selected regions and shows:

1. **Capacity Blocks**: Best offering at the earliest date for the lowest price across the regions you select
2. **Spot Instances**: Best AZ to try spot for each instance based upon spot placement scores  
3. **On-Demand**: Uses spot scores to estimate likelihood of getting on-demand and shows highest opportunity AZs

**Important**: This tool provides analysis only - it does not guarantee availability or procure instances. You must still launch/purchase instances through AWS console, CLI, or API.

## Quick Start - Understanding Immediate P-Series Availability

### Prerequisites

- Python 3.10+
- AWS CLI configured with appropriate credentials
- boto3 library
- EC2 permissions for spot pricing, placement scores, availability zones, and capacity blocks
- Pricing API permissions
- **Sufficient AWS quotas** (see quota requirements below)

#### AWS Quota Requirements

**IMPORTANT**: P-series instances require quota increases from AWS default limits. New accounts start with 0 vCPU quotas for P-series instances. See [Quota Requirements](#quota-requirements) section below for detailed requirements and instructions.

#### AWS APIs Used
These scripts utilize the following AWS APIs to gather real-time data:

- **EC2 API**:
  - `describe_spot_price_history` - Current spot pricing across AZs
  - `get_spot_placement_scores` - Availability scores (1-10) for optimal placement
  - `describe_availability_zones` - AZ mapping and zone information
  - `describe_capacity_block_offerings` - Reserved capacity block availability

- **Pricing API**:
  - `get_products` - Real-time on-demand pricing data

All API calls are optimized for immediate availability analysis (quantity: 1, duration: ≤24 hours).

### AWS Configuration
Ensure your AWS credentials are configured before running any scripts:

```bash
aws configure
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=your_region
```

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd p-series-aws
```

2. **Create and activate a virtual environment:**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Verify installation:**
```bash
python --version  # Should show Python 3.10+
pip list          # Should show boto3 and dependencies
```

## Running the Analysis

**Important**: Make sure your virtual environment is activated before running the scripts:
```bash
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
```

The interactive menu is recommended for most users:

```bash
python p_series_menu.py
```

**Next Steps:**
1. **Select "All Options - Complete analysis"** for comprehensive evaluation across all procurement methods

2. **Select your regions of interest** from the available options

3. **Review the complete analysis** which will show:
   - **Spot pricing** with placement scores for cost optimization
   - **Capacity blocks** for guaranteed immediate availability 
   - **On-demand pricing** for maximum flexibility

This complete analysis provides everything needed to make an informed decision about GPU instance procurement for your short-term workloads:

**Spot Analysis**: Shows the single best AZ per instance type across all regions. Code selects highest placement score (availability indicator on 1-10 scale), with price as tiebreaker.

**Capacity Blocks**: Shows earliest available 24-hour blocks across all regions. Code picks most immediate availability, with shorter duration as tiebreaker. Blocks starting within 1 hour are marked as "Immediate".

**On-Demand**: Shows highest availability option per instance type across all regions. Code selects highest spot score (availability indicator), with lowest price as tiebreaker.

**Important**: Most H100+ instances (p5, p6) are only available via spot and capacity blocks - not on-demand at this time (1/11)

**When finished**, deactivate the virtual environment:
```bash
deactivate
```

### Sample Analysis Results

After running the complete analysis, you'll see results like these:

#### Complete Analysis Output (All Options)
When you select "All Options - Complete analysis" from the menu, you get comprehensive results across all three procurement methods:

```
BEST SPOT OPTIONS ACROSS REGIONS (Highest Score + Competitive Price)
Regions: us-east-1, us-east-2
====================================================================================
Instance           GPU          Best Score   Price/Hour   Region       AZ (AZ-ID)          
------------------------------------------------------------------------------------
p4d.24xlarge       8x A100      9            $8.2736      us-east-1    1a (use1-az1)      
p4de.24xlarge      8x A100      8            $9.1584      us-east-1    1b (use1-az2)      
p5.48xlarge        8x H100      7            $32.7726     us-east-1    1c (use1-az3)      
p5e.48xlarge       8x H200      6            $40.3200     us-east-1    1c (use1-az3)      
p5en.48xlarge      8x H200      5            $45.1200     us-east-1    1d (use1-az6)      

BEST CAPACITY BLOCKS ACROSS REGIONS (Soonest Start Times)
Regions: us-east-1, us-east-2 - Within 7 Days
====================================================================================
Instance           GPU      Available Start Date           Duration Total Cost Region       AZ       Offering ID 
-------------------------------------------------------------------------------------------------------------------
p4d.24xlarge       8x A100  Yes       2026-01-11 06:30 AM EST 24hrs    ($283)     us-east-1    1d       cb-0ecb45dda935ff136
p4de.24xlarge      8x A100  Yes       2026-01-11 06:30 AM EST 24hrs    ($354)     us-east-1    1d       cb-0871d34d9dc094dea
p5.4xlarge         1x H100  Yes       2026-01-11 06:30 AM EST 24hrs    ($94)      us-east-1    1f       cb-06bfeb47a343d237b
p5.48xlarge        8x H100  Yes       2026-01-14 06:30 AM EST 24hrs    ($755)     us-east-1    1f       cb-0f4351b051663609b
p5e.48xlarge       8x H200  No        N/A                  N/A      N/A        No availability N/A      N/A            
p5en.48xlarge      8x H200  Yes       2026-01-14 06:30 AM EST 24hrs    ($999)     us-east-1    1b       cb-0aba0f548f5580de2
p6-b200.48xlarge   8x B200  Yes       2026-01-11 06:30 AM EST 24hrs    ($1797)    us-east-1    1d       cb-025724580902276b8
p6-b300.48xlarge   8x B300  No        N/A                  N/A      N/A        No availability N/A      N/A            

BEST ON-DEMAND OPTIONS (Highest Availability + Competitive Price)
====================================================================================
Instance           GPU          Best Price   Region       Best AZ (AZ-ID) & Score       
------------------------------------------------------------------------------------
p4d.24xlarge       8x A100      $21.9576     us-east-2    2b (use2-az2) Score:9         
p4de.24xlarge      8x A100      $27.4471     us-east-1    1d (use1-az6) Score:9         
p5.4xlarge         1x H100      N/A          Spot & CB Only N/A                           
p5.48xlarge        8x H100      N/A          Spot & CB Only N/A                           
p5e.48xlarge       8x H200      N/A          Spot & CB Only N/A                           
p5en.48xlarge      8x H200      N/A          Spot & CB Only N/A                           
p6-b200.48xlarge   8x B200      N/A          Spot & CB Only N/A                           
p6-b300.48xlarge   8x B300      N/A          Spot & CB Only N/A                           
```

## Supported Instance Types

| Instance Type | GPU Type | GPU Count | GPU Memory | System Memory | CPU | Instance Store | Use Case |
|---------------|----------|-----------|------------|---------------|-----|----------------|----------|
| p4d.24xlarge | 8x A100 | 8 | 40GB each (320GB total) | 1152 GB | Intel Xeon Platinum 8175 | 8 x 1000 GB NVMe SSD | Training, Inference |
| p4de.24xlarge | 8x A100 | 8 | 80GB each (640GB total) | 1152 GB | Intel Xeon Platinum 8175 | 8 x 1000 GB NVMe SSD | Training, Inference |
| p5.4xlarge | 1x H100 | 1 | 80GB each (80GB total) | 192 GB | AMD EPYC 7R13 | 1 x 3800 GB NVMe SSD | Small-scale Training, Inference |
| p5.48xlarge | 8x H100 | 8 | 80GB each (640GB total) | 2048 GB | AMD EPYC 7R13 | 8 x 3800 GB NVMe SSD | Large Model Training |
| p5e.48xlarge | 8x H200 | 8 | 141GB each (1128GB total) | 2048 GB | AMD EPYC 7R13 | 8 x 3800 GB NVMe SSD | Large Model Training |
| p5en.48xlarge | 8x H200 | 8 | 141GB each (1128GB total) | 2048 GB | Intel Xeon Sapphire Rapids | 8 x 3800 GB NVMe SSD | Next-gen AI Workloads |
| p6-b200.48xlarge | 8x B200 | 8 | 192GB each (1536GB total) | 2048 GB | Intel Xeon Emerald Rapids | 8 x 3800 GB NVMe SSD | Next-gen AI Workloads |
| p6-b300.48xlarge | 8x B300 | 8 | 192GB each (1536GB total) | 4096 GB | Intel Xeon Emerald Rapids | 8 x 3800 GB NVMe SSD | Next-gen AI Workloads |

## Supported Regions

- us-east-1 (N. Virginia)
- us-east-2 (Ohio)
- us-west-1 (N. California)
- us-west-2 (Oregon)
- ap-northeast-1 (Tokyo)
- ap-northeast-2 (Seoul)
- ap-south-1 (Mumbai)

**Note**: Most H100-B300 instances (p5, p5e, p5en, p6-b200, p6-b300) are available via spot & capacity blocks only. **On-demand is primarily available for A100 instances (p4d, p4de)**.

## Quota Requirements

**IMPORTANT**: P-series instances require quota increases from AWS default limits. You must request quota increases before attempting to launch instances.

### Default P-Series Quotas (New Accounts)
- **On-Demand P instances**: 0 vCPUs (must request increase)
- **Spot P4/P3/P2 instances**: 0 vCPUs (must request increase) 
- **Spot P5 instances**: 0 vCPUs (must request increase)
- **Capacity Blocks**: Up to 64 instances per block, 256 instances total across blocks



### How to Request Quota Increases
1. Go to [AWS Service Quotas Console](https://console.aws.amazon.com/servicequotas/)
2. Search for "EC2" and select "Amazon Elastic Compute Cloud (Amazon EC2)"
3. Request increases for:
   - "Running On-Demand P instances" (for p4d/p4de on-demand)
   - "All P4, P3 and P2 Spot Instance Requests" (for p4d/p4de spot)
   - "All P5 Spot Instance Requests" (for p5+/p6 spot instances)
4. Specify the total vCPUs needed (e.g., 192 vCPUs for one p5.48xlarge)
5. Provide business justification for ML/AI workloads

**Note**: Quota increases typically take 24-48 hours to process. Plan accordingly for immediate availability needs.

### vCPU Requirements by Instance Type
| Instance Type | vCPUs Required | GPU Type | Quota Category |
|---------------|----------------|----------|----------------|
| p4d.24xlarge | 96 vCPUs | 8x A100 | On-Demand P / Spot P4/P3/P2 |
| p4de.24xlarge | 96 vCPUs | 8x A100 | On-Demand P / Spot P4/P3/P2 |
| p5.4xlarge | 16 vCPUs | 1x H100 | Spot P5 |
| p5.48xlarge | 192 vCPUs | 8x H100 | Spot P5 |
| p5e.48xlarge | 192 vCPUs | 8x H200 | Spot P5 |
| p5en.48xlarge | 192 vCPUs | 8x H200 | Spot P5 |
| p6-b200.48xlarge | 192 vCPUs | 8x B200 | Spot P5 |
| p6-b300.48xlarge | 192 vCPUs | 8x B300 | Spot P5 |

## Disclaimer

These scripts are provided as-is for monitoring AWS pricing and availability. Use at your own discretion for production workloads. Always verify pricing and availability through the AWS console before making purchasing decisions.

## SSH Configuration

The SSH configuration has been moved to `ssh-config.yaml` in the root directory. This contains template SSH settings for accessing development environments after launching P-series instances.

**Security Note**: The `ssh-config.yaml` file is excluded from git tracking. Update the configuration with your specific hostnames and key paths before use.

## Support

For issues, questions, or feature requests, please open an issue on GitLab.