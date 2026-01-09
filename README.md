[README.md](https://github.com/user-attachments/files/24532592/README.md)
# P Series AWS GPU Instance Analysis Scripts - Short Term and Immediate Access

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-EC2-orange.svg)](https://aws.amazon.com/ec2/)

## 🎯 Summary

**Teams want immediate, single instance, short-term access to high-end GPU compute for adhoc jobs AI and ML training jobs. This simplifies the process of finding what Nvidia P-Series instances are available on AWS at this moment in time.**

AWS offers P-series GPU instances (A100, H100, H200, B200, B300) through multiple procurement options, each with different availability, pricing, and commitment models:

- **Spot Instances**: Up to 90% cost savings but can be interrupted
- **Capacity Blocks**: Reserved capacity with guaranteed availability for specific durations. This option is for reserving instances similar to a hotel booking - usually 24 hours but can be less. 
- **On-Demand**: Immediate availability with no commitment (not available for all p-instances)

**Our Solution**: This toolkit provides comprehensive analysis across all three procurement methods for immediate availability, enabling customers to make informed decisions based on real-time availability, pricing, and placement optimization.

---

A collection of Python scripts for analyzing AWS P-series GPU instance availability, pricing, and placement across spot instances, capacity blocks, and on-demand instances. These scripts focus on immediate availability for **quantity of 1 for one day or less**.

## 🚀 Quick Start - Understanding Immediate P-Series Availability

### Prerequisites

- Python 3.10+
- AWS CLI configured with appropriate credentials
- boto3 library
- EC2 permissions for spot pricing, placement scores, availability zones, and capacity blocks
- Pricing API permissions

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

## 🚀 Running the Analysis

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

4. **Compare results** across all three procurement methods to find the best fit for your specific needs:
   - **Lowest cost**: Look for spot instances with high placement scores
   - **Guaranteed capacity**: Compare capacity blocks vs on-demand pricing
   - **Best availability**: Identify regions with immediate capacity blocks or high spot scores

This full analysis provides everything needed to make an informed decision about GPU instance procurement for your short-term workloads.

**When finished**, deactivate the virtual environment:
```bash
deactivate
```

### Sample Analysis Results

After running the complete analysis, you'll see results like these:

#### Spot Analysis - Price-Capacity Optimized
This analysis identifies the best availability zones for each P-series instance type using [AWS Spot Placement Scores](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-placement-score.html) (1-10 scale). Higher scores indicate better capacity availability and lower interruption risk. The AZ-ID shows the optimal zone for launching each instance type.

```
PRICE-CAPACITY OPTIMIZED RECOMMENDATIONS (Best Value: High Score + Low Price)
Regions: us-east-1, us-west-2
================================================================================
Instance Type      GPU      Score  Price/Hour  AZ (AZ-ID)           Region    
--------------------------------------------------------------------------------
p4d.24xlarge      8x A100    9     $8.2736     us-east-1a (use1-az1)  us-east-1
p4de.24xlarge     8x A100    8     $9.1584     us-east-1b (use1-az2)  us-east-1
p5.48xlarge       8x H100    7     $32.7726    us-west-2a (usw2-az1)  us-west-2
p5e.48xlarge      8x H200    6     $40.3200    us-east-1c (use1-az3)  us-east-1
p5en.48xlarge     8x H200    5     $45.1200    us-west-2b (usw2-az2)  us-west-2
```

#### Capacity Blocks - Immediate Availability
Shows reserved capacity blocks available for immediate booking with guaranteed availability. Each entry shows the specific AZ-ID where capacity blocks are available, the exact start time, duration in hours, and upfront cost. This gives you the best zones to reserve guaranteed GPU capacity for your specific time requirements.

```
CAPACITY BLOCKS AVAILABILITY & PRICING (A100-B300 GPUs)
Regions: us-east-1, us-west-2 - Immediate Availability Focus
================================================================================
Region       Instance Type      GPU          Available  Start Date           Duration  Upfront Fee  AZ (AZ-ID)        
--------------------------------------------------------------------------------
us-east-1    p4d.24xlarge       8x A100      Yes        Immediately Available 20hrs     $245         us-east-1d (use1-az6)
             p4de.24xlarge      8x A100      Yes        Immediately Available 20hrs     $306         us-east-1d (use1-az6)
             p5.4xlarge         1x H100      Yes        Immediately Available 20hrs     $82          us-east-1f (use1-az5)
             p5.48xlarge        8x H100      Yes        2026-01-10 11:30      24hrs     $755         us-east-1f (use1-az5)
             p5e.48xlarge       8x H200      No         N/A                    N/A       N/A          N/A
             p5en.48xlarge      8x H200      Yes        2026-01-14 11:30      24hrs     $999         us-east-1b (use1-az2)
             p6-b200.48xlarge   8x B200      Yes        Immediately Available 20hrs     $1551        us-east-1d (use1-az6)
             p6-b300.48xlarge   8x B300      No         N/A                    N/A       N/A          N/A

us-west-2    p4d.24xlarge       8x A100      Yes        Immediately Available 20hrs     $244         us-west-2a (usw2-az2)
             p4de.24xlarge      8x A100      Yes        Immediately Available 20hrs     $306         us-west-2a (usw2-az2)
             p5.4xlarge         1x H100      Yes        2026-01-13 11:30      24hrs     $94          us-west-2c (usw2-az3)
             p5.48xlarge        8x H100      Yes        Immediately Available 20hrs     $652         us-west-2a (usw2-az2)
             p5e.48xlarge       8x H200      Yes        Immediately Available 20hrs     $825         us-west-2c (usw2-az3)
             p5en.48xlarge      8x H200      No         N/A                    N/A       N/A          N/A
             p6-b200.48xlarge   8x B200      Yes        Immediately Available 20hrs     $1550        us-west-2d (usw2-az4)
             p6-b300.48xlarge   8x B300      Yes        Immediately Available 20hrs     $1938        us-west-2a (usw2-az2)
```

#### On-Demand - Best Available Options
Displays the lowest-priced on-demand instances across regions with optimal availability zone recommendations. The "Best AZ" shows the specific AZ-ID with the highest [spot placement score](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-placement-score.html) (1-10 scale). We use spot placement scores as an indicator of on-demand capacity availability since spot and on-demand instances share the same underlying capacity pools - higher spot scores typically indicate better on-demand availability and launch success rates in that zone.

```
BEST ON-DEMAND OPTIONS (Lowest Price + Available)
================================================================================
Instance           GPU      Best Price   Region       Best AZ (AZ-ID) & Score                    
--------------------------------------------------------------------------------
p4d.24xlarge      8x A100   $21.9576     us-east-2    Best: use2-az1 (score: 9)
p4de.24xlarge     8x A100   $27.4471     us-east-1    Best: use1-az6 (score: 9)
p5.4xlarge        1x H100   N/A          Spot & CB Only  N/A
p5.48xlarge       8x H100   N/A          Spot & CB Only  N/A
p5e.48xlarge      8x H200   N/A          Spot & CB Only  N/A
p5en.48xlarge     8x H200   N/A          Spot & CB Only  N/A
p6-b200.48xlarge  8x B200   N/A          Spot & CB Only  N/A
p6-b300.48xlarge  8x B300   N/A          Spot & CB Only  N/A
```

## 🖥️ Supported Instance Types

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

## 🌍 Supported Regions

- us-east-1 (N. Virginia)
- us-east-2 (Ohio)
- us-west-1 (N. California)
- us-west-2 (Oregon)
- ap-northeast-1 (Tokyo)
- ap-northeast-2 (Seoul)
- ap-south-1 (Mumbai)

**Note**: Most H100-B300 instances (p5, p5e, p5en, p6-b200, p6-b300) are available via spot & capacity blocks only. **On-demand is primarily available for A100 instances (p4d, p4de)**.

## ⚠️ Disclaimer

These scripts are provided as-is for monitoring AWS pricing and availability. Use at your own discretion for production workloads. Always verify pricing and availability through the AWS console before making purchasing decisions.

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitLab.
