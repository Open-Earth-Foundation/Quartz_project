"""
Script to run all tests for the GHGI Dataset Discovery Agent.
This is a convenience wrapper around pytest.
"""
import os
import sys
import subprocess

def run_tests():
    """Run all tests using pytest."""
    # Get the directory containing this script
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine the tests directory
    tests_dir = os.path.join(root_dir, "tests")
    
    # Print test header
    print("\n" + "="*70)
    print("Running tests for GHGI Dataset Discovery Agent")
    print("="*70)
    
    # Build pytest command
    pytest_args = [
        "pytest",
        tests_dir,
        "-v",                 # Verbose output
        "--color=yes"         # Colorized output
    ]
    
    # Add any additional arguments passed to this script
    pytest_args.extend(sys.argv[1:])
    
    # Print the command being run
    print(f"Running command: {' '.join(pytest_args)}\n")
    
    # Run pytest
    try:
        result = subprocess.run(pytest_args, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests()) 