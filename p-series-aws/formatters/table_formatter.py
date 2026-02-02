"""
Table formatter for P-Series analysis output.

Handles all display/printing logic, separated from business logic.
Provides consistent table formatting for spot, capacity block, and on-demand results.
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from core.models import SpotResult, CapacityBlockResult, OnDemandResult


# Display constants
DEFAULT_TERMINAL_WIDTH = 120

# Table formatting widths
TABLE_WIDTH_STANDARD = 84
TABLE_WIDTH_WIDE = 100

# US Eastern timezone (handles DST automatically)
EASTERN_TZ = ZoneInfo("America/New_York")

# Spinner frames for smooth animation
SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


class Spinner:
    """Animated spinner with status text for smooth progress indication."""
    
    def __init__(self, message: str = "Loading"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = None
        self._frame_idx = 0
    
    def _animate(self):
        while not self._stop_event.is_set():
            frame = SPINNER_FRAMES[self._frame_idx % len(SPINNER_FRAMES)]
            text = f"\r{frame} {self.message}"
            sys.stdout.write(f"{text:<60}")
            sys.stdout.flush()
            self._frame_idx += 1
            time.sleep(0.08)
    
    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
    
    def update(self):
        """No-op for compatibility - spinner just animates continuously."""
        pass
    
    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.2)
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()


class TableFormatter:
    """
    Formats and displays P-series analysis results.
    
    Provides methods for printing spot, capacity block, and on-demand results
    in consistent table formats. Supports both cross-region summary views
    and per-region detailed views.
    """
    
    def __init__(self):
        self.terminal_width = self._get_terminal_width()
        self._spinner = None
    
    def _get_terminal_width(self) -> int:
        """Get terminal width, default if unable to detect"""
        try:
            return os.get_terminal_size().columns
        except OSError:
            return DEFAULT_TERMINAL_WIDTH
    
    def start_progress(self, message: str = "Analyzing"):
        """Start an animated spinner with the given message."""
        self._spinner = Spinner(message)
        self._spinner.start()
    
    def update_progress(self, current: int = 0, total: int = 0):
        """No-op for compatibility - spinner just animates continuously."""
        pass
    
    def stop_progress(self):
        """Stop and clear the spinner."""
        if self._spinner:
            self._spinner.stop()
            self._spinner = None
    
    # Legacy methods for backward compatibility
    def show_progress(self, current: int = 0, total: int = 0, prefix: str = "Progress"):
        """Display progress (starts spinner on first call)."""
        if self._spinner is None:
            self.start_progress(prefix)
    
    def clear_progress(self):
        """Clear progress indicator."""
        self.stop_progress()
    
    def print_spot_results(self, results: list[SpotResult], regions: list[str]):
        """
        Print spot analysis results table.
        
        Shows the best spot option per instance type across all analyzed regions,
        selected by highest placement score with lowest price as tiebreaker.
        """
        print(f"BEST SPOT OPTIONS ACROSS REGIONS (Highest Score + Competitive Price)")
        print(f"Regions: {', '.join(regions)}")
        print("=" * TABLE_WIDTH_STANDARD)
        print(f"{'Instance':<18} {'GPU':<12} {'Best Score':<10} {'Price/Hour':<12} {'Region':<12} {'AZ (AZ-ID)':<20}")
        print("-" * TABLE_WIDTH_STANDARD)
        
        for r in results:
            if r.score > 0:
                score_str = str(r.score)
                price_str = f"${r.price:.4f}"
                region_str = r.region
                az_str = r.az_display
            else:
                score_str = "N/A"
                price_str = "N/A"
                region_str = "No availability"
                az_str = "N/A"
            
            print(f"{r.instance_type:<18} {r.gpu_type:<12} {score_str:<10} {price_str:<12} {region_str:<12} {az_str:<20}")
        
        print("\n" + "=" * TABLE_WIDTH_STANDARD)
        print("Important: Shows highest placement score per instance type, with lowest price as tiebreaker.")
    
    def print_spot_results_by_region(self, results_by_region: dict[str, list[SpotResult]], regions: list[str]):
        """
        Print spot results grouped by region.
        
        Used for single-region analysis to show detailed per-region breakdown.
        """
        print(f"SPOT PRICING - BEST AVAILABILITY (Highest Score, Lowest Price Tiebreaker)")
        print(f"Regions: {', '.join(regions)}")
        print("=" * TABLE_WIDTH_STANDARD)
        
        for region, results in results_by_region.items():
            print(f"{'Instance Type':<18} {'GPU':<12} {'Score':<6} {'Price/Hour':<12} {'AZ (AZ-ID)':<20}")
            print("-" * 72)
            
            for r in results:
                if r.score > 0:
                    score_str = str(r.score)
                    price_str = f"${r.price:.4f}"
                    az_str = r.az_display
                else:
                    score_str = "N/A"
                    price_str = "N/A"
                    az_str = "N/A"
                
                print(f"{r.instance_type:<18} {r.gpu_type:<12} {score_str:<6} {price_str:<12} {az_str:<20}")
        
        print("\n" + "=" * TABLE_WIDTH_STANDARD)
        print("Important: Shows highest placement score per instance type, with lowest price as tiebreaker.")
    
    def print_capacity_block_results(self, results: list[CapacityBlockResult], regions: list[str]):
        """
        Print capacity block results table.
        
        Shows the best capacity block per instance type across all analyzed regions,
        selected by earliest start time with shortest duration as tiebreaker.
        """
        print(f"BEST CAPACITY BLOCKS ACROSS REGIONS (Soonest Start Times)")
        print(f"Regions: {', '.join(regions)} - Within 7 Days")
        print("=" * TABLE_WIDTH_WIDE)
        
        # Check if any capacity blocks are available
        has_any_available = any(r.available for r in results)
        
        if not has_any_available:
            print()
            print("  ⚠ No capacity blocks available in the selected region(s)")
            print("  Try expanding your search to additional regions.")
            print()
            print("=" * TABLE_WIDTH_WIDE)
            return
        
        print(f"{'Instance':<18} {'GPU':<8} {'Available':<9} {'Start Date':<20} {'Duration':<8} {'Total Cost':<10} {'Region':<12} {'AZ (AZ-ID)':<12} {'Offering ID':<12}")
        print("-" * TABLE_WIDTH_WIDE)
        
        for r in results:
            if r.available:
                # Format start date
                now = datetime.now(timezone.utc)
                time_diff = (r.start_date - now).total_seconds() / 3600
                
                if time_diff <= 1:
                    start_str = "Immediate"
                else:
                    # Convert to US Eastern for display (handles DST automatically)
                    eastern_time = r.start_date.astimezone(EASTERN_TZ)
                    start_str = eastern_time.strftime('%m/%d %I:%M %p')
                
                duration_str = f"{r.duration_hours}hrs"
                cost_str = f"(${r.upfront_fee})"
                region_str = r.region
                az_str = r.az_display
                offering_str = r.offering_id[:12] if r.offering_id and len(r.offering_id) > 12 else (r.offering_id or "N/A")
                avail_str = "Yes"
            else:
                start_str = "N/A"
                duration_str = "N/A"
                cost_str = "N/A"
                region_str = "No availability"
                az_str = "N/A"
                offering_str = "N/A"
                avail_str = "No"
            
            print(f"{r.instance_type:<18} {r.gpu_type:<8} {avail_str:<9} {start_str:<20} {duration_str:<8} {cost_str:<10} {region_str:<12} {az_str:<12} {offering_str:<12}")
        
        print("\n" + "=" * TABLE_WIDTH_WIDE)
        print("Important: Shows earliest available blocks. Code picks most immediate availability, with shorter duration as tiebreaker.")
    
    def print_capacity_block_results_by_region(self, results_by_region: dict[str, list[CapacityBlockResult]], regions: list[str]):
        """
        Print capacity block results grouped by region.
        
        Used for single-region analysis to show detailed per-region breakdown.
        """
        print(f"CAPACITY BLOCKS - IMMEDIATE AVAILABILITY (1 Instance, ≤24 Hours)")
        print(f"Regions: {', '.join(regions)} - Within 7 Days")
        print("=" * TABLE_WIDTH_WIDE)
        
        for region, results in results_by_region.items():
            # Check if region has any available capacity blocks
            has_any_available = any(r.available for r in results)
            
            if not has_any_available:
                print()
                print("  ⚠ No capacity blocks available in this region")
                continue
            
            print(f"{'Instance Type':<18} {'GPU':<8} {'Avail':<6} {'Start Date':<20} {'Dur':<6} {'Total Cost':<10} {'AZ (AZ-ID)':<16} {'Offering ID':<12}")
            print("-" * 100)
            
            for r in results:
                if r.available:
                    now = datetime.now(timezone.utc)
                    time_diff = (r.start_date - now).total_seconds() / 3600
                    
                    if time_diff <= 1:
                        start_str = "Immediate"
                    else:
                        # Convert to US Eastern for display (handles DST automatically)
                        eastern_time = r.start_date.astimezone(EASTERN_TZ)
                        start_str = eastern_time.strftime('%Y-%m-%d %I:%M %p EST')
                    
                    duration_str = f"{r.duration_hours}hrs"
                    cost_str = f"(${r.upfront_fee})"
                    az_str = r.az_display
                    offering_str = r.offering_id[:12] if r.offering_id and len(r.offering_id) > 12 else (r.offering_id or "N/A")
                    avail_str = "Yes"
                else:
                    start_str = "N/A"
                    duration_str = "N/A"
                    cost_str = "N/A"
                    az_str = "N/A"
                    offering_str = "N/A"
                    avail_str = "No"
                
                print(f"{r.instance_type:<18} {r.gpu_type:<8} {avail_str:<6} {start_str:<20} {duration_str:<6} {cost_str:<10} {az_str:<16} {offering_str:<12}")
        
        print("\n" + "=" * TABLE_WIDTH_WIDE)
        print("Important: Shows earliest available blocks. Code picks most immediate availability, with shorter duration as tiebreaker.")
    
    def print_on_demand_results(self, results: list[OnDemandResult], regions: list[str]):
        """
        Print on-demand results table.
        
        Shows the best on-demand option per instance type across all analyzed regions.
        Note: Most P5+ instances show 'Spot & CB Only' as they're not available on-demand.
        """
        print(f"BEST ON-DEMAND OPTIONS (Highest Availability + Competitive Price)")
        print("=" * TABLE_WIDTH_STANDARD)
        print(f"{'Instance':<18} {'GPU':<12} {'Best Price':<12} {'Region':<12} {'AZ / Availability':<30}")
        print("-" * TABLE_WIDTH_STANDARD)
        
        for r in results:
            if r.available:
                price_str = f"${r.price:.4f}"
                region_str = r.region
                az_str = r.az_display
            else:
                price_str = "N/A"
                region_str = "Spot & CB Only"
                az_str = "N/A"
            
            print(f"{r.instance_type:<18} {r.gpu_type:<12} {price_str:<12} {region_str:<12} {az_str:<30}")
        
        print("\n" + "=" * TABLE_WIDTH_STANDARD)
        print("Important: Likelihood to launch - Likely = Decent chance | Possible = Low chance | Unlikely = Low to zero chance")
