import asyncio
import json
import os
import pytest
from unittest.mock import patch, AsyncMock

from lib.scenario_runner import ScenarioRunner
from tests import test_functions as Tests
from lib.db import DB

GMT_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))


class TestDependencyCollection:

    @pytest.mark.asyncio
    async def test_execute_dependency_resolver_for_container_success(self):
        """Test successful dependency resolver execution for a single container"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        # Mock successful dependency resolver response
        mock_response = {
            "_container-info": {
                "name": "test-container",
                "image": "nginx:latest",
                "hash": "sha256:2cd1d97f893f"
            }
        }

        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_response).encode('utf-8'),
                b''
            )
            mock_subprocess.return_value = mock_process

            result = await runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] == {"image": "nginx:latest", "hash": "sha256:2cd1d97f893f"}

            # Verify correct command was called
            mock_subprocess.assert_called_once()
            args = mock_subprocess.call_args[0]
            assert args[0] == "python3"
            assert "dependency_resolver.py" in args[1]
            assert args[2] == "docker"
            assert args[3] == "test-container"
            assert args[4] == "--only-container-info"

    @pytest.mark.asyncio
    async def test_execute_dependency_resolver_for_container_timeout(self):
        """Test dependency resolver timeout handling"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError()
            mock_subprocess.return_value = mock_process

            result = await runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] is None

    @pytest.mark.asyncio
    async def test_execute_dependency_resolver_for_container_failure(self):
        """Test dependency resolver execution failure"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b'', b'Error message')
            mock_subprocess.return_value = mock_process

            result = await runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] is None

    @pytest.mark.asyncio
    async def test_execute_dependency_resolver_for_container_invalid_json(self):
        """Test dependency resolver with invalid JSON response"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b'invalid json', b'')
            mock_subprocess.return_value = mock_process

            result = await runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] is None

    @pytest.mark.asyncio
    async def test_collect_dependency_info_all_containers_succeed(self):
        """Test dependency collection when all containers succeed"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        # Mock container data
        runner._ScenarioRunner__containers = {
            'container1_id': {'name': 'nginx-container'},
            'container2_id': {'name': 'postgres-container'}
        }

        # Mock successful responses for both containers
        mock_responses = [
            ("nginx-container", {"image": "nginx:latest", "hash": "sha256:nginx123"}),
            ("postgres-container", {"image": "postgres:13", "hash": "sha256:postgres456"})
        ]

        with patch.object(runner, '_execute_dependency_resolver_for_container') as mock_exec:
            mock_exec.side_effect = mock_responses

            await runner._collect_dependency_info()

            expected_dependencies = {
                "nginx-container": {"image": "nginx:latest", "hash": "sha256:nginx123"},
                "postgres-container": {"image": "postgres:13", "hash": "sha256:postgres456"}
            }

            assert runner._ScenarioRunner__usage_scenario_dependencies == expected_dependencies
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_dependency_info_partial_failure(self):
        """Test dependency collection when some containers fail"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        # Mock container data
        runner._ScenarioRunner__containers = {
            'container1_id': {'name': 'nginx-container'},
            'container2_id': {'name': 'postgres-container'}
        }

        # Mock mixed responses (one success, one failure)
        mock_responses = [
            ("nginx-container", {"image": "nginx:latest", "hash": "sha256:nginx123"}),
            ("postgres-container", None)  # Failed
        ]

        with patch.object(runner, '_execute_dependency_resolver_for_container') as mock_exec:
            mock_exec.side_effect = mock_responses

            await runner._collect_dependency_info()

            # Should be None due to partial failure
            assert runner._ScenarioRunner__usage_scenario_dependencies is None
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_dependency_info_no_containers(self):
        """Test dependency collection when no containers are available"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        # No containers
        runner._ScenarioRunner__containers = {}

        await runner._collect_dependency_info()

        # Should remain None
        assert runner._ScenarioRunner__usage_scenario_dependencies is None

    def test_dependency_resolver_integration_in_run_workflow(self):
        """Test that dependency resolver is called during the run workflow"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_metrics=True,
            dev_no_save=True
        )

        # Mock the dependency collection method
        with patch.object(runner, '_collect_container_dependencies') as mock_collect:

            with Tests.RunUntilManager(runner) as context:
                # Run until after the dependency collection point
                context.run_until('collect_container_dependencies')

            # Verify dependency collection was called
            mock_collect.assert_called_once()

    def test_database_insertion_with_dependencies(self):
        """Test that dependencies are properly inserted into database"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_metrics=True,
            dev_no_phase_stats=True,
            dev_no_optimizations=True
        )

        # Set mock dependencies
        mock_dependencies = {
            "nginx-container": {"image": "nginx:latest", "hash": "sha256:nginx123"}
        }
        runner._ScenarioRunner__usage_scenario_dependencies = mock_dependencies

        run_id = runner.run()

        # Verify run was created and dependencies were saved
        assert run_id is not None

        result = DB().fetch_one(
            "SELECT usage_scenario_dependencies FROM runs WHERE id = %s",
            (run_id,)
        )

        assert result[0] == mock_dependencies

    def test_database_insertion_with_null_dependencies(self):
        """Test that null dependencies are properly handled in database"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_metrics=True,
            dev_no_phase_stats=True,
            dev_no_optimizations=True
        )

        # Set dependencies to None (failure case)
        runner._ScenarioRunner__usage_scenario_dependencies = None

        run_id = runner.run()

        # Verify run was created and dependencies are null
        assert run_id is not None

        result = DB().fetch_one(
            "SELECT usage_scenario_dependencies FROM runs WHERE id = %s",
            (run_id,)
        )

        assert result[0] is None
