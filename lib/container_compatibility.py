import platform as platform_module
import subprocess
import json
from enum import Enum


# Cache for platform detection results
_platform_cache = {}

def _clear_platform_cache():
    """Clear the platform detection cache. Primarily for testing purposes."""
    _platform_cache.clear()

class CompatibilityStatus(Enum):
    """Docker platform compatibility status."""
    NATIVE = 'NATIVE'
    EMULATED = 'EMULATED'
    INCOMPATIBLE = 'INCOMPATIBLE'

# Common architecture mappings for Docker platform detection
ARCH_MAPPING = {
    'x86_64': 'amd64',
    'amd64': 'amd64',
    'aarch64': 'arm64',
    'arm64': 'arm64',
    'armv7l': 'arm',
    'armv6l': 'arm',
    'arm': 'arm',
    'i386': '386',
    'i686': '386',
    's390x': 's390x',
    'ppc64le': 'ppc64le'
}


def _execute_command_safe(cmd):
    """Run a command and return success, stdout, stderr.
    
    Returns:
        Tuple of (success_bool, stdout_string, stderr_string)
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='UTF-8',
            check=False,
            timeout=5
        )
        return result.returncode == 0, result.stdout, result.stderr
    except (subprocess.SubprocessError, OSError) as e:
        return False, "", str(e)


def get_native_architecture():
    """Get the native architecture in Docker platform format.
    
    Returns:
        String representing architecture (e.g., 'amd64', 'arm64')
    """
    machine = platform_module.machine().lower()
    return ARCH_MAPPING.get(machine, machine)


def get_native_platform():
    """Get the native platform in Docker format (OS/architecture).
    
    Docker containers always run as Linux, even on macOS/Windows.
    Windows containers are not supported.
    
    Returns:
        String representing platform (e.g., 'linux/amd64', 'linux/arm64')
    """
    # Docker containers always run as Linux, even on macOS/Windows
    # This matches how Docker handles cross-platform containers
    arch = get_native_architecture()
    return f"linux/{arch}"


def _get_platforms_via_buildx():
    """Check supported platforms using docker buildx.
    
    Returns:
        List of supported platform strings
    """
    # Check if buildx is available
    success, _, _ = _execute_command_safe(['docker', 'buildx', 'version'])
    if not success:
        return []

    # Get platform information
    success, stdout, _ = _execute_command_safe([
        'docker', 'buildx', 'inspect', '--bootstrap'
    ])

    if not success:
        return []

    platforms = set()
    for line in stdout.split('\n'):
        line = line.strip()
        if line.startswith('Platforms:'):
            # Extract platforms from "Platforms: linux/amd64, linux/arm64, ..." format
            platforms_str = line[10:].strip()  # Remove 'Platforms:' prefix
            for platform in platforms_str.split(','):
                platform = platform.strip()
                if platform and '/' in platform:
                    platforms.add(platform)
            break

    return list(platforms)


def _get_platforms_via_docker_version():
    """Check Docker version for basic platform support as fallback when buildx unavailable.
    
    Returns:
        List of supported platform strings
    """
    success, stdout, _ = _execute_command_safe(['docker', 'version', '--format', 'json'])

    if not success:
        return []

    try:
        info = json.loads(stdout)
        server_info = info.get('Server', {})
        architecture = server_info.get('Arch', '')

        if architecture:
            mapped_arch = ARCH_MAPPING.get(architecture.lower(), architecture.lower())
            return [f"linux/{mapped_arch}"]

    except (json.JSONDecodeError, KeyError):
        pass

    return []


def _get_supported_platforms():
    """Get all supported platforms using Docker buildx.
    
    Returns:
        List of supported platform strings
    """
    cache_key = 'supported_platforms'
    if cache_key in _platform_cache:
        return _platform_cache[cache_key]

    # Try buildx first (most reliable)
    platforms = _get_platforms_via_buildx()
    if platforms:
        _platform_cache[cache_key] = platforms
        return platforms

    print("Warning: Could not determine platform support with docker buildx, falling back to basic detection.")

    # Fallback to basic system info
    platforms = _get_platforms_via_docker_version()
    if platforms:
        _platform_cache[cache_key] = platforms
        return platforms

    # Final fallback to native platform
    native_platform = get_native_platform()
    platforms = [native_platform]
    _platform_cache[cache_key] = platforms
    return platforms


def _can_run_natively(target_platform, host_platform):
    """Check if a target platform can run natively on the host architecture.
    
    Considers two types of native compatibility:
    1. Architecture variants: linux/amd64/v2, linux/amd64/v3, linux/amd64/v4
       are native instruction set variants that run without emulation
    2. Backward compatibility: Newer architectures can run older instruction sets
       natively due to hardware backward compatibility (e.g., amd64 can run 386)
    
    Args:
        target_platform: Platform string to check (e.g., 'linux/amd64/v2')
        host_platform: Host's native platform string (e.g., 'linux/amd64')
    
    Returns:
        True if target_platform can run natively, False if it requires emulation
    """
    if target_platform == host_platform:
        return True

    # Extract base architecture from both platforms for comparison
    # Format: linux/architecture[/variant]
    if '/' not in target_platform or '/' not in host_platform:
        return False

    target_parts = target_platform.split('/')
    host_parts = host_platform.split('/')

    # Ensure both platforms have at least OS and architecture parts (e.g., 'linux/amd64')
    if len(target_parts) < 2 or len(host_parts) < 2:
        return False

    if target_parts[0] != host_parts[0]:  # Different OS
        return False

    target_arch = target_parts[1]
    host_arch = host_parts[1]

    # Handle native backward compatibility cases
    if host_arch == 'amd64' and target_arch == '386':
        # 32-bit x86 runs natively on amd64 without emulation
        return True

    if target_arch != host_arch:  # Different base architecture
        return False

    # Same base architecture - check if this is a variant
    # Variants have additional parts (e.g., linux/amd64/v2 vs linux/amd64)
    if len(target_parts) > len(host_parts):
        # This is a variant of the native architecture
        return True

    return False


def get_platform_compatibility_status(platform=None):
    """
    Get platform compatibility information.
    
    Args:
        platform: Optional platform string (e.g., 'linux/arm64').
                 If provided, returns CompatibilityStatus for that platform.
                 If None, returns full compatibility details dict.
        
    Returns:
        If platform specified: CompatibilityStatus (NATIVE, EMULATED, or INCOMPATIBLE)
        If platform is None: Dict with detailed platform compatibility information containing:
            - platform_compatibility: Dict mapping platforms to CompatibilityStatus
            - native_platform: String of the host's native platform
            - emulated_platforms: List of platforms that require emulation
    """
    cache_key = 'emulation_support_detailed'
    if cache_key in _platform_cache:
        compatibility_data = _platform_cache[cache_key]
    else:
        # Get supported platforms
        all_platforms = _get_supported_platforms()

        # Determine native platform
        native_platform = get_native_platform()

        # If native platform not in detected platforms, add it
        if native_platform not in all_platforms:
            all_platforms.append(native_platform)

        platform_compatibility = {}
        emulated_platforms = []

        for p in all_platforms:
            if _can_run_natively(p, native_platform):
                # Can run natively (exact match, variant, or backward compatible)
                platform_compatibility[p] = CompatibilityStatus.NATIVE
            else:
                # Requires emulation
                platform_compatibility[p] = CompatibilityStatus.EMULATED
                emulated_platforms.append(p)

        compatibility_data = {
            'platform_compatibility': platform_compatibility,
            'native_platform': native_platform,
            'emulated_platforms': emulated_platforms,
        }

        _platform_cache[cache_key] = compatibility_data

    # Return specific platform status if requested
    if platform is not None:
        return compatibility_data['platform_compatibility'].get(platform, CompatibilityStatus.INCOMPATIBLE)

    # Return full compatibility data
    return compatibility_data


def check_image_architecture_compatibility(image_name):
    """Check if Docker image can run on host, with detailed compatibility analysis.

    Performs comprehensive architecture compatibility checking by:
    - Inspecting image architecture via Docker
    - Detecting host emulation capabilities
    - Determining if image can run natively, via emulation, or not at all

    Args:
        image_name: The Docker image name to check

    Returns:
        Dict containing:
            - image_arch: Architecture of the Docker image
            - host_arch: Native architecture of the host  
            - image_platform: Full platform string (e.g., 'linux/arm64')
            - status: CompatibilityStatus enum (NATIVE, EMULATED, or INCOMPATIBLE)
            - can_run: True if image can execute (natively or via emulation)
            - needs_emulation: True if emulation is required to run
            - is_native_compatible: True if image runs natively without emulation
            - error: Error message if compatibility check failed, None otherwise
    """
    try:
        # Get image architecture
        ps = subprocess.run(
            ['docker', 'image', 'inspect', image_name, '--format', '{{.Architecture}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', check=False
        )

        if ps.returncode != 0:
            raise RuntimeError(f"Failed to inspect Docker image architecture for '{image_name}': {ps.stderr.strip()}")

        image_arch = ps.stdout.strip()
        # Docker images are typically Linux-based containers
        image_platform = f"linux/{image_arch}"

        image_compatibility_status = get_platform_compatibility_status(image_platform)
        can_run = image_compatibility_status in [CompatibilityStatus.NATIVE, CompatibilityStatus.EMULATED]
        needs_emulation = image_compatibility_status == CompatibilityStatus.EMULATED
        is_native = image_compatibility_status == CompatibilityStatus.NATIVE

        return {
            'image_arch': image_arch,
            'host_arch': get_native_architecture(),
            'image_platform': image_platform,
            'status': image_compatibility_status,
            'can_run': can_run,
            'needs_emulation': needs_emulation,
            'is_native_compatible': is_native,
            'error': None
        }

    except Exception as e: #pylint: disable=broad-except
        return {
            'image_arch': 'unknown',
            'host_arch': get_native_architecture(),
            'image_platform': 'unknown',
            'status': CompatibilityStatus.INCOMPATIBLE,
            'can_run': False,
            'needs_emulation': False,
            'is_native_compatible': False,
            'error': str(e)
        }


if __name__ == '__main__':
    compatibility_status = get_platform_compatibility_status()

    print('Native platform:', compatibility_status['native_platform'])
    print('Platform compatibility:')

    for platform_name, status in compatibility_status['platform_compatibility'].items():
        print(f'  {platform_name}: {status.value}')

    if compatibility_status['emulated_platforms']:
        print('Emulation supported:', ', '.join(compatibility_status['emulated_platforms']))
    else:
        print('No emulation supported')
