#!/usr/bin/env python3
"""
P Series GPU Instance Analysis Menu
Choose between Spot, Capacity Blocks, or Both
"""

import subprocess
import sys
import termios
import tty


def getch():
    """Get a single character from stdin without pressing Enter"""
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
    """Display the main menu and get user choice with arrow key navigation"""
    options = [
        ("Capacity Blocks (CB) - Reserved capacity pricing and availability", "a"),
        ("Spot Instances - Dynamic spot pricing & placement", "b"),
        ("On-Demand - Fixed pricing with guaranteed capacity", "c"),
        ("All Options - Complete analysis (Spot + CB + On-Demand)", "d")
    ]
    
    selected = 0
    
    while True:
        # Clear screen and show menu
        print("\033[2J\033[H")  # Clear screen and move cursor to top
        print("=" * 60)
        print("P SERIES AVAILABILITY AND PRICING")
        print("=" * 60)
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
    """Get region selection from user"""
    options = [
        ("Multiple regions (select several)", "multi"),
        ("us-east-1 (N. Virginia)", "us-east-1"),
        ("us-east-2 (Ohio)", "us-east-2"),
        ("us-west-1 (N. California)", "us-west-1"),
        ("us-west-2 (Oregon)", "us-west-2"),
        ("ap-northeast-1 (Tokyo)", "ap-northeast-1"),
        ("ap-northeast-2 (Seoul)", "ap-northeast-2"),
        ("ap-south-1 (Mumbai)", "ap-south-1"),
        ("All regions", "all"),
        ("Custom (enter manually)", "custom")
    ]
    
    while True:
        # Clear screen and show menu
        print("\033[2J\033[H")  # Clear screen and move cursor to top
        print("Select regions to analyze:")
        print()
        
        for i, (name, _) in enumerate(options):
            print(f"  {i+1}) {name}")
        
        print()
        print("Enter your choice (1-10) or 'q' to quit:")
        
        try:
            user_input = input().strip()
            
            if user_input.lower() == 'q':
                sys.exit(0)
            elif user_input.isdigit():
                num = int(user_input) - 1
                if 0 <= num < len(options):
                    choice = options[num][1]
                    break
                else:
                    print(f"Invalid choice. Please enter 1-{len(options)}")
                    input("Press Enter to continue...")
            else:
                print("Invalid input. Please enter a number or 'q'")
                input("Press Enter to continue...")
                
        except (ValueError, KeyboardInterrupt):
            sys.exit(0)
    
    # Clear screen for result
    print("\033[2J\033[H")
    
    # Handle the selected choice
    if choice == "multi":
        return get_multi_region_selection(options[1:-2])  # Exclude multi, all, and custom options
    elif choice == "all":
        return ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "ap-northeast-1", "ap-northeast-2", "ap-south-1"]
    elif choice == "custom":
        regions_input = input("Enter regions separated by commas (e.g., us-east-1,us-west-2): ").strip()
        regions = [r.strip() for r in regions_input.split(',') if r.strip()]
        return regions if regions else ["us-east-1", "us-east-2"]
    else:
        return [choice]


def get_multi_region_selection(region_options):
    """Allow selection of multiple regions"""
    chosen = set()
    
    while True:
        # Clear screen and show menu
        print("\033[2J\033[H")
        print("Select multiple regions (enter numbers separated by commas):")
        print()
        
        for i, (name, code) in enumerate(region_options):
            marker = "✓" if code in chosen else " "
            print(f"  [{marker}] {i+1}) {name}")
        
        print()
        if chosen:
            print(f"Selected: {', '.join(sorted(chosen))}")
        else:
            print("No regions selected yet")
        
        print()
        print("Enter numbers (e.g., 1,3,5) to toggle regions, 'done' to finish, or 'q' to quit:")
        
        try:
            user_input = input().strip().lower()
            
            if user_input == 'q':
                sys.exit(0)
            elif user_input == 'done':
                if chosen:
                    return list(chosen)
                else:
                    print("Please select at least one region")
                    input("Press Enter to continue...")
            elif user_input:
                # Parse comma-separated numbers
                try:
                    numbers = [int(x.strip()) for x in user_input.split(',') if x.strip()]
                    for num in numbers:
                        if 1 <= num <= len(region_options):
                            code = region_options[num-1][1]
                            if code in chosen:
                                chosen.remove(code)
                            else:
                                chosen.add(code)
                        else:
                            print(f"Invalid number: {num}. Please use 1-{len(region_options)}")
                            input("Press Enter to continue...")
                            break
                except ValueError:
                    print("Invalid input. Please enter numbers separated by commas")
                    input("Press Enter to continue...")
            
        except KeyboardInterrupt:
            sys.exit(0)

def run_script(script_name, regions=None):
    """Run a Python script and handle errors"""
    try:
        print(f"\nRunning {script_name}...")
        print("=" * 80)
        
        # Pass regions as command line arguments if provided
        cmd = [sys.executable, script_name]
        if regions:
            cmd.extend(regions)
            
        result = subprocess.run(cmd, 
                              capture_output=False, 
                              text=True, 
                              check=True)
        print("=" * 80)
        print(f"✓ {script_name} completed successfully")
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error running {script_name}")
        print(f"Exit code: {e.returncode}")
        
    except FileNotFoundError:
        print(f"✗ Script {script_name} not found")
        print("Make sure all scripts are in the same directory")

def main():
    """Main menu loop"""
    while True:
        choice = show_menu()
        
        # Clear screen for results
        print("\033[2J\033[H")
        
        if choice == 'q':
            print("Goodbye!")
            break
            
        elif choice == 'a':
            print("🔍 Running Capacity Blocks Analysis...")
            regions = get_regions()
            run_script("p_series_capacity_blocks.py", regions)
            
        elif choice == 'b':
            print("🔍 Running Spot Analysis...")
            regions = get_regions()
            run_script("p_series_spot.py", regions)
            
        elif choice == 'c':
            print("🔍 Running On-Demand Analysis...")
            regions = get_regions()
            run_script("p_series_on_demand.py", regions)
            
        elif choice == 'd':
            print("🔍 Running Complete Analysis (Spot + Capacity Blocks + On-Demand)...")
            regions = get_regions()
            run_script("p_series_spot.py", regions)
            print("\n" + "="*80)
            run_script("p_series_capacity_blocks.py", regions)
            print("\n" + "="*80)
            run_script("p_series_on_demand.py", regions)
        
        print("\n" + "="*60)
        input("Press Enter to return to menu...")
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nUnexpected error: {e}")