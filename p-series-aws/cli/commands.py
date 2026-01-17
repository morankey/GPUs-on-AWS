#!/usr/bin/env python3
"""
CLI commands for P-Series analysis.
Thin wrappers that connect GPUAdvisor to TableFormatter.
"""

import sys
from core import GPUAdvisor
from formatters import TableFormatter


def run_spot_analysis(regions: list = None):
    """Run spot instance analysis"""
    formatter = TableFormatter()
    
    def progress_callback(current, total):
        formatter.show_progress(current, total, "Analyzing spot data")
    
    advisor = GPUAdvisor(regions=regions, progress_callback=progress_callback)
    
    if len(advisor.regions) == 1:
        results = advisor.get_spot_options_by_region()
        formatter.clear_progress()
        formatter.print_spot_results_by_region(results, advisor.regions)
    else:
        results = advisor.get_best_spot_options()
        formatter.clear_progress()
        formatter.print_spot_results(results, advisor.regions)


def run_capacity_block_analysis(regions: list = None):
    """Run capacity block analysis"""
    formatter = TableFormatter()
    
    def progress_callback(current, total):
        formatter.show_progress(current, total, "Analyzing capacity blocks")
    
    advisor = GPUAdvisor(regions=regions, progress_callback=progress_callback)
    
    if len(advisor.regions) == 1:
        results = advisor.get_capacity_blocks_by_region()
        formatter.clear_progress()
        formatter.print_capacity_block_results_by_region(results, advisor.regions)
    else:
        results = advisor.get_best_capacity_blocks()
        formatter.clear_progress()
        formatter.print_capacity_block_results(results, advisor.regions)


def run_on_demand_analysis(regions: list = None):
    """Run on-demand analysis"""
    formatter = TableFormatter()
    
    def progress_callback(current, total):
        formatter.show_progress(current, total, "Fetching pricing data")
    
    advisor = GPUAdvisor(regions=regions, progress_callback=progress_callback)
    results = advisor.get_best_on_demand_options()
    formatter.clear_progress()
    formatter.print_on_demand_results(results, advisor.regions)


def run_full_analysis(regions: list = None):
    """Run all three analyses"""
    run_spot_analysis(regions)
    print()
    run_capacity_block_analysis(regions)
    print()
    run_on_demand_analysis(regions)


# Entry point functions for direct script execution
def spot_main():
    regions = sys.argv[1:] if len(sys.argv) > 1 else None
    try:
        run_spot_analysis(regions)
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")
        sys.exit(1)


def capacity_blocks_main():
    regions = sys.argv[1:] if len(sys.argv) > 1 else None
    try:
        run_capacity_block_analysis(regions)
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure AWS credentials are configured and you have proper permissions.")
        sys.exit(1)


def on_demand_main():
    regions = sys.argv[1:] if len(sys.argv) > 1 else None
    try:
        run_on_demand_analysis(regions)
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        sys.exit(1)
