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

#### 2.1 Script Location
- **Initial implementation**: Use local filesystem path `$HOME/git/gcs/dependency-resolver/dependency_resolver.py`
- **Future**: Replace with PyPI dependency (implementation should be designed to easily swap the execution method)

#### 2.2 Command Structure
```bash
python3 dependency_resolver.py docker <container_name> --only-container-info
```

#### 2.3 Multiple Container Handling
- Execute dependency resolver for **each known container**
- Individual container executions **can be run in parallel** for efficiency
- **Must complete synchronously** - all executions must finish before proceeding to next workflow step
- **Not asynchronous** - should not run in background of following workflow steps
- Aggregate results from all containers into a single JSON structure for storage

#### 2.4 Execution Context
- Inherit GMT's environment variables
- Inherit GMT's working directory
- Container names must be available in GMT's runtime context
- Execute dependency resolver in a loop for each container name

#### 2.5 Expected Output Format
Each execution returns JSON with container information:
```json
{
  "_container-info": {
    "name": "nginx-container",
    "image": "nginx:latest", 
    "hash": "sha256:2cd1d97f893f..."
  }
}
```

### 3. Error Handling

#### 3.1 Failure Behavior
- If dependency resolver fails for any container, GMT should **continue execution**
- **Only store results if ALL containers succeed** - partial results should not be stored
- Print overall summary warning message during execution
- Display notification in frontend (following existing error notification patterns)

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

#### 6.1 Scenario Runner Integration
- Modify `lib/scenario_runner.py` to call dependency resolver after BOOT phase
- Access container names from existing `self.__containers` dictionary structure:
  ```python
  self.__containers[container_id] = {
      'name': container_name
  }
  ```
- Execute dependency resolver for each container (can be done in parallel)
- Aggregate results from all containers
- **Only store results if all containers succeed**
- Add error handling with overall summary warning messages
- Ensure all executions complete before proceeding to next workflow step (synchronous completion, not asynchronous background execution)

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
- Python3 environment available for executing dependency resolver
- Access to `$HOME/git/gcs/dependency-resolver/dependency_resolver.py`
- Container names must be available in GMT's runtime context

#### 7.2 Container Names
- Use the individual container names that GMT started during the BOOT phase
- Execute dependency resolver in a loop, once per container name
- Handle cases where individual containers might not be accessible or may have stopped

## Future Considerations

### 8. Migration to PyPI
- Design the integration to easily replace filesystem execution with PyPI package import
- Consider using a configuration parameter to switch between execution methods
- Maintain same command-line interface for consistency

### 9. Performance
- Monitor execution time impact on overall GMT workflow
- Consider timeout mechanisms if dependency resolution takes too long

## Acceptance Criteria

1. Dependency resolver executes successfully after BOOT phase for each container in a loop
2. Aggregated JSON output is stored in `usage_scenario_dependencies` column **only if all containers succeed**
3. Frontend displays dependencies in table format within "Usage Scenario" tab
4. Error handling works correctly - GMT continues on failure with overall summary warnings
5. Integration follows existing GMT patterns for logging and error handling
6. All container dependency data includes all available fields from `_container-info`
7. Container names are accessed from existing `self.__containers` dictionary
8. No impact on existing GMT functionality