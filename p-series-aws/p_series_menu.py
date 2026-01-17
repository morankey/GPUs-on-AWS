#!/usr/bin/env python3
"""
P Series GPU Instance Analysis Menu

Interactive terminal menu for analyzing P-series GPU instance availability
across spot, capacity blocks, and on-demand procurement methods.

Note: Uses Unix-specific terminal features (termios, tty) for arrow key navigation.
This menu is designed for macOS/Linux systems only.
"""

import sys
import termios
import tty

from cli.commands import run_spot_analysis, run_capacity_block_analysis, run_on_demand_analysis
from core.aws_client import AWSClient

# Menu display constants
MENU_SEPARATOR_WIDTH = 60

# ANSI escape codes for terminal control
CLEAR_SCREEN = "\033[2J\033[H"

# Region display names
REGION_NAMES = {
    "us-east-1": "N. Virginia",
    "us-east-2": "Ohio",
    "us-west-2": "Oregon",
    "eu-west-1": "Ireland",
    "eu-central-1": "Frankfurt",
    "ap-northeast-1": "Tokyo",
    "ap-southeast-1": "Singapore",
    "ap-southeast-2": "Sydney",
}


def getch():
    """
    Get a single character from stdin without requiring Enter.
    
    Handles arrow key escape sequences for menu navigation.
    Returns the character or escape sequence read.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ord(ch) == 27:  # ESC sequence
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def show_menu():
    """
    Display the main menu and get user choice.
    
    Supports arrow key navigation and direct letter selection.
    Returns the selected option letter or 'q' to quit.
    """
    options = [
        ("All Options (recommended) - Complete analysis (Spot + Capacity Blocks + On-Demand)", "a"),
        ("Capacity Blocks - Reserved capacity pricing and availability", "b"),
        ("Spot Instances - Dynamic spot pricing & placement", "c"),
        ("On-Demand - Fixed pricing with guaranteed capacity", "d")
    ]
    
    selected = 0
    
    while True:
        print(CLEAR_SCREEN, end="")
        print("=" * MENU_SEPARATOR_WIDTH)
        print("P SERIES AVAILABILITY AND PRICING")
        print("=" * MENU_SEPARATOR_WIDTH)
        print()
        print("What would you like to explore?")
        print("Use ↑/↓ arrows to navigate, Enter to select, 'q' to quit")
        print()
        
        for i, (name, _) in enumerate(options):
            if i == selected:
                print(f"→ {chr(97+i)}) {name}")
            else:
                print(f"  {chr(97+i)}) {name}")
        
        print()
        print("Press 'q' to quit")
        
        # Get input
        key = getch()
        
        if key == 'q' or key == 'Q':
            return 'q'
        elif key == '\r' or key == '\n':  # Enter key
            return options[selected][1]
        elif key == '\033[A':  # Up arrow
            selected = (selected - 1) % len(options)
        elif key == '\033[B':  # Down arrow
            selected = (selected + 1) % len(options)
        elif key.lower() in [opt[1] for opt in options]:
            return key.lower()


def get_regions():
    """
    Get region selection from user.
    
    Auto-detects user's active regions and shows them first for easy selection.
    Returns a list of region codes, or 'back' to return to main menu.
    """
    print(CLEAR_SCREEN, end="")
    print("Detecting your active AWS regions...")
    
    # Auto-detect regions
    client = AWSClient()
    priority_regions, other_regions = client.get_suggested_regions()
    default_region = client.get_default_region()
    
    print(CLEAR_SCREEN, end="")
    
    # Build menu options
    options = []
    
    # Quick select option if we found active regions
    if priority_regions:
        if len(priority_regions) == 1:
            region = priority_regions[0]
            options.append((f"★ {region} ({REGION_NAMES.get(region, '')}) - Your active region", "auto"))
        else:
            regions_display = ", ".join([f"{r}" for r in priority_regions])
            options.append((f"★ {regions_display} - Your active regions", "auto"))
    
    # Multi-select option
    options.append(("Select regions manually...", "multi"))
    
    # Show other regions as individual options (flat list, no section header)
    for region in other_regions:
        options.append((f"{region} ({REGION_NAMES.get(region, '')})", region))
    
    # Display menu
    while True:
        print(CLEAR_SCREEN, end="")
        print("Select regions to analyze:")
        print()
        
        display_num = 1
        option_map = {}  # Maps display number to option
        
        for name, code in options:
            option_map[display_num] = (name, code)
            if code == "auto":
                print(f"  {display_num}) {name}  ← Quick select")
            else:
                print(f"  {display_num}) {name}")
            display_num += 1
        
        print()
        print(f"Enter choice (1-{display_num-1}), 'b' to go back, or 'q' to quit:")
        
        try:
            user_input = input().strip()
            
            if user_input.lower() == 'q':
                sys.exit(0)
            elif user_input.lower() == 'b':
                return 'back'
            elif user_input.isdigit():
                num = int(user_input)
                if num in option_map:
                    _, code = option_map[num]
                    if code == "auto":
                        return priority_regions
                    elif code == "multi":
                        all_regions = priority_regions + other_regions
                        result = get_multi_region_selection(all_regions, priority_regions, default_region)
                        return result if result != 'back' else 'back'
                    else:
                        return [code]
                else:
                    print(f"Invalid choice. Please enter 1-{display_num-1}")
                    input("Press Enter to continue...")
            else:
                print("Invalid input. Please enter a number, 'b' to go back, or 'q'")
                input("Press Enter to continue...")
                
        except (ValueError, KeyboardInterrupt):
            sys.exit(0)


def get_multi_region_selection(all_regions, priority_regions, default_region):
    """
    Allow selection of multiple regions with interactive toggle interface.
    
    Args:
        all_regions: List of all available region codes
        priority_regions: List of detected/active regions (shown first, pre-selected)
        default_region: User's default region (marked in display)
        
    Returns:
        List of selected region codes, or 'back' to return to previous menu.
    """
    # Pre-select priority regions
    chosen = set(priority_regions) if priority_regions else set()
    
    while True:
        print(CLEAR_SCREEN, end="")
        print("Select multiple regions (enter numbers to toggle, or use shortcuts):")
        print()
        
        display_num = 1
        region_map = {}
        
        # Show all regions in a flat list (priority regions first, then others)
        ordered_regions = list(priority_regions) + [r for r in all_regions if r not in priority_regions]
        
        for region in ordered_regions:
            marker = "✓" if region in chosen else " "
            default_marker = " ★" if region == default_region else ""
            print(f"  [{marker}] {display_num}) {region} ({REGION_NAMES.get(region, '')}){default_marker}")
            region_map[display_num] = region
            display_num += 1
        
        print()
        if chosen:
            print(f"Selected: {', '.join(sorted(chosen))}")
        else:
            print("No regions selected")
        
        print()
        print("Commands: numbers to toggle | 'all' | 'none' | 'done' | 'b' back | 'q' quit")
        print()
        print("Enter command:")
        
        try:
            user_input = input().strip().lower()
            
            if user_input == 'q':
                sys.exit(0)
            elif user_input == 'b':
                return 'back'
            elif user_input == 'done':
                if chosen:
                    return list(chosen)
                else:
                    print("Please select at least one region")
                    input("Press Enter to continue...")
            elif user_input == 'all':
                chosen = set(all_regions)
            elif user_input == 'none':
                chosen = set()
            elif user_input:
                # Parse comma-separated numbers
                try:
                    numbers = [int(x.strip()) for x in user_input.split(',') if x.strip()]
                    for num in numbers:
                        if num in region_map:
                            region = region_map[num]
                            if region in chosen:
                                chosen.remove(region)
                            else:
                                chosen.add(region)
                        else:
                            print(f"Invalid number: {num}")
                            input("Press Enter to continue...")
                            break
                except ValueError:
                    print("Invalid input. Enter numbers separated by commas, or a command.")
                    input("Press Enter to continue...")
            
        except KeyboardInterrupt:
            sys.exit(0)


def main():
    """Main menu loop"""
    while True:
        choice = show_menu()
        
        print(CLEAR_SCREEN, end="")
        
        if choice == 'q':
            print("Goodbye!")
            break
            
        elif choice == 'a':
            # Complete analysis - all three types
            regions = get_regions()
            if regions == 'back':
                continue
            run_spot_analysis(regions)
            print()
            run_capacity_block_analysis(regions)
            print()
            run_on_demand_analysis(regions)
            
        elif choice == 'b':
            regions = get_regions()
            if regions == 'back':
                continue
            run_capacity_block_analysis(regions)
            
        elif choice == 'c':
            regions = get_regions()
            if regions == 'back':
                continue
            run_spot_analysis(regions)
            
        elif choice == 'd':
            regions = get_regions()
            if regions == 'back':
                continue
            run_on_demand_analysis(regions)
        
        print("\n" + "=" * MENU_SEPARATOR_WIDTH)
        input("Press Enter to return to menu...")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
