#!/usr/bin/env python3
"""
Test script to verify the CCRA agent fixes and run a simple test.
This script will help diagnose and fix the data saving issues.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main agent function
from main import run_agent, setup_logging

def check_environment():
    """Check if the environment is properly configured."""
    print("=== Environment Check ===")
    
    # Check if .env file exists
    env_file = ".env"
    if os.path.exists(env_file):
        print(f"[OK] Found {env_file}")
    else:
        print(f"[FAIL] Missing {env_file} - copy from .env.example and configure")
        return False

    # Check API keys
    from config import FIRECRAWL_API_KEY, OPENROUTER_API_KEY

    if FIRECRAWL_API_KEY:
        print("[OK] FIRECRAWL_API_KEY is set")
    else:
        print("[FAIL] FIRECRAWL_API_KEY is not set")
        return False

    if OPENROUTER_API_KEY:
        print("[OK] OPENROUTER_API_KEY is set")
    else:
        print("[FAIL] OPENROUTER_API_KEY is not set")
        return False

    # Check Firecrawl import
    try:
        from firecrawl import FirecrawlApp
        print("[OK] Firecrawl package imports correctly")
    except ImportError as e:
        print(f"[FAIL] Firecrawl import failed: {e}")
        print("Run: pip install -r requirements.txt")
        return False

    # Check runs directory
    runs_dir = "runs"
    if not os.path.exists(runs_dir):
        os.makedirs(runs_dir)
        print(f"[OK] Created {runs_dir} directory")
    else:
        print(f"[OK] {runs_dir} directory exists")
    
    return True

async def test_simple_run():
    """Run a simple test with the agent."""
    print("\n=== Running Simple Test ===")
    print("Mode: hazards, Type: heatwave, Scope: global")
    print("Max iterations: 3 (instead of 1)")
    
    try:
        # Run the agent with proper settings
        final_state = await run_agent(
            mode_name="hazards",
            which_name="heatwave",
            country_name=None,  # Global scope
            city_name=None,
            english_only_mode=True,  # Use English only for faster testing
            cli_config_overrides={"MAX_ITERATIONS": 3}  # Allow more iterations
        )
        
        print(f"\n=== Test Results ===")
        print(f"Final iteration: {final_state.current_iteration}")
        print(f"Searches conducted: {final_state.searches_conducted_count}")
        print(f"Structured data items: {len(final_state.structured_data)}")
        
        # Check final review action
        final_structured_review_action = final_state.metadata.get("next_step_after_structured_review", "N/A")
        print(f"Final structured review action: {final_structured_review_action}")
        
        # Check if data should be saved
        if final_structured_review_action == "accept":
            print("[OK] Data should be saved (final action is 'accept')")
        else:
            print(f"[FAIL] Data will not be saved (final action is '{final_structured_review_action}', not 'accept')")

        # Check runs directory for saved files
        runs_files = os.listdir("runs") if os.path.exists("runs") else []
        if runs_files:
            print(f"[OK] Found {len(runs_files)} files in runs directory:")
            for file in runs_files[-3:]:  # Show last 3 files
                print(f"  - {file}")
        else:
            print("[FAIL] No files found in runs directory")
        
        return final_state
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main test function."""
    print("CCRA Agent Fix Test")
    print("=" * 50)
    
    # Setup logging
    setup_logging(log_level="INFO", log_dir="logs")
    
    # Check environment
    if not check_environment():
        print("\n[ERROR] Environment check failed. Please fix the issues above.")
        return 1
    
    print("\n[SUCCESS] Environment check passed!")

    # Run the test
    result = asyncio.run(test_simple_run())

    if result:
        print("\n[SUCCESS] Test completed successfully!")
        print("\nNext steps:")
        print("1. Check the logs directory for detailed execution logs")
        print("2. Check the runs directory for saved results")
        print("3. If no data was saved, the structured reviewer didn't accept the results")
        print("4. Try running with more iterations or different parameters")
    else:
        print("\n[ERROR] Test failed!")
        print("Check the error messages above and fix any issues.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())