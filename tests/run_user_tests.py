#!/usr/bin/env python3

"""
Test runner for user management CLI tests
"""

import unittest
import sys
import os

# Add the test directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Import test modules
import config_test_user
import show_test_user

def run_all_user_tests():
    """Run all user management tests"""
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add config tests
    suite.addTests(loader.loadTestsFromModule(config_test_user))
    
    # Add show tests
    suite.addTests(loader.loadTestsFromModule(show_test_user))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()

def run_config_tests():
    """Run only config user tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(config_test_user)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_show_tests():
    """Run only show user tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(show_test_user)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run user management tests')
    parser.add_argument('--config-only', action='store_true', 
                       help='Run only config user tests')
    parser.add_argument('--show-only', action='store_true',
                       help='Run only show user tests')
    
    args = parser.parse_args()
    
    if args.config_only:
        success = run_config_tests()
    elif args.show_only:
        success = run_show_tests()
    else:
        success = run_all_user_tests()
    
    sys.exit(0 if success else 1)
