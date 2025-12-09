"""
Test runner script for running unit tests.
"""
import unittest
import sys
import os

def run_tests():
    # Add the project root to the Python path
    sys.path.insert(0, os.path.abspath('.'))
    
    # Discover and run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return success/failure status
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
