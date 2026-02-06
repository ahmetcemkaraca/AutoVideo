#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test runner script for AutoVideo.

This script provides convenient commands for running tests with different configurations.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print output."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"\n✅ {description} passed!")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Run AutoVideo tests with various configurations"
    )
    parser.add_argument(
        "category",
        nargs="?",
        choices=["all", "unit", "integration", "performance", "coverage"],
        default="all",
        help="Test category to run"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-k", "--keep",
        action="store_true",
        help="Keep temporary files after tests"
    )
    parser.add_argument(
        "-x", "--stop-on-fail",
        action="store_true",
        help="Stop on first failure"
    )
    parser.add_argument(
        "-n", "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--cov",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML coverage report"
    )

    args = parser.parse_args()

    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Build pytest command
    pytest_cmd = ["python", "-m", "pytest"]

    # Add verbosity
    if args.verbose:
        pytest_cmd.append("-vv")

    # Add stop on failure
    if args.stop_on_fail:
        pytest_cmd.append("-x")

    # Add parallel execution
    if args.parallel:
        pytest_cmd.extend(["-n", "auto"])

    # Add coverage
    if args.cov or args.html:
        pytest_cmd.extend([
            "--cov=video_renderer",
            "--cov=VideoAutomation/automation",
            "--cov-report=term-missing"
        ])
        if args.html:
            pytest_cmd.append("--cov-report=html:htmlcov")

    # Add test category
    if args.category == "unit":
        pytest_cmd.extend(["-m", "unit", "tests/unit/"])
    elif args.category == "integration":
        pytest_cmd.extend(["-m", "integration", "tests/integration/"])
    elif args.category == "performance":
        pytest_cmd.extend(["-m", "performance", "tests/performance/"])
    elif args.category == "coverage":
        pytest_cmd.extend([
            "--cov=video_renderer",
            "--cov=VideoAutomation/automation",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml"
        ])
    else:  # all
        pytest_cmd.append("tests/")

    # Run tests
    success = run_command(pytest_cmd, f"Tests ({args.category})")

    # Print summary
    print(f"\n{'='*60}")
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")

    if args.cov or args.html:
        print("\n📊 Coverage report generated:")
        if args.html:
            print(f"   HTML: {project_root / 'htmlcov' / 'index.html'}")
        print(f"   Terminal: See above")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
