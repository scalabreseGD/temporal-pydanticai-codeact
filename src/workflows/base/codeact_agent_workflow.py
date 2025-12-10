"""
Base workflow mixin for code-executing agents with sandbox management.

This module provides CodeActAgentWorkflow, a mixin class that adds sandbox
container lifecycle management to Temporal workflows. Workflows that include
code execution capabilities should inherit from this class.
"""
import asyncio

from pydantic_ai.durable_exec.temporal import TemporalAgent
from temporalio import workflow
from temporalio.common import RetryPolicy

from datamodels.agent_builder import AgentBuilder

with workflow.unsafe.imports_passed_through():
    from datamodels.sandbox import SandboxTaskTypes, StartContainerArgs, SandboxBaseArgs
    from datamodels.codeact import CodeActAgentOutput, CodeActAgentDeps
    from datamodels.prompts import AgentPrompts, Prompts
    from collections import deque
    from datetime import timedelta
    from typing import List, Optional, Any


class CodeActAgentWorkflow:
    """
    Mixin for managing sandbox container lifecycle in workflows.

    Provides methods for starting and stopping Docker sandbox containers
    as part of a workflow. Workflows that execute code should inherit from
    or compose with this class to manage container lifecycle.

    The container_id is stored as workflow state and made available to
    agents via CodeActAgentDeps.

    Attributes:
        container_id: ID of the currently running sandbox container.
            None if no container is active.

    Example:
        ```python
        @workflow.defn
        class MyCodeWorkflow(CodeActAgentWorkflow):
            @workflow.run
            async def run(self, task: str) -> str:
                # Start container with packages
                await self.start_sandbox_container(
                    python_packages=['numpy', 'pandas']
                )

                try:
                    # Use self.container_id in agent deps
                    result = await agent.run(
                        user_prompt=task,
                        deps=CodeActAgentDeps(container_id=self.container_id)
                    )
                    return result.output
                finally:
                    # Always cleanup
                    await self.stop_sandbox_container()
        ```
    """

    def __init__(self):
        self.container_id: str | None = None
        self.user_tasks: deque[str] = deque()
        self.chat_history = []

        self.is_running = True
        self.last_output: deque[CodeActAgentOutput | str] = deque()

    async def run(self) -> CodeActAgentOutput | str:
        workflow.logger.info(f"Starting container...")
        await self._start_sandbox_container(python_packages=["numpy", "pandas"])
        workflow.logger.info(f"Started container {self.container_id}")

        try:
            prompts = await self._get_prompts()
            configs = await self._get_configs()
            gemini_configs = configs['llm']['gemini']
            agent = await self._get_agent(agent_builder=AgentBuilder(prompts=prompts, model_configs=gemini_configs))

            while self.is_running:
                try:
                    await workflow.wait_condition(lambda: len(self.user_tasks) > 0 or not self.is_running,
                                                  timeout=timedelta(hours=1),
                                                  timeout_summary="Waiting for user input")
                    if not self.is_running:
                        await self._stop_sandbox_container()
                except asyncio.TimeoutError:
                    self.is_running = False
                    continue

                user_task = self.user_tasks.popleft()
                agent_output = await agent.run(
                    user_prompt=user_task,
                    deps=CodeActAgentDeps(container_id=self.container_id,
                                          python_packages=["numpy", "pandas"]),
                    output_type=CodeActAgentOutput,
                    message_history=self.chat_history,
                )
                self.chat_history.extend(agent_output.new_messages())
                self.last_output.append(agent_output.output)
        except Exception as ex:
            self.last_output.append(str(ex))
        finally:
            await self._stop_sandbox_container()
            workflow.logger.info(f"Stopping container {self.container_id}")
        return "Workflow completed"

    @workflow.signal
    async def send_user_task(self, user_task: str):
        """
        Signal handler to send user input to the workflow.

        Appends the prompt to the queue for processing by the agent.

        Args:
            user_task: The user's input message.
        """
        self.user_tasks.append(user_task)

    @workflow.signal
    async def stop_chat(self):
        """
        Signal handler to stop the workflow execution.

        Sets the is_running flag to False, causing the workflow to exit
        its main loop gracefully.
        """
        self.is_running = False

    @workflow.query
    def agent_output(self) -> Optional[CodeActAgentOutput | str]:
        """
        Query handler to retrieve the last agent output.

        Returns:
            Optional[str]: The last output from the agent, or None.
        """
        if self.last_output:
            return self.last_output.popleft()
        else:
            return None

    async def _get_agent(self, agent_builder: AgentBuilder) -> TemporalAgent:
        raise NotImplementedError("Implement this method in the subclass workflow")

    @staticmethod
    async def _get_configs():
        """
        Load and extract environment variables for the workflow.

        Retrieves configuration from the get_configs activity and
        extracts MCP and LLM configuration sections.

        Returns:
            Dict containing processed environment variables for the workflow.
        """
        configs = await workflow.execute_activity(
            activity='get_configs',
            start_to_close_timeout=timedelta(minutes=1),
            result_type=dict[str, Any],
        )
        return configs

    @staticmethod
    async def _get_prompts() -> dict[str, AgentPrompts]:
        """
        Load agent prompts from configuration.

        Executes the get_prompts activity to retrieve all agent prompts
        from the YAML configuration file.

        Returns:
            Dict[str, AgentPrompts]: All agent prompts and instructions.
        """
        prompts = await workflow.execute_activity(
            activity='get_prompts',
            start_to_close_timeout=timedelta(minutes=1),
            result_type=Prompts,
        )
        return prompts.agent_prompts

    async def _start_sandbox_container(self,
                                       python_packages: Optional[List[str]] = None,
                                       system_packages: Optional[List[str]] = None
                                       ):
        """
        Start a new sandbox container with specified packages.

        Executes the START_CONTAINER activity to create and initialize a new
        Docker container. Installs requested packages and initializes persistent
        state. Sets self.container_id to the new container's ID.

        The container is named using the workflow ID for easy tracking and
        management across workflow executions.

        Args:
            python_packages: Optional list of Python packages to install via uv.
            system_packages: Optional list of system packages to install via apt-get.

        Returns:
            None. Sets self.container_id as a side effect.

        Raises:
            ApplicationError: If container creation or package installation fails
                after 3 retry attempts.

        Note:
            Container creation has a 10-minute timeout with up to 3 retries.
            Package installation is part of container startup.
        """
        self.container_id = await workflow.execute_activity(
            activity=SandboxTaskTypes.START_CONTAINER,
            arg=StartContainerArgs(
                python_packages=python_packages,
                system_packages=system_packages,
                container_name=workflow.info().workflow_id
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                maximum_interval=timedelta(seconds=10),
            ),
            summary=f"Executing task {SandboxTaskTypes.START_CONTAINER.value}"
        )

    async def _stop_sandbox_container(self):
        """
        Stop and remove the current sandbox container.

        Executes the STOP_CONTAINER activity to stop and remove the container
        managed by this workflow. Clears self.container_id after successful stop.

        Returns:
            None. Clears self.container_id as a side effect.

        Raises:
            ValueError: If no container is currently running (container_id is None).
            ApplicationError: If container stop/removal fails after 3 retry attempts.

        Note:
            This should be called in a finally block to ensure cleanup even if
            the workflow fails. Has a 10-minute timeout with up to 3 retries.
        """
        await workflow.execute_activity(
            activity=SandboxTaskTypes.STOP_CONTAINER,
            arg=SandboxBaseArgs(container_id=self.container_id),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                maximum_interval=timedelta(seconds=10),
            ),
            summary=f"Executing {SandboxTaskTypes.STOP_CONTAINER.value} with {self.container_id}"
        )
        self.container_id = None
