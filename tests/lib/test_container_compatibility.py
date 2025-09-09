import os
import platform
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.container_compatibility import CompatibilityStatus
from lib.container_compatibility import _is_compatible_architecture_variant
from lib.container_compatibility import check_image_architecture_compatibility
from lib.container_compatibility import _clear_platform_cache


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

    def test_architecture_compatibility_check_native_image(self):
        """Test architecture compatibility checking with native architecture image"""

        # Test with hello-world which should be native amd64 on most systems
        compat_info = check_image_architecture_compatibility('hello-world')

        assert isinstance(compat_info, dict)
        assert 'image_arch' in compat_info
        assert 'host_arch' in compat_info
        assert 'status' in compat_info
        assert 'can_run' in compat_info
        assert 'needs_emulation' in compat_info

        # On native architecture, these should be true
        if compat_info['image_arch'] == compat_info['host_arch']:
            assert compat_info['status'] == CompatibilityStatus.NATIVE
            assert compat_info['is_native_compatible'] is True
            assert compat_info['needs_emulation'] is False
            assert compat_info['can_run'] is True

    @pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
    def test_architecture_compatibility_check_arm64_image_on_x86_64_host(self):
        """Test architecture compatibility checking with ARM64 image on x86_64 host"""

        # Use ARM64 alpine image on x86_64 host
        compat_info = check_image_architecture_compatibility('alpine@sha256:4562b419adf48c5f3c763995d6014c123b3ce1d2e0ef2613b189779caa787192')

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
            # Should be verified if we're testing with verification enabled
            assert isinstance(compat_info['emulation_verified'], bool)
        elif compatibility_status == CompatibilityStatus.INCOMPATIBLE:
            # If no working emulation, container cannot run
            assert compat_info['can_run'] is False
            assert compat_info['needs_emulation'] is False

    @pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
    def test_architecture_compatibility_check_amd64_image_on_arm64_host(self):
        """Test architecture compatibility checking with AMD64 image on ARM64 host"""

        # Use AMD64 alpine image on ARM64 host
        compat_info = check_image_architecture_compatibility('alpine@sha256:eafc1edb577d2e9b458664a15f23ea1c370214193226069eb22921169fc7e43f')

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
            # Should be verified if we're testing with verification enabled
            assert isinstance(compat_info['emulation_verified'], bool)
        elif compatibility_status == CompatibilityStatus.INCOMPATIBLE:
            # If no working emulation, container cannot run
            assert compat_info['can_run'] is False
            assert compat_info['needs_emulation'] is False
            assert compat_info['emulation_verified'] is False
