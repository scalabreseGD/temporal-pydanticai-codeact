import asyncio
import inspect
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, List, Type, get_type_hints, Optional

import docker
from docker.errors import ImageNotFound
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from temporalio import activity
from temporalio.client import WorkflowExecutionStatus, WorkflowHandle
from temporalio.exceptions import ApplicationError
from temporalio.workflow import ChildWorkflowHandle

from datamodels.sandbox import StartContainerArgs, SandboxBaseArgs, ReadVariableInStateArgs, ExecutePythonArgs, \
    ExecuteBashArgs, WriteFileArgs, ReadOperationsArgs, SandboxInputTask, SandboxTaskTypes
from .sandbox import SANDBOX_DIR, DOCKERFILE_PATH


class PersistentContainerSandbox:
    def __init__(
            self,
            dockerfile_path: str = None,
            image_name: str = "python-uv-sandbox",
            image_tag: str = "latest",
            memory_limit: str = "512m",
            cpu_limit: float = 1.0,
            enable_network: bool = True
    ):
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

        # Dictionary to store containers: {container_id: container_object}
        self.containers: Dict[str, Any] = {}

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=10)

        self._ensure_image()

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

    async def start_container(
            self,
            input_model: StartContainerArgs
    ) -> str:
        """Start a new persistent container and install packages"""
        loop = asyncio.get_event_loop()

        container = await loop.run_in_executor(  # type: ignore[arg-type]
            self.executor,
            lambda: self.client.containers.run(
                self.full_image_name,
                command="tail -f /dev/null",
                detach=True,
                mem_limit=self.memory_limit,
                nano_cpus=int(self.cpu_limit * 1e9),
                network_disabled=not self.enable_network,
                remove=False,
                stdin_open=True,
                tty=True
            )
        )

        container_id = container.id
        self.containers[container_id] = container

        print(f"Container started: {container_id[:12]}")

        await self._install_packages(
            container_id,
            input_model.python_packages or [],
            input_model.system_packages or []
        )

        await self._initialize_state(container_id)

        return container_id

    async def _initialize_state(self, container_id: str):
        """Initialize persistent state storage in the container"""
        container = self.containers.get(container_id)
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
        container = self.containers.get(container_id)
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

    async def execute_python(
            self,
            input_model: ExecutePythonArgs
    ):
        """Execute Python code in the specified container with persistent state"""
        container = self.containers.get(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        # Load sandbox script templates from the packaged sandbox directory
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

        full_script = "\n".join(script_parts)

        loop = asyncio.get_event_loop()

        def _exec():
            exit_code, output = container.exec_run(
                cmd=["python", "-c", full_script],
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

    async def get_python_state(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        """Get the current persisted Python state from a container"""
        container = self.containers.get(input_model.container_id)
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
                import ast
                return ast.literal_eval(result["output"].strip())
            except:
                return {}
        return {}

    async def clear_python_state(self, input_model: SandboxBaseArgs):
        """Clear the persisted Python state in a container"""
        container = self.containers.get(input_model.container_id)
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
        container = self.containers.get(input_model.container_id)
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
        container = self.containers.get(input_model.container_id)
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
    ):
        """Execute bash commands in the specified container"""
        container = self.containers.get(input_model.container_id)
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
            input_model: StartContainerArgs
    ):
        """Install additional Python packages at runtime using uv"""
        try:
            await self._install_packages(container_id=input_model.container_id,
                                         python_packages=input_model.python_packages,
                                         system_packages=input_model.system_packages)
            return {"success": True}
        except ApplicationError as e:
            return {"success": False, "error": e.message}

    async def write_file(self, input_model: WriteFileArgs):
        """Write a file to the specified container"""
        container = self.containers.get(input_model.container_id)
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

    async def read_file(self, input_model: ReadOperationsArgs):
        """Read a file from the specified container"""
        container = self.containers.get(input_model.container_id)
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

    async def list_files(self, input_model: ReadOperationsArgs):
        """List files in container directory"""
        return await self.execute_bash(
            input_model=ExecuteBashArgs(container_id=input_model.container_id, script=f"ls -la {input_model.path}"))

    async def get_container_info(self, input_model: SandboxBaseArgs):
        """Get information about the specified container"""
        container = self.containers.get(input_model.container_id)
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

    async def get_all_containers(self):
        """Get information about all managed containers"""
        return {
            container_id: await self.get_container_info(SandboxBaseArgs(container_id=container_id))
            for container_id in self.containers.keys()
        }

    async def stop_container(self, input_model: SandboxBaseArgs):
        """Stop and remove the specified container"""
        container = self.containers.get(input_model.container_id)
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
        del self.containers[input_model.container_id]
        return {"success": True}

    async def restart_container(self, input_model: SandboxBaseArgs):
        """Restart the specified container"""
        container = self.containers.get(input_model.container_id)
        if not container:
            raise ValueError(f"Container {input_model.container_id} not found")

        loop = asyncio.get_event_loop()

        def _restart():
            container.restart()
            print(f"Container {input_model.container_id[:12]} restarted")

        await loop.run_in_executor(self.executor, _restart)  # type: ignore[arg-type]
        return {"success": True}

    async def cleanup_containers(self):
        """
        Cleanup all resources
        Stop and remove all managed containers
        """
        container_ids = list(self.containers.keys())
        for container_id in container_ids:
            try:
                await self.stop_container(SandboxBaseArgs(container_id=container_id))
            except Exception as e:
                print(f"Error stopping container {container_id[:12]}: {e}")
        self.executor.shutdown(wait=True)
        return {"success": True}


class DurablePersistentContainerSandbox(PersistentContainerSandbox):

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
        return await super().start_container(input_model)

    @activity.defn
    async def stop_container(self, input_model: SandboxBaseArgs):
        return await super().stop_container(input_model)

    @activity.defn
    async def restart_container(self, input_model: SandboxBaseArgs):
        return await super().restart_container(input_model)

    @activity.defn
    async def cleanup_containers(self):
        return await super().cleanup_containers()

    @activity.defn
    async def get_all_containers(self):
        return await super().get_all_containers()

    @activity.defn
    async def get_container_info(self, input_model: SandboxBaseArgs):
        return await super().get_container_info(input_model)

    @activity.defn
    async def list_files(self, input_model: ReadOperationsArgs):
        return await super().list_files(input_model)

    @activity.defn
    async def read_file(self, input_model: ReadOperationsArgs):
        return await super().read_file(input_model)

    @activity.defn
    async def write_file(self, input_model: WriteFileArgs):
        return await super().write_file(input_model)

    @activity.defn
    async def install_additional_packages(self, input_model: StartContainerArgs):
        return await super().install_additional_packages(input_model)

    @activity.defn
    async def execute_bash(self, input_model: ExecuteBashArgs):
        return await super().execute_bash(input_model)

    @activity.defn
    async def read_state_variable(self, input_model: ReadVariableInStateArgs) -> Dict[str, Any]:
        return await super().read_state_variable(input_model)

    @activity.defn
    async def list_state_variables(self, input_model: SandboxBaseArgs) -> Dict[str, str]:
        return await super().list_state_variables(input_model)

    @activity.defn
    async def clear_python_state(self, input_model: SandboxBaseArgs):
        return await super().clear_python_state(input_model)

    @activity.defn
    async def get_python_state(self, input_model: SandboxBaseArgs) -> Dict[str, Any]:
        return await super().get_python_state(input_model)

    @activity.defn
    async def execute_python(self, input_model: ExecutePythonArgs):
        return await super().execute_python(input_model)


class StatelessPersistentSandbox:

    @staticmethod
    def __extract_activities(
            sandbox_class: Type[DurablePersistentContainerSandbox] = DurablePersistentContainerSandbox,
            blacklist: List[str] = None
    ) -> Dict[str, Dict]:
        """
        Extract activity names and their input signatures.

        Args:
            sandbox_class: The sandbox class to inspect
            blacklist: List of activity names to exclude

        Returns:
            Dict mapping activity_name to {'input_type': Type, 'signature': dict}
        """
        if blacklist is None:
            blacklist = []

        activities = {}

        for name, method in inspect.getmembers(sandbox_class, predicate=inspect.isfunction):
            if name in blacklist:
                continue

            if hasattr(method, '__temporal_activity_definition'):
                type_hints = get_type_hints(method)

                # Get input_model parameter type (skip 'self' and 'return')
                input_type = type_hints.get('input_model', None)

                activities[name] = {
                    'input_type': input_type,
                    'signature': {k: v for k, v in type_hints.items() if k not in ('self', 'return')}
                }

        return activities

    @staticmethod
    async def __create_tool(
            activity_name: str,
            input_type: Type[BaseModel] = None):
        """
        Create a PydanticAI tool that delegates to a Temporal workflow.

        Args:
            workflow_id: The ID of the temporal workflow
            activity_name: Name of the activity
            input_type: Pydantic model for input validation

        Returns:
            Async function suitable as a PydanticAI tool
        """
        if input_type is None:
            # No input parameters
            async def tool_func():
                workflow_id = await StatelessPersistentSandbox.get_workflow_id()
                if activity.in_activity():
                    await activity.client().start_workflow(
                        workflow='SandboxWorkflow',
                        id=workflow_id,
                        task_queue=activity.info().task_queue,
                        start_signal=activity_name,
                        run_timeout=timedelta(minutes=10),
                        start_signal_args=[],
                    )

            tool_func.__name__ = activity_name
            return tool_func

        # Has input parameters
        async def tool_func(**kwargs):
            input_model = input_type(**kwargs)

            if activity.in_activity():
                workflow_id = await StatelessPersistentSandbox.get_workflow_id()
                await activity.client().start_workflow(
                    workflow='SandboxWorkflow',
                    id=workflow_id,
                    task_queue=activity.info().task_queue,
                    start_signal=activity_name,
                    run_timeout=timedelta(hours=2),
                    start_signal_args=[input_model],
                )

        tool_func.__name__ = activity_name

        # Add parameter annotations from input model
        if input_type:
            tool_func.__annotations__ = {
                **{field: field_info.annotation
                   for field, field_info in input_type.model_fields.items()},
                'return': None
            }

        return tool_func

    async def instrument_agent_old(
            self,
            agent: Agent,
            blacklist: List[str] = None
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
            tool_func = await self.__create_tool(
                activity_name=activity_name,
                input_type=metadata['input_type']
            )
            agent.tool(name=activity_name, strict=True)(tool_func)

        return agent

    @staticmethod
    async def __get_handle_if_wf_exists(workflow_id) -> WorkflowHandle | None:
        try:
            handle = activity.client().get_workflow_handle(workflow_id)
            desc = await handle.describe()
            if desc.status == WorkflowExecutionStatus.RUNNING:
                return handle
            else:
                return None
        except Exception:
            return None

    async def instrument_agent(self, agent: Agent):
        @agent.tool(name='execute_python', strict=True)
        async def execute_python(ctx: RunContext[None], input_model: ExecutePythonArgs):
            if activity.in_activity():
                workflow_id = ctx.deps.sandbox_workflow_id
                handle = await self.__get_handle_if_wf_exists(workflow_id)

                return await StatelessPersistentSandbox.trigger_and_wait_result(
                    handle=handle,
                    sandbox_input=SandboxInputTask(
                        task_name=SandboxTaskTypes.EXECUTE_PYTHON,
                        task_args=input_model
                    ),
                )
            else:
                raise ApplicationError(message='No in activity context', non_retryable=True)

        return agent

    @staticmethod
    async def __wait_for_sandbox_workflow_result(handle: WorkflowHandle | ChildWorkflowHandle):
        res = None
        while res is None:
            res = await handle.query('task_output', result_type=Optional[Any])
            if res is not None:
                break
            else:
                await asyncio.sleep(5)
        return res

    @staticmethod
    async def trigger_and_wait_result(handle: WorkflowHandle | ChildWorkflowHandle,
                                      sandbox_input: SandboxInputTask):
        await handle.signal(signal='submit_task',
                            arg=sandbox_input)
        return await StatelessPersistentSandbox.__wait_for_sandbox_workflow_result(handle=handle)
