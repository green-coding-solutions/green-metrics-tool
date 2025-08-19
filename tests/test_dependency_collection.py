import os
from unittest.mock import patch

from lib.scenario_runner import ScenarioRunner
from tests import test_functions as Tests
from lib.db import DB

GMT_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))


class TestDependencyCollection:

    def test_execute_dependency_resolver_for_container_success(self):
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

        with patch('lib.scenario_runner.resolve_docker_dependencies_as_dict') as mock_resolver:
            mock_resolver.return_value = mock_response

            result = runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] == {"image": "nginx:latest", "hash": "sha256:2cd1d97f893f"}

            # Verify correct function was called with correct parameters
            mock_resolver.assert_called_once_with(
                container_identifier="test-container",
                only_container_info=True
            )

    def test_execute_dependency_resolver_for_container_exception(self):
        """Test dependency resolver exception handling"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        with patch('lib.scenario_runner.resolve_docker_dependencies_as_dict') as mock_resolver:
            mock_resolver.side_effect = RuntimeError("Container not found")

            result = runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] is None

    def test_execute_dependency_resolver_for_container_missing_container_info(self):
        """Test dependency resolver with response missing container info"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        # Mock response missing _container-info
        mock_response = {"some_other_key": "value"}

        with patch('lib.scenario_runner.resolve_docker_dependencies_as_dict') as mock_resolver:
            mock_resolver.return_value = mock_response

            result = runner._execute_dependency_resolver_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] is None

    def test_collect_dependency_info_all_containers_succeed(self):
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

            runner._collect_dependency_info()

            expected_dependencies = {
                "nginx-container": {"image": "nginx:latest", "hash": "sha256:nginx123"},
                "postgres-container": {"image": "postgres:13", "hash": "sha256:postgres456"}
            }

            assert runner._ScenarioRunner__usage_scenario_dependencies == expected_dependencies
            assert mock_exec.call_count == 2

    def test_collect_dependency_info_partial_failure(self):
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

            runner._collect_dependency_info()

            # Should be None due to partial failure
            assert runner._ScenarioRunner__usage_scenario_dependencies is None
            assert mock_exec.call_count == 2

    def test_collect_dependency_info_no_containers(self):
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

        runner._collect_dependency_info()

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
        """Test that dependencies are properly stored in database when collection succeeds"""
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

        # Mock successful dependency collection
        expected_dependencies = {
            "test-container": {"image": "gcb_stress_gmt_run_tmp:latest", "hash": "sha256:mock123"}
        }

        with patch.object(runner, '_collect_dependency_info') as mock_collect:
            def mock_successful_collection():
                runner._ScenarioRunner__usage_scenario_dependencies = expected_dependencies
            mock_collect.side_effect = mock_successful_collection

            run_id = runner.run()

            # Verify run was created and dependencies were saved
            assert run_id is not None

            result = DB().fetch_one(
                "SELECT usage_scenario_dependencies FROM runs WHERE id = %s",
                (run_id,)
            )

            assert result[0] == expected_dependencies

    def test_database_insertion_with_null_dependencies(self):
        """Test that null dependencies are stored when collection fails"""
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

        # Mock failed dependency collection
        with patch.object(runner, '_collect_dependency_info') as mock_collect:
            def mock_failed_collection():
                runner._ScenarioRunner__usage_scenario_dependencies = None
            mock_collect.side_effect = mock_failed_collection

            run_id = runner.run()

            # Verify run was created and dependencies are null
            assert run_id is not None

            result = DB().fetch_one(
                "SELECT usage_scenario_dependencies FROM runs WHERE id = %s",
                (run_id,)
            )

            assert result[0] is None
