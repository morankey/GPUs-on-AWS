# P-Series AWS Analyzer Tests

Comprehensive test suite covering unit and integration tests for the P-Series GPU analyzer.

## Running Tests

```bash
# Run all tests
python run_tests.py

# Run specific test file
python -m unittest tests.test_models

# Run specific test class
python -m unittest tests.test_advisor.TestGPUAdvisor

# Run specific test
python -m unittest tests.test_advisor.TestGPUAdvisor.test_default_regions
```

## Test Coverage

### Unit Tests

**test_models.py** - Data model tests
- SpotResult, CapacityBlockResult, OnDemandResult
- AZ display formatting
- Available/unavailable states

**test_aws_client.py** - AWS client tests
- GPU info retrieval and caching
- AZ mapping and caching
- Spot prices and placement scores
- On-demand availability matrix
- Error handling for API failures

**test_advisor.py** - Business logic tests
- Region configuration
- Instance type discovery
- Spot option selection (highest score, lowest price)
- Capacity block selection (earliest, shortest, cheapest)
- On-demand option selection
- Progress callbacks
- Multi-region analysis

### Integration Tests

**test_integration.py** - End-to-end workflows
- Complete spot analysis workflow
- Complete capacity block workflow
- Complete on-demand workflow
- AWS client integration points

## Test Results

All 32 tests passing:
- 10 model tests
- 11 AWS client tests
- 10 advisor tests
- 1 integration test

## Key Test Patterns

**Mocking AWS APIs**: Tests use `unittest.mock` to simulate AWS responses without making real API calls.

**Selection Logic**: Tests verify the core selection algorithms:
- Spot: highest score, lowest price tiebreaker
- Capacity blocks: earliest start, shortest duration, lowest price
- On-demand: highest availability score, lowest price tiebreaker

**Error Handling**: Tests ensure graceful degradation when AWS APIs fail.

**Caching**: Tests verify that expensive API calls are cached appropriately.
