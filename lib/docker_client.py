import re
import subprocess
from dataclasses import dataclass

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from requests.exceptions import ReadTimeout


@dataclass
class DockerCommandResult:
    args: list[str] | str
    returncode: int
    stdout: str = ''
    stderr: str = ''


def _decode(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return value.decode('UTF-8', errors='replace')


def _docker_exception_message(exc):
    return getattr(exc, 'explanation', None) or str(exc)


def docker_exception_to_called_process_error(exc, cmd):
    return subprocess.CalledProcessError(
        1,
        cmd,
        output='',
        stderr=_docker_exception_message(exc),
    )


def docker_duration_to_ns(value):
    if isinstance(value, int):
        return value
    if value is None:
        return None

    value = str(value).strip()
    if value.isdigit():
        return int(value)

    units = {
        'h': 60 * 60 * 1_000_000_000,
        'm': 60 * 1_000_000_000,
        's': 1_000_000_000,
        'ms': 1_000_000,
        'us': 1_000,
        'ns': 1,
    }
    total = 0
    pos = 0
    for match in re.finditer(r'(\d+)(h|ms|us|ns|m|s)', value):
        if match.start() != pos:
            raise ValueError(f"Unsupported Docker duration value: {value}")
        total += int(match.group(1)) * units[match.group(2)]
        pos = match.end()
    if pos != len(value):
        raise ValueError(f"Unsupported Docker duration value: {value}")
    return total


class DockerClient:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def ping(self):
        self.client.ping()

    def list_running_container_names(self):
        return [container.name for container in self.client.containers.list()]

    def get_container(self, container_name):
        return self.client.containers.get(container_name)

    def is_container_running(self, container_name):
        try:
            container = self.get_container(container_name)
            container.reload()
            return container.status == 'running'
        except NotFound:
            return False

    def container_logs(self, container_name, *, stdout=True, stderr=True):
        container = self.get_container(container_name)
        stdout_text = _decode(container.logs(stdout=stdout, stderr=False)) if stdout else ''
        stderr_text = _decode(container.logs(stdout=False, stderr=stderr)) if stderr else ''
        return stdout_text, stderr_text

    def container_exit_code(self, container_name):
        try:
            container = self.get_container(container_name)
            container.reload()
            return container.attrs.get('State', {}).get('ExitCode')
        except NotFound:
            return None

    def container_image_name(self, container_name):
        container = self.get_container(container_name)
        container.reload()
        return container.attrs.get('Config', {}).get('Image')

    def container_state(self, container_name):
        container = self.get_container(container_name)
        container.reload()
        return container.attrs.get('State', {})

    def remove_container_force(self, container_name):
        try:
            self.get_container(container_name).remove(force=True)
        except NotFound:
            return

    def pause_container(self, container_name):
        self.get_container(container_name).pause()

    def run_container_detached(self, *, image, command, name, mounts, volumes, environment,
                               labels, ports, networks, network_aliases, entrypoint,
                               healthcheck, host_options):
        kwargs = {
            'detach': True,
            'tty': True,
            'stdin_open': True,
            'name': name,
            'mounts': mounts,
            'volumes': volumes,
            'environment': environment,
            'labels': labels,
            'ports': ports,
            'entrypoint': entrypoint,
            'healthcheck': healthcheck,
            **host_options,
        }

        kwargs = {key: value for key, value in kwargs.items() if value not in (None, [], {})}

        if networks and networks[0] in ('host', 'bridge', 'none'):
            kwargs['network_mode'] = networks[0]
        elif networks:
            kwargs['network'] = networks[0]
            if network_aliases:
                kwargs['networking_config'] = {
                    network: docker.types.EndpointConfig(aliases=network_aliases.get(network, []))
                    for network in networks
                }

        container = self.client.containers.run(image, command=command or None, **kwargs)

        for network in networks[1:]:
            self.client.networks.get(network).connect(
                container,
                aliases=network_aliases.get(network, []),
            )

        return container.id

    def run_container_and_wait(self, *, image, command, mounts, volumes, environment,
                               timeout=None, stream_output=False, host_options=None,
                               display_cmd=None):
        container = None
        host_options = host_options or {}
        try:
            container = self.client.containers.run(
                image,
                command=command,
                detach=True,
                mounts=mounts,
                volumes=volumes,
                environment=environment,
                **host_options,
            )
            if stream_output:
                for line in container.logs(stream=True, follow=True):
                    print(_decode(line), end='')
            try:
                wait_result = container.wait(timeout=timeout)
            except ReadTimeout as exc:
                raise subprocess.TimeoutExpired(display_cmd or [image, *(command or [])], timeout) from exc
            stdout_text, stderr_text = self.container_logs(container.id)
            return DockerCommandResult(
                args=[image, *(command or [])],
                returncode=wait_result.get('StatusCode', 1),
                stdout=stdout_text,
                stderr=stderr_text,
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError:
                    pass

    def image_exists(self, image_name):
        try:
            self.client.images.get(image_name)
            return True
        except ImageNotFound:
            return False

    def pull_image(self, image_name):
        self.client.images.pull(image_name)

    def tag_image(self, source, target):
        image = self.client.images.get(source)
        if not image.tag(target):
            raise RuntimeError(f"Could not tag Docker image '{source}' as '{target}'")

    def load_image(self, tar_path):
        with open(tar_path, 'rb') as tar_file:
            self.client.images.load(tar_file.read())

    def image_size(self, image_name):
        image = self.client.images.get(image_name)
        return int(image.attrs.get('Size', 0))

    def registry_mirrors(self):
        info = self.client.info()
        return info.get('RegistryConfig', {}).get('Mirrors', []) or []

    def remove_image(self, image_name, *, force=True):
        try:
            self.client.images.remove(image=image_name, force=force)
        except ImageNotFound:
            return
        except APIError:
            return

    def remove_temporary_gmt_images(self):
        for image in self.client.images.list(all=True):
            for tag in image.tags:
                if 'gmt_run_tmp' in tag:
                    self.remove_image(tag, force=True)

    def stop_all_containers(self):
        for container in self.client.containers.list(all=True):
            try:
                container.stop()
            except APIError:
                pass

    def remove_non_whitelisted_images(self, whitelist):
        for image in self.client.images.list(all=True):
            tags = image.tags or []
            if any(any(allowed in tag for allowed in whitelist) for tag in tags):
                continue
            try:
                self.client.images.remove(image=image.id, force=True)
            except APIError:
                pass

    def system_prune(self, *, volumes=True):
        self.client.containers.prune()
        self.client.networks.prune()
        self.client.images.prune()
        if volumes:
            self.client.volumes.prune()
        try:
            self.client.api.prune_builds()
        except (APIError, AttributeError):
            pass

    def remove_network(self, network_name):
        try:
            self.client.networks.get(network_name).remove()
        except NotFound:
            return

    def create_network(self, network_name, *, internal=False):
        return self.client.networks.create(network_name, internal=internal)

    def volume_exists(self, volume_name):
        try:
            self.client.volumes.get(volume_name)
            return True
        except NotFound:
            return False

    def volume_mountpoint(self, volume_name):
        volume = self.client.volumes.get(volume_name)
        return volume.attrs.get('Mountpoint')

    @staticmethod
    def mount_from_cli(mount_string):
        values = {}
        read_only = False
        for item in mount_string.split(','):
            if item in ('readonly', 'ro'):
                read_only = True
                continue
            key, value = item.split('=', 1)
            values[key] = value

        target = values.get('target') or values.get('dst') or values.get('destination')
        source = values.get('source') or values.get('src')
        mount_type = values.get('type', 'volume')

        return docker.types.Mount(
            target=target,
            source=source,
            type=mount_type,
            read_only=read_only,
        )

    @staticmethod
    def docker_exception_message(exc):
        if isinstance(exc, DockerException):
            return _docker_exception_message(exc)
        return str(exc)
