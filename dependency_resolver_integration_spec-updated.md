# GMT Dependency Resolver Integration Specification

## Overview
This specification defines the integration of the dependency-resolver component into GMT (Green Metrics Tool) to capture a snapshot of dependencies after the BOOT phase. The integration will capture, store, and display dependency information for Docker Compose-based usage scenarios.

## Requirements

### 1. Integration Point
- Execute dependency resolver **after** the BOOT phase in GMT
- Integration should be **synchronous/blocking** - GMT waits for completion
- Execution should occur in the main workflow where individual containers are already running
- Execute in a loop for each known container name

### 2. Dependency Resolver Execution

#### 2.1 Implementation Method
- **Current implementation**: Use Python package `dependency-resolver` installed via pip
- Function call: `resolve_docker_dependencies_as_dict(container_identifier=container_name, only_container_info=True)`
- **Previous approach**: Command line execution (replaced for better performance and reliability)

#### 2.2 Function Interface
```python
from dependency_resolver import resolve_docker_dependencies_as_dict

result = resolve_docker_dependencies_as_dict(
    container_identifier=container_name,
    only_container_info=True
)
```

#### 2.3 Multiple Container Handling
- Execute dependency resolver for **each known container**
- Individual container executions **run in parallel** using `ThreadPoolExecutor` for efficiency
- **Must complete synchronously** - all executions must finish before proceeding to next workflow step
- **Not asynchronous** - does not run in background of following workflow steps
- Limited to max 4 parallel workers to prevent resource exhaustion
- Aggregate results from all containers into a single JSON structure for storage

#### 2.4 Execution Context
- Direct Python function calls eliminate subprocess overhead
- No working directory parameter needed for container info only
- Container names must be available in GMT's runtime context
- Execute dependency resolver in parallel for all container names

#### 2.5 Expected Output Format
Each function call returns a Python dictionary with container information:
```python
{
  "_container-info": {
    "name": "nginx-container",
    "image": "nginx:latest", 
    "hash": "sha256:2cd1d97f893f..."
  }
}
```

The implementation extracts the `_container-info` section and removes the `name` field (since container name is used as the key in the aggregated structure). If `_container-info` is missing from the response, the container result is treated as failed.

### 3. Error Handling

#### 3.1 Failure Behavior
- If dependency resolver fails for any container, the **whole GMT run fails**

#### 3.2 Logging
- Follow existing GMT logging patterns for consistency
- Log dependency resolver execution start/completion
- Log **overall summary** of errors or warnings (not individual container failures)
- Use same log levels as other GMT components

### 4. Data Storage

#### 4.1 Database Schema Changes
- Add new JSONB column to `runs` table: `usage_scenario_dependencies`
- Store **raw output** from dependency resolver in this column
- No additional indexes required

#### 4.2 Data Structure
- Store the **aggregated JSON output** from all container dependency resolver executions
- **Only store if all containers succeed** - do not store partial results
- Combine individual container results into a single JSON structure using container name as key
- **Include all fields** from the `_container-info` section of each container's raw output
- Example aggregated structure (showing minimum fields - additional fields will be included if present):
```json
{
  "nginx-container": {
    "image": "nginx:latest",
    "hash": "sha256:2cd1d97f893f..."
  },
  "postgres-container": {
    "image": "postgres:13",
    "hash": "sha256:5f2a1b8d..."
  }
}
```

### 5. Frontend Integration

#### 5.1 Display Location
- Add to existing "Usage Scenario" tab
- Create new section: "Usage Scenario Dependencies"
- Position alongside existing sections:
  - Usage Scenario Variables
  - Usage Scenario File
  - **Usage Scenario Dependencies** (new)

#### 5.2 Display Format
- Present dependency information in **table format**
- Table should parse and display the JSON data in a user-friendly manner
- Include standard table features (sorting, if applicable)

#### 5.3 Error Display
- If dependency resolution failed, show appropriate error message in the section
- Follow existing frontend error notification patterns

## Implementation Details

### 6. Code Integration Points

#### 6.1 Scenario Runner Integration ✅ COMPLETED
- ✅ Modified `lib/scenario_runner.py` to call dependency resolver after BOOT phase
- ✅ Access container names from existing `self.__containers` dictionary structure:
  ```python
  container_names = [container_info['name'] for container_info in self.__containers.values()]
  ```
- ✅ Execute dependency resolver for each container using ThreadPoolExecutor for parallel execution
- ✅ Aggregate results from all containers into single JSON structure
- ✅ **Only store results if all containers succeed**
- ✅ Added error handling with overall summary warning messages
- ✅ Synchronous completion using `ThreadPoolExecutor.map()` - all executions complete before proceeding

#### 6.2 Database Integration
- Update database schema to add `usage_scenario_dependencies` JSONB column
- Modify data access layer to handle the new column
- Update run insertion/update queries

#### 6.3 Frontend Integration
- Update "Usage Scenario" tab component
- Add new "Usage Scenario Dependencies" section
- Implement table rendering for dependency data
- Add error state handling

### 7. Environment Requirements

#### 7.1 Prerequisites
- Individual Docker containers must be running (handled by existing GMT BOOT phase)
- Python3 environment with `dependency-resolver` package installed via pip
- Container names must be available in GMT's runtime context

#### 7.2 Container Names
- Use the individual container names that GMT started during the BOOT phase
- Execute dependency resolver in a loop, once per container name
- Handle cases where individual containers might not be accessible or may have stopped

## Implementation Status

### 8. Migration to PyPI ✅ COMPLETED
- ✅ Replaced filesystem execution with PyPI package `dependency-resolver`
- ✅ Direct function calls provide better performance and reliability
- ✅ Eliminated subprocess overhead and timeout issues
- ✅ Maintained same output format for consistency

### 9. Performance Improvements ✅ COMPLETED
- ✅ ThreadPoolExecutor provides efficient parallel execution
- ✅ Limited to max 4 workers to prevent resource exhaustion
- ✅ Direct Python calls eliminate command-line overhead
- ✅ Synchronous execution model maintained

## Acceptance Criteria

1. ✅ Dependency resolver executes successfully after BOOT phase using Python package
2. ✅ Aggregated JSON output is stored in `usage_scenario_dependencies` column **only if all containers succeed**
3. ✅ Frontend displays dependencies in table format within "Usage Scenario" tab
4. ✅ Error handling works correctly - GMT continues on failure with overall summary warnings
5. ✅ Integration follows existing GMT patterns for logging and error handling
6. ✅ All container dependency data includes all available fields from `_container-info`
7. ✅ Container names are accessed from existing `self.__containers` dictionary
8. ✅ No impact on existing GMT functionality
9. ✅ Parallel execution using ThreadPoolExecutor for improved performance
10. ✅ Direct Python function calls eliminate subprocess overhead
