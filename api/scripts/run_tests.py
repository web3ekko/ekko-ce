#!/usr/bin/env python3
"""Test runner script using testcontainers for isolated testing."""

import os
import sys
import subprocess
import argparse
import logging

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_tests(test_pattern=None, verbose=False, coverage=False, parallel=False):
    """Run tests with pytest using testcontainers."""
    
    # Set environment variables for testing
    os.environ["TEST_MODE"] = "true"
    os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), '..')
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test directory
    test_dir = os.path.join(os.path.dirname(__file__), '..', 'tests')
    cmd.append(test_dir)
    
    # Add test pattern if specified
    if test_pattern:
        cmd.extend(["-k", test_pattern])
    
    # Add verbose flag
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Add coverage if requested
    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Add parallel execution if requested
    if parallel:
        cmd.extend(["-n", "auto"])
    
    # Add asyncio mode
    cmd.append("--asyncio-mode=auto")
    
    # Add output formatting
    cmd.extend([
        "--tb=short",
        "--strict-markers"
    ])
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        # Run the tests
        result = subprocess.run(cmd, cwd=os.path.dirname(__file__), check=False)
        return result.returncode
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return 1


def run_specific_test_file(test_file, verbose=False):
    """Run a specific test file."""
    
    test_path = os.path.join(os.path.dirname(__file__), '..', 'tests', test_file)
    
    if not os.path.exists(test_path):
        logger.error(f"Test file not found: {test_path}")
        return 1
    
    cmd = ["python", "-m", "pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("--asyncio-mode=auto")
    
    logger.info(f"Running test file: {test_file}")
    
    try:
        result = subprocess.run(cmd, cwd=os.path.dirname(__file__), check=False)
        return result.returncode
    except Exception as e:
        logger.error(f"Error running test file: {e}")
        return 1


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "pytest",
        "pytest-asyncio", 
        "testcontainers",
        "duckdb"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing required packages: {', '.join(missing_packages)}")
        logger.error("Install them with: pip install " + " ".join(missing_packages))
        return False
    
    return True


def list_available_tests():
    """List all available test files."""
    test_dir = os.path.join(os.path.dirname(__file__), '..', 'tests')
    
    if not os.path.exists(test_dir):
        logger.error(f"Test directory not found: {test_dir}")
        return
    
    test_files = []
    for file in os.listdir(test_dir):
        if file.startswith('test_') and file.endswith('.py'):
            test_files.append(file)
    
    if test_files:
        logger.info("Available test files:")
        for test_file in sorted(test_files):
            logger.info(f"  - {test_file}")
    else:
        logger.info("No test files found")


def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(description="Run tests with testcontainers")
    
    parser.add_argument(
        "--pattern", "-k",
        help="Run tests matching this pattern"
    )
    
    parser.add_argument(
        "--file", "-f",
        help="Run a specific test file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available test files"
    )
    
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check if required dependencies are installed"
    )
    
    args = parser.parse_args()
    
    # Check dependencies if requested
    if args.check_deps:
        if check_dependencies():
            logger.info("All required dependencies are installed")
            return 0
        else:
            return 1
    
    # List tests if requested
    if args.list:
        list_available_tests()
        return 0
    
    # Check dependencies before running tests
    if not check_dependencies():
        return 1
    
    # Run specific test file
    if args.file:
        return run_specific_test_file(args.file, args.verbose)
    
    # Run tests with pattern or all tests
    return run_tests(
        test_pattern=args.pattern,
        verbose=args.verbose,
        coverage=args.coverage,
        parallel=args.parallel
    )


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
