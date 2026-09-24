"""Contract test suites for Keepsake providers.

Each test module in this package defines a reusable test suite that any provider
implementation must pass. For example, test_llm.py defines tests that verify
LLM.complete() returns a string and handles messages correctly.

To add a new provider implementation, simply parametrize the tests with your
implementation.
"""
