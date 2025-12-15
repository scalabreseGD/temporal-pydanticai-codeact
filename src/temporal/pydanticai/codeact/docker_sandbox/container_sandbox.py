"""
Docker-based sandbox for safe code execution with persistent state.

This module provides three sandbox implementations for executing Python and bash
code in isolated Docker containers with persistent variable state:

1. PersistentContainerSandbox: Core implementation with container lifecycle management
2. DurablePersistentContainerSandbox: Temporal activity wrapper for workflow integration
3. StatelessPersistentSandbox: Agent instrumentation layer for serverless execution

Features:
- Isolated execution in Docker containers
- Persistent Python variable state across executions (via pickle)
- Package installation (system and Python)
- File operations (read/write/list)
- Container lifecycle management
- Thread-safe async operations
"""

import asyncio
import inspect
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Type, get_type_hints, Optional, Sequence

import docker
from docker.errors import ImageNotFound
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP, MCPServerSSE
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.exceptions import ApplicationError

from temporal.pydanticai.codeact.datamodels.sandbox import StartContainerArgs, SandboxBaseArgs, ReadVariableInStateArgs, \
    ExecutePythonArgs, \
    ExecuteBashArgs, WriteFileArgs, SandboxInputTask, SandboxTaskTypes, SandboxTaskArgsAdapter, \
    InstallAdditionalPackagesArgs, ReadOperationsArgs
from .sandbox import SANDBOX_DIR, DOCKERFILE_PATH


class PersistentContainerSandbox:
    """
    Docker-based sandbox with persistent Python variable state.

    Manages the lifecycle of Docker containers for code execution, with support
    for persistent state across multiple code executions. Variables created in
    one execution are available in subsequent executions within the same container.

    The sandbox uses a custom Docker image with Python and uv package manager,
    and maintains state via pickle serialization in /tmp/sandbox_state/.

    Attributes:
        client: Docker client for container management.
        sandbox_dir: Directory containing Dockerfile and state management scripts.
        dockerfile_path: Path to the Dockerfile for building the sandbox image.
        image_name: Name of the Docker image.
        image_tag: Tag for the Docker image.
        full_image_name: Complete image identifier (name:tag).
        memory_limit: Memory limit for containers (e.g., '512m').
        cpu_limit: CPU limit for containers (e.g., 1.0 = 1 core).
        enable_network: Whether containers should have network access.
        executor: ThreadPoolExecutor for async Docker operations.

    Example:
        ```python
        sandbox = PersistentContainerSandbox()
        container_id = await sandbox.start_container(
            StartContainerArgs(python_packages=['numpy', 'pandas'])
        )

        result = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container_id,
                code="x = 42\\nprint(x)"
            )
        )
        print(result['output'])  # "42"

        # State persists across executions
        result2 = await sandbox.execute_python(
            ExecutePythonArgs(
                container_id=container_id,
                code="print(x * 2)"
            )
        )
        print(result2['output'])  # "84"

        await sandbox.stop_container(SandboxBaseArgs(container_id=container_id))
        ```
    """

    def __init__(
            self,
            dockerfile_path: str = None,
            image_name: str = "python-uv-sandbox",
            image_tag: str = "latest",
            memory_limit: str = "512m",
            cpu_limit: float = 1.0,
            enable_network: bool = True,
            enable_persistence: bool = True,
            volume_driver: str = "local",
            volume_driver_opts: Optional[Dict[str, str]] = None
    ):
        """
        Initialize PersistentContainerSandbox.

        Args:
            dockerfile_path: Path to custom Dockerfile (optional).
            image_name: Name of the Docker image.
            image_tag: Tag for the Docker image.
            memory_limit: Memory limit for containers (e.g., '512m').
            cpu_limit: CPU limit for containers (e.g., 1.0 = 1 core).
            enable_network: Whether containers should have network access.
            enable_persistence: If True, creates named volumes for workflow state persistence.
            volume_driver: Docker volume driver (default: 'local', can be 'nfs', 'azure-file-volume', etc.).
            volume_driver_opts: Driver-specific options for network storage (e.g., NFS config).

        Example:
            ```python
            # Local persistence (default)
            sandbox = PersistentContainerSandbox()

            # No persistence (ephemeral)
            sandbox = PersistentContainerSandbox(enable_persistence=False)

            # NFS-backed persistence for multi-host
            sandbox = PersistentContainerSandbox(
                volume_driver='nfs',
                volume_driver_opts={
                    'type': 'nfs',
                    'o': 'addr=nfs-server.com,rw',
                    'device': ':/exports/workflows'
                }
            )
            ```
        """
        self.client = docker.from_env()

        # Set sandbox directory - use packaged sandbox module
        if dockerfile_path is None:
            self.sandbox_dir = SANDBOX_DIR
            self.dockerfile_path = str(DOCKERFILE_PATH)
        else:
            self.dockerfile_path = dockerfile_path
            self.sandbox_dir = Path(dockerfile_path).parent

        self.image_name = image_name
        self.image_tag = image_tag
        self.full_image_name = f"{image_name}:{image_tag}"
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.enable_network = enable_network

        # Persistence configuration
        self.enable_persistence = enable_persistence
        self.volume_driver = volume_driver
        self.volume_driver_opts = volume_driver_opts or {}

        # Dictionary to store containers: {container_id: container_object}
        # self.containers: Dict[str, Any] = {}

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=10)

        self._ensure_image()

    def _get_container_by_id(self, container_id: str):
        try:
            return self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return None

    def _ensure_image(self):
        """Ensure Docker image exists, build if not present"""
        try:
            self.client.images.get(self.full_image_name)
            print(f"Image {self.full_image_name} found")
        except docker.errors.ImageNotFound:
            print(f"Image {self.full_image_name} not found, building...")
            self._build_image()

    def _build_image(self):
        """Build Docker image from Dockerfile"""
        if not os.path.exists(self.dockerfile_path):
            raise FileNotFoundError(
                f"Dockerfile not found at: {self.dockerfile_path}\n"
                f"Please ensure {self.dockerfile_path} exists in your project."
            )

        dockerfile_dir = str(Path(self.dockerfile_path).parent)
        if not dockerfile_dir or dockerfile_dir == ".":
            dockerfile_dir = os.getcwd()

        dockerfile_name = Path(self.dockerfile_path).name

        print(f"Building image from {self.dockerfile_path}...")

        try:
            image, build_logs = self.client.images.build(
                path=dockerfile_dir,
                dockerfile=dockerfile_name,
                tag=self.full_image_name,
                rm=True,
                forcerm=True
            )

            for log in build_logs:
                if 'stream' in log:
                    print(log['stream'].strip())
                elif 'error' in log:
                    print(f"ERROR: {log['error']}")

            print(f"✓ Image {self.full_image_name} built successfully")

        except docker.errors.BuildError as e:
            print(f"Build failed: {e}")
            raise

    def _ensure_volume(self, volume_name: str) -> None:
        """
        Ensure a named Docker volume exists, creating it if necessary.

        Args:
            volume_name: Name of the volume to create.
        """
        try:
            self.client.volumes.get(volume_name)
            print(f"Volume '{volume_name}' already exists, reusing...")
        except docker.errors.NotFound:
            print(f"Creating volume '{volume_name}'...")
            self.client.volumes.create(
                name=volume_name,
                driver=self.volume_driver,
                driver_opts=self.volume_driver_opts if self.volume_driver_opts else None
            )
            print(f"Volume '{volume_name}' created successfully")

    async def start_container(
            self,
            input_model: StartContainerArgs
    ) -> str:
        """
        Start a new persistent container with optional persistent storage.

        If enable_persistence=True and container_name is provided, creates a named
        volume specific to this workflow_id that persists across container restarts.

        Args:
            input_model: Container configuration including packages and optional name.

        Returns:
            str: Container ID or container name if provided.
        """
        loop = asyncio.get_event_loop()

        # Prepare environment variables
        environment = {}
        # Pass workflow_id if container name is provided
        if input_model.container_name:
            environment['WORKFLOW_ID'] = input_model.container_name

        # Prepare kwargs for container creation
        container_kwargs = {
            'image': self.full_image_name,
            'command': ["tail", "-f", "/dev/null"],
            'detach': True,
            'mem_limit': self.memory_limit,
            'nano_cpus': int(self.cpu_limit * 1e9),
            'remove': False,
            'stdin_open': True,
            'tty': True,
            'environment': environment,
            'network_disabled': not self.enable_network
        }

        # Configure persistent storage if enabled
        if self.enable_persistence and input_model.container_name:
            # Create workflow-specific volume name
            volume_name = f"workflow-{input_model.container_name}"

            # Ensure volume exists
            await loop.run_in_executor(  # type: ignore[arg-type]
                self.executor,
                lambda: self._ensure_volume(volume_name)
            )

            # Mount volume to /persistent-storage
            container_kwargs['volumes'] = {
                volume_name: {
                    'bind': '/persistent-storage',
                    'mode': 'rw'
                }
            }
            print(f"Persistent storage enabled: volume '{volume_name}' mounted at /persistent-storage")

        # Add name if provided
        if input_model.container_name:
            container_kwargs['name'] = input_model.container_name

            # Check if container is already running otherwise continue
            container = self._get_container_by_id(input_model.container_name)
            if container:
                return input_model.container_name

        container = await loop.run_in_executor(  # type: ignore[arg-type]
            self.executor,
            lambda: self.client.containers.run(**container_kwargs)
        )

        # Return the custom name if provided, otherwise Docker's auto-generated ID
        container_id = input_model.container_name if input_model.container_name else container.id

        print(f"Container started: {container_id if input_model.container_name else container_id[:12]}")

        await self._install_packages(
            container_id,
            input_model.python_packages or [],
            input_model.system_packages or []
        )

        await self._initialize_state(container_id)

        return container_id

    async def _initialize_state(self, container_id: str):
        """Initialize persistent state storage in the container"""
        container = self._get_container_by_id(container_id)
        if not container:
            raise ValueError(f"Container {container_id} not found")

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["python", "/app/sandbox/init_state.py"],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        result = await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]
        if not result["success"]:
            raise RuntimeError(f"Failed to initialize state: {result['error']}")

    async def _install_packages(
            self,
            container_id: str,
            python_packages: List[str],
            system_packages: List[str]
    ):
        """Install system and Python packages using uv during container startup"""
        container = self._get_container_by_id(container_id)
        if not container:
            raise ValueError(f"Container {container_id} not found")

        if system_packages:
            print(f"Installing system packages: {', '.join(system_packages)}")

            await self._exec_in_container(container, ["bash", "-c", "apt-get update -qq"])

            install_cmd = f"apt-get install -y -qq {' '.join(system_packages)}"
            result = await self._exec_in_container(container, ["bash", "-c", install_cmd])

            if result["exit_code"] == 0:
                print(f"System packages installed successfully")
            else:
                raise ApplicationError(message=f"System package installation failed: {result['stderr']}",
                                       non_retryable=True)

        if python_packages:
            print(f"Installing Python packages with uv: {', '.join(python_packages)}")

            uv_cmd = f"uv pip install --system {' '.join(python_packages)}"
            result = await self._exec_in_container(container, ["bash", "-c", uv_cmd])

            if result["exit_code"] == 0:
                print(f"Python packages installed successfully with uv")
            else:
                raise ApplicationError(message=f"uv package installation failed: {result['stderr']}",
                                       non_retryable=True)

    async def _exec_in_container(self, container, cmd: List[str], environment: Dict[str, str] = None):
        """Helper to execute command in container asynchronously"""
        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=cmd,
                stdout=True,
                stderr=True,
                demux=True,
                environment=environment
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "exit_code": exit_code,
                "stdout": stdout_str,
                "stderr": stderr_str
            }

        try:
            return await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e)
            }

    def _serialize_mcp_servers(
            self,
            mcp_servers: list[MCPServerStdio | MCPServerStreamableHTTP | MCPServerSSE]
    ) -> str:
        """
        Serialize MCP server configurations to JSON for passing to container.

        Args:
            mcp_servers: List of MCP server configurations

        Returns:
            JSON string containing MCP server configurations
        """
        configs = []

        for server in mcp_servers:
            if isinstance(server, MCPServerStdio):
                # Extract command and args from MCPServerStdio
                command = getattr(server, 'command')
                args = getattr(server, 'args')
                env = getattr(server, 'env', {})
                cwd = getattr(server, 'cwd', None)
                config = {
                    'type': 'stdio',
                    'command': command,
                    'args': args,
                    'env': env,
                    'cwd': cwd,
                }
            elif isinstance(server, MCPServerStreamableHTTP):
                url = getattr(server, 'url')
                headers = getattr(server, 'headers')

                config = {
                    'type': 'streamablehttp',
                    'url': url,
                    'headers': headers,
                }
            elif isinstance(server, MCPServerSSE):
                url = getattr(server, 'url')
                headers = getattr(server, 'headers')
                config = {
                    'type': 'sse',
                    'url': url,
                    'headers': headers,
                }
            else:
                raise RuntimeError(f"Unsupported server type: {type(server)}")
            timeout = getattr(server, 'timeout')
            read_timeout = getattr(server, 'read_timeout')
            config.update({
                'timeout': timeout,
                'read_timeout': read_timeout,
            })
            configs.append(config)
        return json.dumps(configs)

    def _build_execution_script(self, input_model: ExecutePythonArgs) -> str:
        """Build the complete Python script with state management and variable injection."""
        load_state_script = (self.sandbox_dir / "load_state.py").read_text()
        save_state_script = (self.sandbox_dir / "save_state.py").read_text()

        script_parts = []

        if input_model.persist_state:
            script_parts.append(load_state_script)

        if input_model.variables:
            script_parts.append("import json")
            script_parts.append(f"_injected = json.loads('''{json.dumps(input_model.variables)}''')")
            script_parts.append("globals().update(_injected)")

        script_parts.append(input_model.code)

        if input_model.persist_state:
            script_parts.append(save_state_script)

        return "\n".join(script_parts)

    async def execute_python(
            self,
            input_model: ExecutePythonArgs,
            mcp_servers: Optional[list[MCPServerStdio | MCPServerStreamableHTTP | MCPServerSSE]] = None,
    ) -> Dict[str, Any]:
        """Execute Python code in the specified container with persistent state and optional MCP tools"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        # Build the complete script with state management
        full_script = self._build_execution_script(input_model)

        # Choose execution strategy based on whether MCP servers are provided
        if mcp_servers:
            # File-based execution with MCP tools
            def _write_code():
                container.exec_run(
                    cmd=["sh", "-c", f"cat > /tmp/user_code.py << 'EOFCODE'\n{full_script}\nEOFCODE"],
                    stdout=True,
                    stderr=True
                )

            await loop.run_in_executor(self.executor, _write_code)  # type: ignore[arg-type]

            # Prepare execution command with MCP configuration
            cmd = ["python", "/app/sandbox/execute_with_mcp.py"]
            environment = {
                'USER_CODE_PATH': '/tmp/user_code.py',
                'MCP_SERVERS_JSON': self._serialize_mcp_servers(mcp_servers)
            }
        else:
            # Inline execution without MCP
            cmd = ["python", "-c", full_script]
            environment = None

        # Execute with unified execution logic
        def _exec():
            exit_code, output = container.exec_run(
                cmd=cmd,
                stdout=True,
                stderr=True,
                demux=True,
                environment=environment
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        try:
            return await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "exit_code": -1
            }

    async def get_python_state(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        Get the current persisted Python state from a container.

        Returns a dictionary mapping variable names to their type and value info.
        Each variable entry contains:
        - type: The variable's type name
        - value: The variable's value (serialized for complex types)

        Example return:
            {
                "x": {"type": "int", "value": 42},
                "data": {"type": "list", "value": [1, 2, 3, 4, 5]}
            }
        """
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["python", "/app/sandbox/get_state.py"],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        result = await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]

        if result["success"]:
            try:
                # Parse JSON output from get_state.py
                return json.loads(result["output"].strip())
            except json.JSONDecodeError:
                return {}
        return {}

    async def clear_python_state(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """Clear the persisted Python state in a container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["python", "/app/sandbox/clear_state.py"],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        return await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]

    async def list_state_variables(self, input_model: SandboxBaseArgs) -> Dict[str, str]:
        """List all variables in the persisted state with their types"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["python", "/app/sandbox/list_variables.py"],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        result = await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]

        if result["success"]:
            try:
                import json
                return json.loads(result["output"].strip())
            except:
                return {}
        return {}

    async def read_state_variable(self, input_model: ReadVariableInStateArgs) -> Dict[str, Any]:
        """Read a specific variable from the persisted state"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["python", "/app/sandbox/read_variable.py", input_model.variable_name],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        result = await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]

        if result["success"]:
            try:
                import json
                return json.loads(result["output"].strip())
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to parse result: {str(e)}"
                }
        else:
            return {
                "success": False,
                "error": result.get("error", "Execution failed")
            }

    async def execute_bash(
            self,
            input_model: ExecuteBashArgs,
    ) -> Dict[str, Any]:
        """Execute bash commands in the specified container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["bash", "-c", input_model.script],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            return {
                "success": exit_code == 0,
                "output": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code
            }

        try:
            return await loop.run_in_executor(self.executor, _exec)  # type: ignore[arg-type]
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "exit_code": -1
            }

    async def install_additional_packages(
            self,
            input_model: InstallAdditionalPackagesArgs
    ) -> Dict[str, Any]:
        """Install additional Python packages at runtime using uv"""
        try:
            await self._install_packages(container_id=input_model.container_id,
                                         python_packages=input_model.python_packages,
                                         system_packages=input_model.system_packages)
            return {"success": True}
        except ApplicationError as e:
            return {"success": False, "error": e.message}

    async def write_file(self, input_model: WriteFileArgs) -> Dict[str, Any]:
        """Write a file to the specified container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        import tarfile
        import io

        loop = asyncio.get_event_loop()

        def _write():
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=Path(input_model.path).name)
                content_bytes = input_model.content.encode('utf-8')
                tarinfo.size = len(content_bytes)
                tar.addfile(tarinfo, io.BytesIO(content_bytes))

            tar_stream.seek(0)
            container.put_archive(
                path=str(Path(input_model.path).parent),
                data=tar_stream
            )
            return {"success": True}

        try:
            return await loop.run_in_executor(self.executor, _write)  # type: ignore[arg-type]
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_file(self, input_model: ReadOperationsArgs) -> Dict[str, Any]:
        """Read a file from the specified container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _read():
            exit_code, output = container.exec_run(
                cmd=["cat", input_model.path],
                stdout=True,
                stderr=True
            )

            if exit_code == 0:
                return {
                    "success": True,
                    "content": output.decode('utf-8'),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "content": None,
                    "error": output.decode('utf-8')
                }

        try:
            return await loop.run_in_executor(self.executor, _read)  # type: ignore[arg-type]
        except Exception as e:
            return {
                "success": False,
                "content": None,
                "error": str(e)
            }

    async def list_files(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """List files in /output directory and return absolute paths"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _list():
            # Use find to get absolute paths of files in /output
            exit_code, output = container.exec_run(
                cmd=["find", "/output", "-type", "f"],
                stdout=True,
                stderr=True,
                demux=True
            )

            stdout, stderr = output
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""

            if exit_code == 0:
                # Split output into list of file paths, filter out empty lines
                file_paths = [path.strip() for path in stdout_str.split('\n') if path.strip()]
                return {
                    "success": True,
                    "files": file_paths,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "files": [],
                    "error": stderr_str
                }

        try:
            return await loop.run_in_executor(self.executor, _list)  # type: ignore[arg-type]
        except Exception as e:
            return {
                "success": False,
                "files": [],
                "error": str(e)
            }

    async def get_container_info(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """Get information about the specified container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            return {"running": False, "error": "Container not found"}

        loop = asyncio.get_event_loop()

        def _get_info():
            container.reload()
            return {
                "running": container.status == "running",
                "id": container.id,
                "short_id": container.id[:12],
                "status": container.status,
                "image": self.full_image_name,
                "name": container.name
            }

        return await loop.run_in_executor(self.executor, _get_info)  # type: ignore[arg-type]

    async def get_all_containers(self) -> Dict[str, Any]:
        """
        Get information about all containers using this sandbox's image.

        Fetches all running and stopped containers that were created from
        the sandbox image (matching self.full_image_name) and returns
        their detailed information.

        Returns:
            Dict[str, Any]: Dictionary mapping container IDs to their info,
                where each info dict contains status, name, and other details.

        Example:
            ```python
            sandbox = PersistentContainerSandbox()
            containers = await sandbox.get_all_containers()
            for container_id, info in containers.items():
                print(f"{container_id}: {info['status']}")
            ```
        """
        loop = asyncio.get_event_loop()

        def _get_containers():
            # Fetch all containers (running and stopped) with our image
            containers = self.client.containers.list(
                all=True,
                filters={"ancestor": self.full_image_name}
            )
            return containers

        # Get containers synchronously in executor
        containers = await loop.run_in_executor(self.executor, _get_containers)  # type: ignore[arg-type]

        # Build result dict with container info
        result = {}
        for container in containers:
            container_info = await self.get_container_info(
                SandboxBaseArgs(container_id=container.id)
            )
            result[container.id] = container_info

        return result

    async def stop_container(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """Stop and remove the specified container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _stop():
            try:
                container.stop(timeout=5)
                container.remove()
                print(f"Container {input_model.container_id[:12]} stopped and removed")
            except Exception as e:
                print(f"Error stopping container: {e}")
                raise

        await loop.run_in_executor(self.executor, _stop)  # type: ignore[arg-type]
        return {"success": True}

    async def restart_container(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """Restart the specified container"""
        container = self._get_container_by_id(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _restart():
            container.restart()
            print(f"Container {input_model.container_id[:12]} restarted")

        await loop.run_in_executor(self.executor, _restart)  # type: ignore[arg-type]
        return {"success": True}

    async def cleanup_workflow_volume(self, workflow_id: str) -> Dict[str, Any]:
        """
        Remove the persistent volume for a specific workflow.

        Use this to clean up storage after a workflow completes and you no longer
        need its state. This is permanent - all data will be lost!

        Args:
            workflow_id: The workflow ID (container_name) whose volume should be deleted.

        Returns:
            Dict with 'success' status and optional 'message'.

        Example:
            ```python
            # After workflow completes
            await sandbox.cleanup_workflow_volume("data-pipeline-123")
            # Volume 'workflow-data-pipeline-123' is permanently deleted
            ```
        """
        volume_name = f"workflow-{workflow_id}"
        loop = asyncio.get_event_loop()

        def _remove_volume():
            try:
                volume = self.client.volumes.get(volume_name)
                volume.remove()
                return {"success": True, "message": f"Volume '{volume_name}' removed successfully"}
            except docker.errors.NotFound:
                return {"success": False, "message": f"Volume '{volume_name}' not found"}
            except docker.errors.APIError as e:
                return {"success": False, "message": f"Failed to remove volume '{volume_name}': {str(e)}"}

        return await loop.run_in_executor(self.executor, _remove_volume)  # type: ignore[arg-type]

    async def list_workflow_volumes(self) -> List[Dict[str, Any]]:
        """
        List all workflow volumes managed by this sandbox.

        Returns:
            List of dicts containing volume information (name, driver, mountpoint, etc.).

        Example:
            ```python
            volumes = await sandbox.list_workflow_volumes()
            for vol in volumes:
                print(f"Workflow: {vol['workflow_id']}, Size: {vol.get('size', 'unknown')}")
            ```
        """
        loop = asyncio.get_event_loop()

        def _list_volumes():
            # Get all volumes starting with 'workflow-'
            all_volumes = self.client.volumes.list()
            workflow_volumes = []

            for volume in all_volumes:
                if volume.name.startswith('workflow-'):
                    workflow_id = volume.name.replace('workflow-', '', 1)
                    workflow_volumes.append({
                        'workflow_id': workflow_id,
                        'volume_name': volume.name,
                        'driver': volume.attrs.get('Driver'),
                        'mountpoint': volume.attrs.get('Mountpoint'),
                        'created': volume.attrs.get('CreatedAt'),
                    })

            return workflow_volumes

        return await loop.run_in_executor(self.executor, _list_volumes)  # type: ignore[arg-type]

    async def cleanup_containers(self) -> Dict[str, Any]:
        """
        Cleanup all resources.

        Stop and remove all managed containers. Note: This does NOT delete volumes.
        Use cleanup_workflow_volume() to remove persistent storage.
        """
        all_containers = await self.get_all_containers()
        for container_id in all_containers.keys():
            try:
                await self.stop_container(SandboxBaseArgs(container_id=container_id))
            except Exception as e:
                print(f"Error stopping container {container_id[:12]}: {e}")
        self.executor.shutdown(wait=True)
        return {"success": True}


class DurablePersistentContainerSandbox(PersistentContainerSandbox):
    """
    Temporal-compatible version of PersistentContainerSandbox.

    Wraps all PersistentContainerSandbox methods as Temporal activities,
    enabling container operations to be executed as part of durable workflows.
    Each method is decorated with @activity.defn for Temporal registration.

    All methods have identical signatures and behavior to the parent class,
    but are registered as Temporal activities for workflow orchestration.

    Example:
        ```python
        sandbox = DurablePersistentContainerSandbox()
        worker = Worker(
            client,
            task_queue='my-queue',
            workflows=[MyWorkflow],
            activities=sandbox.activities()
        )
        await worker.run()
        ```
    """

    def activities(self):
        """Return list of activity methods for the Temporal worker"""
        return [
            self.start_container,
            self.stop_container,
            self.restart_container,
            self.get_container_info,
            self.get_all_containers,
            self.cleanup_containers,
            self.get_python_state,
            self.read_state_variable,
            self.clear_python_state,
            self.list_state_variables,
            self.execute_python,
            self.execute_bash,
            self.install_additional_packages,
            self.write_file,
            self.read_file,
            self.list_files,
        ]

    @activity.defn
    async def start_container(self, input_model: StartContainerArgs) -> str:
        """
        Start a new persistent Docker container with specified packages.

        Creates and launches a new Docker container with the sandbox image,
        installs requested Python and system packages, and initializes the
        persistent state storage for variable persistence across executions.

        Args:
            input_model: Container configuration including python_packages and system_packages lists.

        Returns:
            str: Unique container ID for subsequent operations.
        """
        return await super().start_container(input_model)

    @activity.defn
    async def stop_container(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        Stop and remove a running container.

        Gracefully stops the specified container (5 second timeout) and removes
        it from the Docker host. All container data and state will be lost.

        Args:
            input_model: Container identifier with container_id field.

        Returns:
            Dict[str, Any]: Success status with 'success': True on completion.
        """
        return await super().stop_container(input_model)

    @activity.defn
    async def restart_container(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        Restart a running container.

        Performs a container restart which stops and starts the container process.
        Persisted state is preserved across restarts.

        Args:
            input_model: Container identifier with container_id field.

        Returns:
            Dict[str, Any]: Success status with 'success': True on completion.
        """
        return await super().restart_container(input_model)

    @activity.defn
    async def cleanup_containers(self) -> Dict[str, Any]:
        """
        Stop and remove all managed containers.

        Performs cleanup of all containers managed by this sandbox instance.
        Useful for cleanup at the end of workflows or on shutdown.

        Returns:
            Dict[str, Any]: Success status with 'success': True on completion.
        """
        return await super().cleanup_containers()

    @activity.defn
    async def get_all_containers(self) -> Dict[str, Any]:
        """
        Get information about all managed containers.

        Returns status and metadata for all containers currently managed
        by this sandbox instance.

        Returns:
            Dict[str, Any]: Dictionary mapping container IDs to their info.
        """
        return await super().get_all_containers()

    @activity.defn
    async def get_container_info(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        Get detailed information about a specific container.

        Returns container status, ID, image name, and other metadata.

        Args:
            input_model: Container identifier with container_id field.

        Returns:
            Dict[str, Any]: Container info including 'running', 'id', 'short_id', 'status', 'image', 'name'.
        """
        return await super().get_container_info(input_model)

    @activity.defn
    async def list_files(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        List files in the /output directory with absolute paths.

        Returns a list of absolute file paths from the container's /output directory.
        The path parameter in input_model is ignored - always lists from /output.

        Args:
            input_model: Contains container_id. The path field is not used.

        Returns:
            Dict[str, Any]: Result with 'success', 'files' (list of absolute paths), and 'error' fields.
        """
        return await super().list_files(input_model)

    @activity.defn
    async def read_file(self, input_model: ReadOperationsArgs) -> Dict[str, Any]:
        """
        Read the contents of a file from the container.

        Reads and returns the complete contents of the specified file.

        Args:
            input_model: Contains container_id and path (file path to read).

        Returns:
            Dict[str, Any]: Result with 'success', 'content' (file contents), and 'error' fields.
        """
        return await super().read_file(input_model)

    @activity.defn
    async def write_file(self, input_model: WriteFileArgs) -> Dict[str, Any]:
        """
        Write content to a file in the container.

        Creates or overwrites a file with the specified content.

        Args:
            input_model: Contains container_id, path (file path), and content (string content to write).

        Returns:
            Dict[str, Any]: Success status with 'success': True on completion, 'error' on failure.
        """
        return await super().write_file(input_model)

    @activity.defn
    async def install_additional_packages(self, input_model: InstallAdditionalPackagesArgs) -> Dict[str, Any]:
        """
        Install additional packages at runtime in the container.

        Installs Python packages via uv and system packages via apt-get.
        Useful for adding dependencies after container creation.

        Args:
            input_model: Contains container_id, python_packages (list), and system_packages (list).

        Returns:
            Dict[str, Any]: Success status with 'success': True on completion, 'error' on failure.
        """
        return await super().install_additional_packages(input_model)

    @activity.defn
    async def execute_bash(self, input_model: ExecuteBashArgs) -> Dict[str, Any]:
        """
        Execute bash commands in the container.

        Runs arbitrary bash commands with access to the container filesystem
        and environment. Commands execute in isolated container environment.

        Args:
            input_model: Contains container_id and script (bash commands to execute).

        Returns:
            Dict[str, Any]: Result with 'success', 'output' (stdout), 'error' (stderr), and 'exit_code'.
        """
        return await super().execute_bash(input_model)

    @activity.defn
    async def read_state_variable(self, input_model: ReadVariableInStateArgs) -> Dict[str, Any]:
        """
        Read a specific variable from the persistent Python state.

        Retrieves the value of a named variable from the container's persisted
        state storage. Variables are stored via pickle between executions.

        Args:
            input_model: Contains container_id and variable_name (name of variable to read).

        Returns:
            Dict[str, Any]: Result with 'success' and variable data, or 'error' on failure.
        """
        return await super().read_state_variable(input_model)

    @activity.defn
    async def list_state_variables(self, input_model: SandboxBaseArgs) -> Dict[str, str]:
        """
        List all variables in the persistent Python state with their types.

        Returns a dictionary mapping variable names to their Python type names
        for all variables currently stored in the container's persistent state.

        Args:
            input_model: Container identifier with container_id field.

        Returns:
            Dict[str, str]: Dictionary mapping variable names to type names (e.g., {'x': 'int', 'data': 'list'}).
        """
        return await super().list_state_variables(input_model)

    @activity.defn
    async def clear_python_state(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        Clear all variables from the persistent Python state.

        Removes all stored variables from the container's persistent state,
        resetting it to an empty state. Container continues running.

        Args:
            input_model: Container identifier with container_id field.

        Returns:
            Dict[str, Any]: Result with 'success', 'output', and 'error' fields.
        """
        return await super().clear_python_state(input_model)

    @activity.defn
    async def get_python_state(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """
        Get the complete persistent Python state with types and values.

        Retrieves all variables from the container's persistent state storage.
        Returns a dictionary mapping variable names to objects containing both
        the variable's type and value.

        Args:
            input_model: Container identifier with container_id field.

        Returns:
            Dict[str, Any]: Dictionary mapping variable names to objects with 'type' and 'value' fields.
                Example: {"x": {"type": "int", "value": 42}, "data": {"type": "list", "value": [1, 2, 3]}}
        """
        return await super().get_python_state(input_model)

    @activity.defn
    async def execute_python(self, input_model: ExecutePythonArgs) -> Dict[str, Any]:
        """
        Execute Python code in the container with persistent state.

        Runs Python code with automatic state persistence. Variables created
        or modified in the code are saved and available in subsequent executions.
        Optionally inject variables into the execution environment.

        Args:
            input_model: Contains container_id, code (Python code string), persist_state (bool), and variables (dict).

        Returns:
            Dict[str, Any]: Result with 'success', 'output' (stdout), 'error' (stderr), and 'exit_code'.
        """
        return await super().execute_python(input_model)


class StatelessPersistentSandbox:
    """
    Serverless sandbox adapter for instrumenting PydanticAI agents.

    Converts DurablePersistentContainerSandbox activities into PydanticAI
    agent tools. Each activity becomes a tool that spawns a child workflow
    for execution, enabling stateless agent operations while delegating
    container management to Temporal workflows.

    This approach allows agents to use sandbox capabilities without managing
    container state directly - all state is managed by the parent workflow.

    Example:
        ```python
        # In your agent workflow:
        agent = Agent('gemini-2.5-pro')
        sandbox = StatelessPersistentSandbox()

        # Instrument agent with sandbox tools (except blacklisted ones)
        agent = await sandbox.instrument_agent(
            agent,
            blacklist=['start_container', 'stop_container']
        )

        # Agent can now call execute_python, execute_bash, etc. as tools
        # Each tool call spawns a child SandboxWorkflow for execution
        ```
    """
    from typing import Type, Dict, Any, Optional
    from pydantic import BaseModel

    @staticmethod
    def __extract_activities(
            sandbox_class: Type[DurablePersistentContainerSandbox] = DurablePersistentContainerSandbox,
            blacklist: Optional[Sequence[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract activity names, their input/output types, and descriptions from docstrings.
        """
        blacklist = blacklist or set()
        activities = {}
        excluded_params = {'self', 'cls', 'return'}

        for name, method in inspect.getmembers(sandbox_class, predicate=inspect.isfunction):
            if name in blacklist or not hasattr(method, '__temporal_activity_definition'):
                continue

            try:
                type_hints = get_type_hints(method)
            except Exception:
                type_hints = getattr(method, '__annotations__', {})

            return_type = type_hints.get('return', type(None))
            sig = inspect.signature(method)

            # Find the BaseModel input type (if any)
            input_type: Optional[Type[BaseModel]] = None

            for param_name, param in sig.parameters.items():
                if param_name in excluded_params:
                    continue

                param_type = type_hints.get(param_name, Any)

                try:
                    if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                        input_type = param_type
                        break  # Assume only one BaseModel parameter
                except TypeError:
                    pass

            # Extract description from docstring (first line)
            description = None
            if method.__doc__:
                # Get the first non-empty line from the docstring
                lines = [line.strip() for line in method.__doc__.strip().split('\n')]
                for line in lines:
                    if line:
                        description = line
                        break

            activities[name] = {
                'input_type': input_type,
                'return_type': return_type,
                'description': description,
            }

        return activities

    @staticmethod
    def __create_tool(
            activity_name: str,
            return_type: Type[Any],
            input_type: Optional[Type[BaseModel]] = None,
            description: Optional[str] = None):

        if input_type is None:
            async def tool_func(ctx: RunContext[None]):
                child_workflow_id = f"{activity.info().workflow_id}-{activity_name}-{activity.info().activity_id}"
                return await activity.client().execute_workflow(
                    id=child_workflow_id,
                    workflow='SandboxWorkflow',
                    task_queue=activity.info().task_queue,
                    result_type=return_type,
                    id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
                    arg=SandboxInputTask(task_name=SandboxTaskTypes(activity_name))
                )

            params = [
                inspect.Parameter('ctx', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContext[None])
            ]
            annotations = {
                'ctx': RunContext[None],
                'return': return_type
            }
        else:
            # No type hint here - we set it manually via annotations
            async def tool_func(ctx: RunContext[None], input_model: input_type):

                if isinstance(input_model, dict):
                    activity_args_input = SandboxTaskArgsAdapter.validate_python(input_model)
                else:
                    activity_args_input = input_model

                child_workflow_id = f"{activity.info().workflow_id}-{activity_name}-{activity.info().activity_id}"
                return await activity.client().execute_workflow(
                    id=child_workflow_id,
                    workflow='SandboxWorkflow',
                    task_queue=activity.info().task_queue,
                    result_type=return_type,
                    id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
                    arg=SandboxInputTask(task_name=SandboxTaskTypes(activity_name), task_args=activity_args_input)
                )

            params = [
                inspect.Parameter('ctx', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContext[None]),
                inspect.Parameter('input_model', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=input_type)
            ]
            annotations = {
                'ctx': RunContext[None],
                'input_model': input_type,
                'return': return_type
            }

        tool_func.__name__ = activity_name
        tool_func.__qualname__ = activity_name
        tool_func.__annotations__ = annotations
        tool_func.__signature__ = inspect.Signature(parameters=params, return_annotation=return_type)

        # Set the docstring from the description
        if description:
            tool_func.__doc__ = description

        return tool_func

    async def instrument_agent(
            self,
            agent: Agent,
            blacklist: Sequence[str] = None
    ):
        """
        Instrument a PydanticAI agent with all sandbox activities as tools.

        Args:
            agent: PydanticAI Agent to instrument
            blacklist: List of activity names to exclude

        Example:
            agent = Agent('openai:gpt-4')
            instrument_agent(agent, blacklist=['cleanup_containers'])
        """
        activities = self.__extract_activities(blacklist=blacklist)

        for activity_name, metadata in activities.items():
            tool_func = self.__create_tool(
                activity_name=activity_name,
                input_type=metadata['input_type'],
                return_type=metadata['return_type'],
                description=metadata.get('description')
            )
            agent.tool(name=activity_name, strict=True)(tool_func)

        return agent
