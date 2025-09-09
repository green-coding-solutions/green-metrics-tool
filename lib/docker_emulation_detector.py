import platform as platform_module
import subprocess
import json
import os


class DockerEmulationDetector:
    """
    Detects Docker emulation capabilities across Linux, macOS, and WSL2.
    """

    # Common architecture mappings - matches scenario_runner.py patterns
    ARCH_MAPPING = {
        'x86_64': 'amd64',
        'aarch64': 'arm64',
        'arm64': 'arm64',
        'armv7l': 'arm',  # Simplified to match GMT patterns
        'armv6l': 'arm',
        'i386': '386',
        's390x': 's390x',
        'ppc64le': 'ppc64le'
    }

    def __init__(self):
        self.os_type = self._detect_os()
        self.native_arch = self._get_native_architecture()

    def _detect_os(self):
        """Detect the operating system type."""
        system = platform_module.system().lower()

        # Check for WSL2
        if system == 'linux' and self._is_wsl2():
            return 'wsl2'

        return system

    def _is_wsl2(self):
        """Check if running under WSL2."""
        try:
            # Check for WSL environment
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r', encoding='utf-8') as f:
                    version_info = f.read().lower()
                    return 'microsoft' in version_info and 'wsl2' in version_info

            # Alternative check
            if 'WSL_DISTRO_NAME' in os.environ:
                return True

        except (OSError, IOError):
            pass

        return False

    def _get_native_architecture(self):
        """Get the native architecture in Docker platform format."""
        machine = platform_module.machine().lower()
        return self.ARCH_MAPPING.get(machine, machine)

    def _run_command(self, cmd):
        """Run a command and return success, stdout, stderr - matches GMT patterns."""
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='UTF-8',
                check=False,
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except (subprocess.SubprocessError, OSError) as e:
            return False, "", str(e)

    def _check_binfmt_misc_linux(self):
        """Check binfmt_misc for QEMU emulation support on Linux."""
        emulated_archs = []
        binfmt_path = '/proc/sys/fs/binfmt_misc'

        if not os.path.exists(binfmt_path):
            return emulated_archs

        try:
            for entry in os.listdir(binfmt_path):
                if entry.startswith('qemu-'):
                    # Extract architecture from qemu-<arch> format
                    arch = entry[5:]  # Remove 'qemu-' prefix

                    # Map QEMU arch names to Docker platform names
                    if arch == 'aarch64':
                        emulated_archs.append('arm64')
                    elif arch == 'arm':
                        emulated_archs.append('arm')
                    elif arch == 'x86_64':
                        emulated_archs.append('amd64')
                    elif arch in ['i386', '386']:
                        emulated_archs.append('386')
                    else:
                        emulated_archs.append(arch)

        except (OSError, IOError):
            pass

        return emulated_archs

    def _check_docker_buildx(self):
        """Check supported platforms using docker buildx."""
        success, stdout, _ = self._run_command(['docker', 'buildx', 'ls'])

        if not success:
            return [], "buildx_not_available"

        platforms = set()

        # Try to get detailed platform info
        success, stdout, _ = self._run_command([
            'docker', 'buildx', 'inspect', '--bootstrap'
        ])

        if success:
            # Parse buildx inspect output
            for line in stdout.split('\n'):
                if 'Platforms:' in line:
                    # Extract platforms from "Platforms: linux/amd64, linux/arm64, ..." format
                    platforms_str = line.split('Platforms:')[1].strip()
                    for platform in platforms_str.split(','):
                        platform = platform.strip()
                        if platform and '/' in platform:
                            platforms.add(platform)

        return list(platforms), "buildx"

    def _check_docker_info(self):
        """Check Docker system info for architecture support."""
        success, stdout, _ = self._run_command(['docker', 'system', 'info', '--format', '{{json .}}'])

        if not success:
            return [], "docker_info_failed"

        try:
            info = json.loads(stdout)

            # Check for architecture info
            architecture = info.get('Architecture', '')

            # Basic platform based on system info
            if architecture:
                mapped_arch = self.ARCH_MAPPING.get(architecture.lower(), architecture.lower())
                return [f"linux/{mapped_arch}"], "docker_info"

        except json.JSONDecodeError:
            pass

        return [], "docker_info_parse_failed"

    def _test_emulation_capability(self, target_platform):
        """Test if a specific platform can be emulated by running a simple container."""
        try:
            # Try to run hello-world with specific platform
            success, _, _ = self._run_command([
                'docker', 'run', '--rm', '--platform', target_platform,
                'hello-world'
            ])
            return success
        except (subprocess.SubprocessError, OSError):
            return False

    def detect_emulation_support(self, test_foreign_platforms=False):
        """
        Detect Docker emulation capabilities.

        Args:
            test_foreign_platforms: If True, actually test running foreign architecture containers

        Returns:
            Dict with emulation capability information
        """
        all_platforms = set()
        emulated_platforms = []
        detection_methods = []

        # Method 1: Check binfmt_misc (Linux/WSL2 only)
        if self.os_type in ['linux', 'wsl2']:
            binfmt_archs = self._check_binfmt_misc_linux()
            if binfmt_archs:
                for arch in binfmt_archs:
                    all_platforms.add(f"linux/{arch}")
                detection_methods.append("binfmt_misc")

        # Method 2: Check docker buildx
        buildx_platforms, buildx_method = self._check_docker_buildx()
        if buildx_platforms:
            all_platforms.update(buildx_platforms)
            detection_methods.append(buildx_method)

        # Method 3: Check docker system info
        info_platforms, info_method = self._check_docker_info()
        if info_platforms:
            all_platforms.update(info_platforms)
            detection_methods.append(info_method)

        # Determine native platform
        native_platform = f"linux/{self.native_arch}"

        # Separate emulated platforms from native
        for platform in all_platforms:
            if platform != native_platform:
                emulated_platforms.append(platform)

        # Optional: Test actual emulation capability
        if test_foreign_platforms and emulated_platforms:
            tested_platforms = []
            for platform in emulated_platforms[:2]:  # Test max 2 to avoid long delays
                if self._test_emulation_capability(platform):
                    tested_platforms.append(platform)
            emulated_platforms = tested_platforms
            if tested_platforms:
                detection_methods.append("runtime_test")

        return {
            'supported_platforms': list(all_platforms),
            'native_platform': native_platform,
            'emulation_available': len(emulated_platforms) > 0,
            'emulated_platforms': emulated_platforms,
            'detection_method': " + ".join(detection_methods)
        }

    def can_run_platform(self, target_platform):
        """
        Check if a specific platform can be run (either natively or via emulation).

        Args:
            target_platform: Platform string like "linux/arm64" or "linux/amd64"
        """
        capability = self.detect_emulation_support()
        return target_platform in capability['supported_platforms']


def check_container_compatibility(image_platform):
    """
    Check if a container with given platform can run on current system.

    Args:
        image_platform: Platform string like "linux/arm64"

    Returns:
        Dictionary with compatibility information
    """
    detector = DockerEmulationDetector()
    capability = detector.detect_emulation_support()

    can_run = detector.can_run_platform(image_platform)
    needs_emulation = image_platform != capability['native_platform'] and can_run

    return {
        'can_run': can_run,
        'needs_emulation': needs_emulation,
        'native_platform': capability['native_platform'],
        'target_platform': image_platform,
        'emulation_available': capability['emulation_available'],
        'detection_method': capability['detection_method']
    }
