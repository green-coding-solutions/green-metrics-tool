import os
import platform
import subprocess
import pytest
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Test image constants
ALPINE_AMD64_IMAGE = 'alpine@sha256:eafc1edb577d2e9b458664a15f23ea1c370214193226069eb22921169fc7e43f'
ALPINE_ARM64_IMAGE = 'alpine@sha256:4562b419adf48c5f3c763995d6014c123b3ce1d2e0ef2613b189779caa787192'

from lib.container_compatibility import CompatibilityStatus
from lib.container_compatibility import _is_compatible_architecture_variant
from lib.container_compatibility import check_image_architecture_compatibility
from lib.container_compatibility import _clear_platform_cache
from lib.container_compatibility import get_platform_compatibility_status


@pytest.fixture(autouse=True)
def clear_platform_cache():
    """Automatically clear platform cache before each test to ensure isolation."""
    _clear_platform_cache()

class TestCompatibleArchitectureVariants:
    """Test suite for _is_compatible_architecture_variant function."""

    def test_exact_match(self):
        """Test exact platform matches are considered native."""
        assert _is_compatible_architecture_variant("linux/amd64", "linux/amd64") is True
        assert _is_compatible_architecture_variant("linux/arm64", "linux/arm64") is True
        assert _is_compatible_architecture_variant("linux/arm", "linux/arm") is True

    @pytest.mark.parametrize("host_platform,variant_platforms", [
        ("linux/amd64", [
            "linux/amd64/v2", "linux/amd64/v3", "linux/amd64/v4",
            "linux/amd64/custom", "linux/amd64/special"
        ]),
        ("linux/arm64", [
            "linux/arm64/v8", "linux/arm64/custom"
        ]),
        ("linux/arm", [
            "linux/arm/v6", "linux/arm/v7", "linux/arm/neon"
        ]),
        ("linux/386", [
            "linux/386/custom"
        ]),
    ])
    def test_architecture_variants_are_native(self, host_platform, variant_platforms):
        """Test that architecture variants are correctly identified as native."""
        for variant in variant_platforms:
            assert _is_compatible_architecture_variant(variant, host_platform) is True, \
                f"{variant} should be native variant of {host_platform}"

    @pytest.mark.parametrize("host_platform,emulated_platforms", [
        ("linux/amd64", [
            "linux/arm64", "linux/386", "linux/arm", "linux/s390x", "linux/ppc64le"
        ]),
        ("linux/arm64", [
            "linux/amd64", "linux/386", "linux/arm", "linux/s390x"
        ]),
        ("linux/arm", [
            "linux/amd64", "linux/arm64", "linux/386", "linux/s390x"
        ]),
    ])
    def test_different_architectures_require_emulation(self, host_platform, emulated_platforms):
        """Test that different architectures are correctly identified as requiring emulation."""
        for emulated in emulated_platforms:
            assert _is_compatible_architecture_variant(emulated, host_platform) is False, \
                f"{emulated} should require emulation on {host_platform}"

    def test_different_os_requires_emulation(self):
        """Test that different operating systems require emulation."""
        host_platform = "linux/amd64"

        different_os_platforms = [
            "windows/amd64", "darwin/amd64", "freebsd/amd64"
        ]

        for candidate_platform in different_os_platforms:
            assert _is_compatible_architecture_variant(candidate_platform, host_platform) is False

    @pytest.mark.parametrize("candidate_platform", [
        "invalid", "linux", "amd64", "", "/", "linux/", "/amd64"
    ])
    def test_invalid_formats_return_false(self, candidate_platform):
        """Test that invalid platform formats return False."""
        host_platform = "linux/amd64"
        assert _is_compatible_architecture_variant(candidate_platform, host_platform) is False

    def test_variant_hierarchy_edge_cases(self):
        """Test edge cases with variant hierarchies."""
        # Base platform is NOT a variant of its own variant
        assert _is_compatible_architecture_variant("linux/amd64", "linux/amd64/v2") is False

        # Variants of variants should not be considered native to base
        # (though this is unlikely in practice)
        assert _is_compatible_architecture_variant("linux/amd64/v2/custom", "linux/amd64") is True

        # Cross-architecture variants
        assert _is_compatible_architecture_variant("linux/arm64/v8", "linux/amd64") is False
        assert _is_compatible_architecture_variant("linux/amd64/v2", "linux/arm64") is False

    def test_case_sensitivity(self):
        """Test that platform comparison handles case correctly."""
        host_platform = "linux/amd64"

        # These should be False as Docker platforms are case-sensitive
        assert _is_compatible_architecture_variant("Linux/amd64", host_platform) is False
        assert _is_compatible_architecture_variant("linux/AMD64", host_platform) is False
        assert _is_compatible_architecture_variant("LINUX/AMD64", host_platform) is False

    def test_real_world_docker_platforms(self):
        """Test with actual Docker platform strings seen in the wild."""
        # Common amd64 variants
        host_amd64 = "linux/amd64"
        amd64_variants = ["linux/amd64/v2", "linux/amd64/v3", "linux/amd64/v4"]

        for variant in amd64_variants:
            assert _is_compatible_architecture_variant(variant, host_amd64) is True

        # ARM variants
        host_arm64 = "linux/arm64"
        assert _is_compatible_architecture_variant("linux/arm64/v8", host_arm64) is True

        host_arm = "linux/arm"
        arm_variants = ["linux/arm/v6", "linux/arm/v7"]

        for variant in arm_variants:
            assert _is_compatible_architecture_variant(variant, host_arm) is True

        # Cross-architecture should be False
        assert _is_compatible_architecture_variant("linux/arm64", host_amd64) is False
        assert _is_compatible_architecture_variant("linux/amd64", host_arm64) is False


class TestArchitectureCompatibility:
    """Test suite for check_image_architecture_compatibility function."""

    class TestUnitTests:
        """Fast unit tests with mocked dependencies."""

        @patch('lib.container_compatibility.subprocess.run')
        @patch('lib.container_compatibility.get_native_architecture')
        @patch('lib.container_compatibility.get_platform_compatibility_status')
        def test_native_compatibility_mocked(self, mock_platform_status, mock_native_arch, mock_subprocess):
            """Test native compatibility logic with mocked dependencies."""
            # Setup mocks
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout.strip.return_value = 'amd64'
            mock_native_arch.return_value = 'amd64'
            mock_platform_status.return_value = CompatibilityStatus.NATIVE

            # Test
            result = check_image_architecture_compatibility('test-image')

            # Verify Docker inspect was called
            mock_subprocess.assert_called_once_with(
                ['docker', 'image', 'inspect', 'test-image', '--format', '{{.Architecture}}'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', check=False
            )

            # Verify platform status check
            mock_platform_status.assert_called_once_with('linux/amd64')

            # Verify result
            assert result['image_arch'] == 'amd64'
            assert result['host_arch'] == 'amd64'
            assert result['image_platform'] == 'linux/amd64'
            assert result['status'] == CompatibilityStatus.NATIVE
            assert result['can_run'] is True
            assert result['needs_emulation'] is False
            assert result['is_native_compatible'] is True
            assert result['error'] is None

        @patch('lib.container_compatibility.subprocess.run')
        @patch('lib.container_compatibility.get_native_architecture')
        @patch('lib.container_compatibility.get_platform_compatibility_status')
        def test_emulated_compatibility_mocked(self, mock_platform_status, mock_native_arch, mock_subprocess):
            """Test emulated compatibility logic with mocked dependencies."""
            # Setup mocks
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout.strip.return_value = 'arm64'
            mock_native_arch.return_value = 'amd64'
            mock_platform_status.return_value = CompatibilityStatus.EMULATED

            # Test
            result = check_image_architecture_compatibility('test-arm64-image')

            # Verify result
            assert result['image_arch'] == 'arm64'
            assert result['host_arch'] == 'amd64'
            assert result['image_platform'] == 'linux/arm64'
            assert result['status'] == CompatibilityStatus.EMULATED
            assert result['can_run'] is True
            assert result['needs_emulation'] is True
            assert result['is_native_compatible'] is False
            assert result['error'] is None

        @patch('lib.container_compatibility.subprocess.run')
        @patch('lib.container_compatibility.get_native_architecture')
        @patch('lib.container_compatibility.get_platform_compatibility_status')
        def test_incompatible_compatibility_mocked(self, mock_platform_status, mock_native_arch, mock_subprocess):
            """Test incompatible compatibility logic with mocked dependencies."""
            # Setup mocks
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout.strip.return_value = 's390x'
            mock_native_arch.return_value = 'amd64'
            mock_platform_status.return_value = CompatibilityStatus.INCOMPATIBLE

            # Test
            result = check_image_architecture_compatibility('test-s390x-image')

            # Verify result
            assert result['image_arch'] == 's390x'
            assert result['host_arch'] == 'amd64'
            assert result['image_platform'] == 'linux/s390x'
            assert result['status'] == CompatibilityStatus.INCOMPATIBLE
            assert result['can_run'] is False
            assert result['needs_emulation'] is False
            assert result['is_native_compatible'] is False
            assert result['error'] is None

        @patch('lib.container_compatibility.subprocess.run')
        @patch('lib.container_compatibility.get_native_architecture')
        def test_docker_inspect_failure_mocked(self, mock_native_arch, mock_subprocess):
            """Test handling of Docker inspect failure with mocked dependencies."""
            # Setup mocks
            mock_subprocess.return_value.returncode = 1
            mock_subprocess.return_value.stderr.strip.return_value = 'No such image'
            mock_native_arch.return_value = 'amd64'

            # Test
            result = check_image_architecture_compatibility('nonexistent-image')

            # Verify error handling
            assert result['image_arch'] == 'unknown'
            assert result['host_arch'] == 'amd64'
            assert result['image_platform'] == 'unknown'
            assert result['status'] == CompatibilityStatus.INCOMPATIBLE
            assert result['can_run'] is False
            assert result['needs_emulation'] is False
            assert result['is_native_compatible'] is False
            assert result['error'] is not None

    class TestIntegrationTests:
        """Integration tests with real Docker for cross-architecture scenarios."""

        @pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
        def test_architecture_compatibility_check_native_image_amd64(self):
            """Test architecture compatibility checking with native amd64 image on amd64 host"""

            # Ensure the alpine amd64 image is available
            subprocess.run(['docker', 'pull', ALPINE_AMD64_IMAGE],
                          check=True, capture_output=True)

            # Test with alpine amd64 image which is native on amd64
            compat_info = check_image_architecture_compatibility(ALPINE_AMD64_IMAGE)

            assert isinstance(compat_info, dict)
            assert 'image_arch' in compat_info
            assert 'host_arch' in compat_info
            assert 'status' in compat_info
            assert 'can_run' in compat_info
            assert 'needs_emulation' in compat_info

             # On amd64 host, amd64 alpine should be native
            assert compat_info['image_arch'] == 'amd64'
            assert compat_info['host_arch'] == 'amd64'
            assert compat_info['status'] == CompatibilityStatus.NATIVE
            assert compat_info['is_native_compatible'] is True
            assert compat_info['needs_emulation'] is False
            assert compat_info['can_run'] is True

        @pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
        def test_architecture_compatibility_check_native_image_arm64(self):
            """Test architecture compatibility checking with native arm64 image on arm64 host"""

            # Ensure the alpine arm64 image is available
            subprocess.run(['docker', 'pull', ALPINE_ARM64_IMAGE],
                          check=True, capture_output=True)

            # Test with alpine arm64 image which is native on arm64
            compat_info = check_image_architecture_compatibility(ALPINE_ARM64_IMAGE)

            assert isinstance(compat_info, dict)
            assert 'image_arch' in compat_info
            assert 'host_arch' in compat_info
            assert 'status' in compat_info
            assert 'can_run' in compat_info
            assert 'needs_emulation' in compat_info

            # On arm64 host, arm64 alpine should be native
            assert compat_info['image_arch'] == 'arm64'
            assert compat_info['host_arch'] == 'arm64'
            assert compat_info['status'] == CompatibilityStatus.NATIVE
            assert compat_info['is_native_compatible'] is True
            assert compat_info['needs_emulation'] is False
            assert compat_info['can_run'] is True

        @pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
        def test_architecture_compatibility_check_arm64_image_on_x86_64_host(self):
            """Test architecture compatibility checking with ARM64 image on x86_64 host"""

            # Ensure the alpine arm64 image is available
            subprocess.run(['docker', 'pull', ALPINE_ARM64_IMAGE],
                          check=True, capture_output=True)

            # Use ARM64 alpine image on x86_64 host
            compat_info = check_image_architecture_compatibility(ALPINE_ARM64_IMAGE)

            assert compat_info['image_arch'] == 'arm64'
            assert compat_info['host_arch'] == 'amd64'
            assert compat_info['is_native_compatible'] is False
            assert compat_info['image_platform'] == 'linux/arm64'

            # Check compatibility status using enum
            compatibility_status = compat_info['status']

            if compatibility_status == CompatibilityStatus.EMULATED:
                # If emulation works, container can run but needs emulation
                assert compat_info['can_run'] is True
                assert compat_info['needs_emulation'] is True
            elif compatibility_status == CompatibilityStatus.INCOMPATIBLE:
                # If no working emulation, container cannot run
                assert compat_info['can_run'] is False
                assert compat_info['needs_emulation'] is False

        @pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
        def test_architecture_compatibility_check_amd64_image_on_arm64_host(self):
            """Test architecture compatibility checking with AMD64 image on ARM64 host"""

            # Ensure the alpine amd64 image is available
            subprocess.run(['docker', 'pull', ALPINE_AMD64_IMAGE],
                          check=True, capture_output=True)

            # Use AMD64 alpine image on ARM64 host
            compat_info = check_image_architecture_compatibility(ALPINE_AMD64_IMAGE)

            assert compat_info['image_arch'] == 'amd64'
            assert compat_info['host_arch'] == 'arm64'
            assert compat_info['is_native_compatible'] is False
            assert compat_info['image_platform'] == 'linux/amd64'

            # Check compatibility status using enum
            compatibility_status = compat_info['status']

            if compatibility_status == CompatibilityStatus.EMULATED:
                # If emulation works, container can run but needs emulation
                assert compat_info['can_run'] is True
                assert compat_info['needs_emulation'] is True
            elif compatibility_status == CompatibilityStatus.INCOMPATIBLE:
                # If no working emulation, container cannot run
                assert compat_info['can_run'] is False
                assert compat_info['needs_emulation'] is False


class TestPlatformCompatibilityStatus:
    """Test suite for get_platform_compatibility_status function."""

    class TestUnitTests:
        """Fast unit tests with mocking for logic validation."""

        @patch('lib.container_compatibility._get_supported_platforms')
        @patch('lib.container_compatibility.get_native_platform')
        def test_caching_behavior_mocked(self, mock_native_platform, mock_supported_platforms):
            """Test caching behavior with mocked dependencies."""
            # Setup mocks
            mock_native_platform.return_value = 'linux/amd64'
            mock_supported_platforms.return_value = ['linux/amd64', 'linux/arm64', 'linux/amd64/v2']

            # Clear cache to ensure clean test
            _clear_platform_cache()

            # First call should populate cache
            result1 = get_platform_compatibility_status()
            assert mock_supported_platforms.call_count == 1
            assert mock_native_platform.call_count == 1

            # Second call should use cache (no additional calls)
            result2 = get_platform_compatibility_status()
            assert mock_supported_platforms.call_count == 1  # Still 1, not 2
            assert mock_native_platform.call_count == 1  # Still 1, not 2

            # Results should be identical (same cached object)
            assert result1 is result2

            # Platform-specific calls should also use cache
            get_platform_compatibility_status('linux/amd64')
            get_platform_compatibility_status('linux/arm64')
            assert mock_supported_platforms.call_count == 1  # Still using cache

        @patch('lib.container_compatibility._get_supported_platforms')
        @patch('lib.container_compatibility.get_native_platform')
        def test_platform_status_logic_mocked(self, mock_native_platform, mock_supported_platforms):
            """Test platform status determination logic with mocked dependencies."""
            # Setup mocks
            mock_native_platform.return_value = 'linux/amd64'
            mock_supported_platforms.return_value = [
                'linux/amd64',      # Native
                'linux/amd64/v2',   # Native variant
                'linux/arm64',      # Emulated
                'linux/386'         # Emulated
            ]

            _clear_platform_cache()

            # Test native platform
            assert get_platform_compatibility_status('linux/amd64') == CompatibilityStatus.NATIVE

            # Test native variant
            assert get_platform_compatibility_status('linux/amd64/v2') == CompatibilityStatus.NATIVE

            # Test emulated platforms
            assert get_platform_compatibility_status('linux/arm64') == CompatibilityStatus.EMULATED
            assert get_platform_compatibility_status('linux/386') == CompatibilityStatus.EMULATED

            # Test unsupported platform
            assert get_platform_compatibility_status('linux/unsupported') == CompatibilityStatus.INCOMPATIBLE

        @patch('lib.container_compatibility._get_supported_platforms')
        @patch('lib.container_compatibility.get_native_platform')
        def test_return_structure_mocked(self, mock_native_platform, mock_supported_platforms):
            """Test return structure with mocked dependencies."""
            # Setup mocks
            mock_native_platform.return_value = 'linux/amd64'
            mock_supported_platforms.return_value = ['linux/amd64', 'linux/arm64', 'linux/amd64/v2']

            _clear_platform_cache()

            result = get_platform_compatibility_status()

            # Test structure
            assert isinstance(result, dict)
            assert 'platform_compatibility' in result
            assert 'native_platform' in result
            assert 'emulated_platforms' in result

            # Test content
            assert result['native_platform'] == 'linux/amd64'
            assert result['platform_compatibility']['linux/amd64'] == CompatibilityStatus.NATIVE
            assert result['platform_compatibility']['linux/amd64/v2'] == CompatibilityStatus.NATIVE
            assert result['platform_compatibility']['linux/arm64'] == CompatibilityStatus.EMULATED
            assert result['emulated_platforms'] == ['linux/arm64']

    class TestIntegrationTests:
        """Integration tests with real system for cross-architecture scenarios."""

        @pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
        def test_cross_architecture_amd64_host(self):
            """Test cross-architecture compatibility on amd64 host (covers emulated and non-emulated scenarios)."""
            result = get_platform_compatibility_status()

            # On amd64, should have linux/amd64 as native
            assert result['native_platform'] == 'linux/amd64'
            assert result['platform_compatibility']['linux/amd64'] == CompatibilityStatus.NATIVE

            # Test cross-architecture cases (covers both EMULATED and INCOMPATIBLE scenarios)
            arm64_status = get_platform_compatibility_status('linux/arm64')
            assert arm64_status in [CompatibilityStatus.EMULATED, CompatibilityStatus.INCOMPATIBLE]

            # Test amd64 variants should be native
            amd64_v2_status = get_platform_compatibility_status('linux/amd64/v2')
            if 'linux/amd64/v2' in result['platform_compatibility']:
                assert amd64_v2_status == CompatibilityStatus.NATIVE
            else:
                assert amd64_v2_status == CompatibilityStatus.INCOMPATIBLE

        @pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
        def test_cross_architecture_arm64_host(self):
            """Test cross-architecture compatibility on ARM64 host (covers emulated and non-emulated scenarios)."""
            result = get_platform_compatibility_status()

            # On ARM64, should have linux/arm64 as native
            assert result['native_platform'] == 'linux/arm64'
            assert result['platform_compatibility']['linux/arm64'] == CompatibilityStatus.NATIVE

            # Test cross-architecture cases (covers both EMULATED and INCOMPATIBLE scenarios)
            amd64_status = get_platform_compatibility_status('linux/amd64')
            assert amd64_status in [CompatibilityStatus.EMULATED, CompatibilityStatus.INCOMPATIBLE]

            # Test arm64 variants should be native
            arm64_v8_status = get_platform_compatibility_status('linux/arm64/v8')
            if 'linux/arm64/v8' in result['platform_compatibility']:
                assert arm64_v8_status == CompatibilityStatus.NATIVE
            else:
                assert arm64_v8_status == CompatibilityStatus.INCOMPATIBLE
