import os
from unittest.mock import patch
import pytest

from lib.scenario_runner import ScenarioRunner
from tests import test_functions as Tests
from lib.db import DB

GMT_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))


class TestDependencyCollection:

    def test_execute_dependency_resolving_for_container_success(self):
        """Test successful energy-dependency-inspector execution for a single container"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_save=True
        )

        # Mock successful energy-dependency-inspector response
        mock_response = {
            "source": {
                "type": "container",
                "name": "test-container",
                "image": "nginx:latest",
                "hash": "sha256:2cd1d97f893f"
            }
        }

        with patch('lib.scenario_runner.resolve_docker_dependencies_as_dict') as mock_resolver:
            mock_resolver.return_value = mock_response

            result = runner._execute_dependency_resolving_for_container("test-container")

            assert result[0] == "test-container"
            assert result[1] == {
                "source": {
                    "type": "container",
                    "image": "nginx:latest",
                    "hash": "sha256:2cd1d97f893f"
                }
            }

            # Verify correct function was called with correct parameters
            mock_resolver.assert_called_once_with(
                container_identifier="test-container"
            )

    def test_execute_dependency_resolving_for_container_exception(self):
        """Test energy-dependency-inspector exception handling"""
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

            result = runner._execute_dependency_resolving_for_container("test-container")

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
            ("nginx-container", {
                "source": {"type": "container", "image": "nginx:latest", "hash": "sha256:nginx123"}
            }),
            ("postgres-container", {
                "source": {"type": "container", "image": "postgres:13", "hash": "sha256:postgres456"}
            })
        ]

        with patch.object(runner, '_execute_dependency_resolving_for_container') as mock_exec:
            mock_exec.side_effect = mock_responses

            runner._collect_dependency_info()

            expected_dependencies = {
                "nginx-container": {
                    "source": {"type": "container", "image": "nginx:latest", "hash": "sha256:nginx123"}
                },
                "postgres-container": {
                    "source": {"type": "container", "image": "postgres:13", "hash": "sha256:postgres456"}
                }
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
            ("nginx-container", {
                "source": {"type": "container", "image": "nginx:latest", "hash": "sha256:nginx123"}
            }),
            ("postgres-container", None)  # Failed
        ]

        with patch.object(runner, '_execute_dependency_resolving_for_container') as mock_exec:
            mock_exec.side_effect = mock_responses

            # Should raise RuntimeError due to partial failure
            with pytest.raises(RuntimeError, match="Dependency resolution failed"):
                runner._collect_dependency_info()

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

    def test_energy_dependency_inspector_integration_in_run_workflow(self):
        """Test that energy-dependency-inspector is called during the run workflow"""
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
            "test-container": {
                "source": {"type": "container", "image": "gcb_stress_gmt_run_tmp:latest", "hash": "sha256:mock123"}
            }
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

    def test_whole_run_fails_when_dependency_collection_fails(self):
        """Test that the entire GMT run fails when dependency collection fails"""
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

        # Mock failed dependency collection that raises exception
        with patch.object(runner, '_collect_dependency_info') as mock_collect:
            mock_collect.side_effect = RuntimeError("Dependency resolution failed for container 'postgres-container'. Aborting GMT run.")

            # The entire run should fail with RuntimeError
            with pytest.raises(RuntimeError, match="Dependency resolution failed"):
                runner.run()

    def test_integration_dependency_collection_with_real_containers(self):
        """Integration test using real containers and energy-dependency-inspector (no mocking)"""
        runner = ScenarioRunner(
            uri=GMT_DIR,
            uri_type='folder',
            filename='tests/data/web-application/usage_scenario.yml',
            skip_unsafe=True,
            skip_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_metrics=True,
            dev_no_phase_stats=True,
            dev_no_optimizations=True
        )

        try:
            run_id = runner.run()
            assert run_id is not None

            # Verify dependencies were collected successfully
            dependencies = runner._ScenarioRunner__usage_scenario_dependencies
            assert dependencies is not None
            assert isinstance(dependencies, dict)

            # Should have dependencies for both containers in docker-compose
            assert len(dependencies) >= 2

            # Verify we have the expected containers
            container_names = set(dependencies.keys())

            # Check that we have some expected containers (names may vary slightly)
            assert any('web' in name for name in container_names), f"No web container found in: {container_names}"
            assert any('db' in name for name in container_names), f"No db container found in: {container_names}"

            # Verify each dependency has required fields and correct structure
            for container_name, container_data in dependencies.items():
                # All containers should have source section
                assert 'source' in container_data, f"Missing 'source' for container {container_name}"

                source_info = container_data['source']
                assert 'image' in source_info, f"Missing 'image' for container {container_name}"
                assert 'hash' in source_info, f"Missing 'hash' for container {container_name}"
                assert source_info['image'] is not None, f"Image is None for container {container_name}"
                assert source_info['hash'] is not None, f"Hash is None for container {container_name}"
                assert source_info['hash'].startswith('sha256:'), f"Hash doesn't start with sha256: for container {container_name}"

                # Check for full dependency resolution on built containers
                if 'web' in container_name:
                    # Built containers should have project and system sections with packages
                    assert 'pip' in container_data, f"Missing 'pip' packages for container {container_name}"

                    project_packages = container_data.get('pip', {}).get('dependencies', [])
                    system_packages = container_data.get('dpkg', {}).get('packages', [])
                    total_packages = len(project_packages) + len(system_packages)

                    assert total_packages > 0, f"Built container {container_name} should have some packages"
                    print(f"✓ Built container {container_name} has {len(project_packages)} project packages and {len(system_packages)} system packages")
                else:
                    print(f"✓ Pre-built container {container_name} has container info")

            # Verify GMT-transformed images (GMT changes postgres:13 to postgres13_gmt_run_tmp:latest)
            images = [data['source']['image'] for data in dependencies.values()]
            assert any('postgres13_gmt_run_tmp' in image for image in images), f"postgres13_gmt_run_tmp not found in images: {images}"
            assert any('web_gmt_run_tmp' in image for image in images), f"web_gmt_run_tmp not found in images: {images}"

            # Verify dependencies were stored in database
            result = DB().fetch_one(
                "SELECT usage_scenario_dependencies FROM runs WHERE id = %s",
                (run_id,)
            )
            assert result is not None
            assert result[0] is not None
            stored_dependencies = result[0]
            assert stored_dependencies == dependencies, "Stored dependencies don't match collected dependencies"

        except Exception as exc:
            # Clean up on any failure
            try:
                runner.cleanup()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            raise exc
