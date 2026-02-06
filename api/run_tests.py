#!/usr/bin/env python3
"""
Test runner script for admin-api
Provides different test execution modes and coverage reporting
"""
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}")
    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ {description} - FAILED")
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.stdout:
            print("STDOUT:", result.stdout)
        return False

    return True


def run_setup_validation():
    """Run setup validation tests"""
    cmd = [
        "python3",
        "-m",
        "pytest",
        "tests/test_setup_validation.py",
        "-v",
        "--tb=short",
    ]
    return run_command(cmd, "Setup Validation Tests")


def run_unit_tests():
    """Run unit tests with coverage"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "app/tests/test_models",
        "app/tests/test_serializers",
        "app/tests/test_views",
        "app/tests/test_services",
        "tests/unit/",
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "-m",
        "unit",
    ]
    return run_command(cmd, "Unit Tests")


def run_integration_tests():
    """Run integration tests"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "app/tests/test_integration",
        "tests/integration/",
        "-v",
        "--tb=short",
        "-m",
        "integration",
    ]
    return run_command(cmd, "Integration Tests")


def run_performance_tests():
    """Run performance tests"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m",
        "performance",
        "--benchmark-only",
    ]
    return run_command(cmd, "Performance Tests")


def run_all_tests():
    """Run all tests with full coverage"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "app/tests/",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-report=xml",
        "--cov-fail-under=95",
    ]
    return run_command(cmd, "All Tests with Coverage")


def run_specific_test(test_path):
    """Run a specific test file or test"""
    cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
    return run_command(cmd, f"Specific Test: {test_path}")


def check_coverage():
    """Check current test coverage"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "--quiet",
    ]
    return run_command(cmd, "Coverage Check")


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Admin-API Test Runner")
    parser.add_argument(
        "mode",
        choices=[
            "setup",
            "unit",
            "integration",
            "performance",
            "all",
            "coverage",
            "specific",
        ],
        help="Test mode to run",
    )
    parser.add_argument(
        "--test", help="Specific test file or test to run (for 'specific' mode)"
    )
    parser.add_argument(
        "--fast", action="store_true", help="Run tests in fast mode (skip slow tests)"
    )
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")

    args = parser.parse_args()

    # Change to admin-api directory
    admin_api_dir = Path(__file__).parent
    import os

    os.chdir(admin_api_dir)

    print("🧪 Admin-API Test Runner")
    print(f"📁 Working directory: {admin_api_dir}")
    print(f"🎯 Mode: {args.mode}")

    # Check if pytest is available
    try:
        subprocess.run(
            ["python", "-m", "pytest", "--version"], capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        print("❌ pytest not found. Please install test dependencies:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

    success = True

    if args.mode == "setup":
        success = run_setup_validation()
    elif args.mode == "unit":
        success = run_unit_tests()
    elif args.mode == "integration":
        success = run_integration_tests()
    elif args.mode == "performance":
        success = run_performance_tests()
    elif args.mode == "all":
        success = run_all_tests()
    elif args.mode == "coverage":
        success = check_coverage()
    elif args.mode == "specific":
        if not args.test:
            print("❌ --test argument required for 'specific' mode")
            sys.exit(1)
        success = run_specific_test(args.test)

    if success:
        print("\n🎉 Tests completed successfully!")

        # Show coverage report location if available
        coverage_html = admin_api_dir / "htmlcov" / "index.html"
        if coverage_html.exists():
            print(f"📊 Coverage report: file://{coverage_html}")
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
