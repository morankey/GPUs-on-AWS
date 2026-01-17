#!/usr/bin/env python3
"""
P-Series GPU Analyzer
Analyze P-series GPU instance availability across AWS regions.

Usage:
    python main.py                  # Interactive menu
    python main.py spot [regions]   # Spot analysis
    python main.py blocks [regions] # Capacity blocks
    python main.py ondemand [regions] # On-demand pricing
    python main.py all [regions]    # Full analysis
"""

import sys
from cli.commands import (
    run_spot_analysis,
    run_capacity_block_analysis, 
    run_on_demand_analysis,
    run_full_analysis
)


def print_usage():
    print(__doc__)


def main():
    args = sys.argv[1:]
    
    # No args = interactive menu
    if not args:
        from p_series_menu import main as menu_main
        menu_main()
        return
    
    command = args[0].lower()
    regions = args[1:] if len(args) > 1 else None
    
    try:
        if command in ('spot', 's'):
            run_spot_analysis(regions)
        elif command in ('blocks', 'capacity', 'cb', 'b'):
            run_capacity_block_analysis(regions)
        elif command in ('ondemand', 'od', 'o'):
            run_on_demand_analysis(regions)
        elif command in ('all', 'a'):
            run_full_analysis(regions)
        elif command in ('help', '-h', '--help'):
            print_usage()
        else:
            print(f"Unknown command: {command}")
            print_usage()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
