"""
Code execution agent with Docker sandbox integration.

This module provides the CodeActAgent class, which extends BaseAgent with
code execution capabilities in isolated Docker containers. It integrates with
StatelessPersistentSandbox to provide agents with tools for executing Python
and bash code safely.
"""
import asyncio
from datetime import timedelta

from pydantic_ai import RunContext
from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.agent import EventStreamHandler, NoneType, Instructions
from pydantic_ai.durable_exec.temporal import TemporalAgent
from pydantic_ai.output import OutputSpec, OutputDataT
from temporalio import workflow

from datamodels.sandbox import SandboxBaseArgs

with workflow.unsafe.imports_passed_through():
    from agents.base.base_agent import BaseAgent
    from datamodels.agent_builder import AgentBuilder
    from datamodels.codeact import CodeActAgentDeps
    from docker_sandbox.container_sandbox import StatelessPersistentSandbox


class CodeActAgent(BaseAgent):
    """
    Agent with code execution capabilities in Docker sandbox environments.

    This agent extends BaseAgent to provide code execution tools via Docker
    containers. It uses StatelessPersistentSandbox to instrument the agent
    with sandbox operations (execute_python, execute_bash, file operations, etc.)
    while blacklisting container lifecycle operations.

    The agent supports dynamic instruction rendering via Jinja2 templates,
    allowing instructions to be customized based on runtime dependencies.

    Attributes:
        agent_name: Fixed identifier 'codeact_agent' for this agent type.
        deps_type: CodeActAgentDeps - requires container_id and package lists.
        output_type: str - agent returns string output.
    """
    agent_name = 'codeact_agent'
    deps_type = CodeActAgentDeps
    output_type = str

    def instructions(self) -> Instructions[AgentDepsT]:
        """
        Generate dynamic instructions using Jinja2 template rendering.

        Renders the agent's instruction template with runtime dependencies
        as context variables. Uses Temporal activity execution when running
        within a workflow, or direct function call otherwise.

        Returns:
            Instructions[AgentDepsT]: Callable that returns rendered instructions
                based on current run context and dependencies.

        Note:
            The instruction template can reference dependency attributes via
            Jinja2 syntax (e.g., {{ container_id }}, {{ python_packages }}).
        """

        async def _instructions_cb(context: RunContext[AgentDepsT]):
            return await CodeActAgent._render_instructions(self._prompts.instructions or '', context.deps)

        return _instructions_cb

    @staticmethod
    async def _render_instructions(base_instruction: str, deps: CodeActAgentDeps):
        model_input = SandboxBaseArgs(container_id=deps.container_id)
        # we always fetch the latest variable lists from the code sandbox
        if workflow.in_workflow():
            prompt_activities = ['list_state_variables', 'list_files']
            variables, files = await asyncio.gather(*[workflow.execute_activity(
                activity=prompt_activity,
                arg=SandboxBaseArgs(container_id=deps.container_id),
                start_to_close_timeout=timedelta(seconds=30),
            ) for prompt_activity in prompt_activities])

        else:
            from docker_sandbox.container_sandbox import PersistentContainerSandbox
            pcs = PersistentContainerSandbox()
            variables, files = await asyncio.gather(*[
                pcs.list_state_variables(input_model=model_input),
                pcs.list_files(input_model=model_input),
            ])

        deps_args = deps.model_dump()
        deps_args['sandbox_variable_names'] = variables
        deps_args['sandbox_files'] = files["files"]

        if workflow.in_workflow():
            rendered_prompt = await workflow.execute_activity(
                activity='render_jinja',
                args=[base_instruction, deps_args],
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            from activities.common import render_jinja
            rendered_prompt = await render_jinja(base_instruction, deps_args)
        return rendered_prompt

    async def _build_agent(self, agent_builder: AgentBuilder,
                           event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                           deps_type: type[AgentDepsT] = NoneType,
                           output_type: OutputSpec[OutputDataT] = str,
                           **kwargs):
        """
        Build a code-execution-enabled agent with sandbox tools.

        Creates the base agent via BaseAgent._build_agent, then instruments it
        with Docker sandbox tools. Container lifecycle operations are blacklisted
        since container management is handled by the workflow layer.

        Args:
            agent_builder: Configuration for building the agent (prompts, model, etc.).
            event_stream_handler: Optional handler for streaming agent events.
            deps_type: Type of dependencies (unused, kept for signature compatibility).
            output_type: Type of agent output (unused, kept for signature compatibility).
            **kwargs: Additional arguments passed to base agent builder.

        Returns:
            Agent: PydanticAI agent instrumented with sandbox execution tools.

        Note:
            Blacklisted tools (container lifecycle operations) are not exposed
            to the agent as these are managed by CodeActAgentWorkflow.
        """
        base_agent = await super()._build_agent(agent_builder, event_stream_handler, **kwargs)
        serverless_sandbox = StatelessPersistentSandbox()
        instrumented_agent = await serverless_sandbox.instrument_agent(agent=base_agent,
                                                                       blacklist=[
                                                                           'start_container',
                                                                           'stop_container',
                                                                           'restart_container',
                                                                           'get_container_info',
                                                                           'get_all_containers',
                                                                           'cleanup_containers'
                                                                       ]
                                                                       )
        return instrumented_agent

    @classmethod
    async def from_agent_confs(cls, agent_builder: AgentBuilder,
                               event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                               **kwargs) -> TemporalAgent:
        """
        Factory method to create a TemporalAgent from configuration.

        Convenience method that builds a CodeActAgent and wraps it for
        Temporal workflow execution. Ensures deps_type is set to CodeActAgentDeps.

        Args:
            agent_builder: Configuration containing prompts, model settings, and
                Temporal wrapper configuration.
            event_stream_handler: Optional handler for streaming agent events.
            **kwargs: Additional arguments (e.g., API keys, environment variables).

        Returns:
            TemporalAgent: Agent wrapped for Temporal workflow execution with
                sandbox tools registered as Temporal activities.
        """
        return await super().from_agent_confs(agent_builder=agent_builder,
                                              event_stream_handler=event_stream_handler,
                                              deps_type=CodeActAgentDeps,
                                              **kwargs)
