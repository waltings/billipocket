#!/usr/bin/env python3
"""
BilliPocket Test Runner Script

Comprehensive test runner for the BilliPocket invoice management application.
Provides different test execution modes and detailed reporting.
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and return the result."""
    if description:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print('='*60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        'pytest',
        'pytest-cov', 
        'pytest-mock',
        'psutil'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstall with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True


def run_unit_tests(coverage=False, verbose=False):
    """Run unit tests."""
    cmd = ['pytest', 'tests/unit/']
    
    if coverage:
        cmd.extend(['--cov=app', '--cov-report=term-missing'])
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run integration tests."""
    cmd = ['pytest', 'tests/integration/']
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, "Integration Tests")


def run_performance_tests(verbose=False):
    """Run performance tests."""
    cmd = ['pytest', '-m', 'performance']
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, "Performance Tests")


def run_estonian_tests(verbose=False):
    """Run Estonian-specific tests."""
    cmd = ['pytest', '-k', 'estonian']
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, "Estonian Compliance Tests")


def run_all_tests(coverage=False, verbose=False):
    """Run all tests."""
    cmd = ['pytest']
    
    if coverage:
        cmd.extend(['--cov=app', '--cov-report=html', '--cov-report=term-missing'])
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, "All Tests")


def run_coverage_report():
    """Generate detailed coverage report."""
    cmd = ['pytest', '--cov=app', '--cov-report=html', '--cov-report=term']
    
    success = run_command(cmd, "Coverage Report Generation")
    
    if success:
        html_report = Path('htmlcov/index.html')
        if html_report.exists():
            print(f"\nHTML coverage report generated: {html_report.absolute()}")
            print("Open in browser to view detailed coverage analysis.")
    
    return success


def run_specific_tests(pattern, verbose=False):
    """Run tests matching a specific pattern."""
    cmd = ['pytest', '-k', pattern]
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, f"Tests matching '{pattern}'")


def run_failed_tests():
    """Re-run only failed tests from last run."""
    cmd = ['pytest', '--lf']
    
    return run_command(cmd, "Re-running Failed Tests")


def lint_tests():
    """Run linting on test files."""
    test_files = []
    
    # Find all Python test files
    for test_dir in ['tests/unit', 'tests/integration', 'tests/fixtures']:
        test_path = Path(test_dir)
        if test_path.exists():
            test_files.extend(test_path.rglob('*.py'))
    
    if not test_files:
        print("No test files found.")
        return True
    
    # Run basic syntax check
    for test_file in test_files:
        try:
            with open(test_file, 'r') as f:
                compile(f.read(), test_file, 'exec')
        except SyntaxError as e:
            print(f"Syntax error in {test_file}: {e}")
            return False
    
    print(f"Syntax check passed for {len(test_files)} test files.")
    return True


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description='BilliPocket Test Runner')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--estonian', action='store_true', help='Run Estonian-specific tests only')
    parser.add_argument('--coverage', action='store_true', help='Include coverage reporting')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--pattern', '-k', help='Run tests matching pattern')
    parser.add_argument('--failed', action='store_true', help='Re-run only failed tests')
    parser.add_argument('--lint', action='store_true', help='Lint test files')
    parser.add_argument('--deps', action='store_true', help='Check dependencies only')
    
    args = parser.parse_args()
    
    # Check dependencies first
    if not check_dependencies():
        if args.deps:
            return 1
        print("Please install missing dependencies before running tests.")
        return 1
    
    if args.deps:
        print("All dependencies are installed.")
        return 0
    
    # Change to project root directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    success = True
    
    try:
        if args.lint:
            success = lint_tests()
        elif args.unit:
            success = run_unit_tests(args.coverage, args.verbose)
        elif args.integration:
            success = run_integration_tests(args.verbose)
        elif args.performance:
            success = run_performance_tests(args.verbose)
        elif args.estonian:
            success = run_estonian_tests(args.verbose)
        elif args.pattern:
            success = run_specific_tests(args.pattern, args.verbose)
        elif args.failed:
            success = run_failed_tests()
        elif args.coverage:
            success = run_coverage_report()
        else:
            # Run all tests by default
            success = run_all_tests(args.coverage, args.verbose)
        
        if success:
            print("\n" + "="*60)
            print("✅ Tests completed successfully!")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("❌ Tests failed!")
            print("="*60)
    
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        return 1
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())