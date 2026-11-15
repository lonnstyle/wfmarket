from unittest import TestCase

__author__ = "lonnstyle"

class BaseTest(TestCase):
    """Base class for all test cases.

    Args:
        TestCase (TestCase): The base class from unittest.
    """

    def setUp(self):
        """Set up the test case.

        This method is called before each test method is executed. It can be used to set up any necessary resources or configurations for the tests.
        """

    def tearDown(self):
        """Tear down the test case.

        This method is called after each test method is executed. It can be used to clean up any resources or configurations that were set up in the setUp method.
        """
        print('=> Result:')

    