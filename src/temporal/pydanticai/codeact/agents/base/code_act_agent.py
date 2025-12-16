"""
Code execution agent with Docker sandbox integration and MCP server support.

This module provides the CodeActAgent class, which extends BaseAgent with
code execution capabilities in isolated Docker containers. It integrates with
StatelessPersistentSandbox to provide agents with tools for executing Python
and bash code safely.

The agent supports Model Context Protocol (MCP) servers, enabling seamless
integration with external tools and services. MCP tools are automatically
discovered, serialized, and made available to the agent both as callable
functions and in the instruction prompt.
"""
import asyncio
from datetime import timedelta
from typing import List, Optional

from pydantic_ai import RunContext, Tool
from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.agent import EventStreamHandler, Instructions, Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal.pydanticai.codeact.datamodels.mcp_tools import serialize_mcp_servers
    from temporal.pydanticai.codeact.datamodels.sandbox import SandboxBaseArgs
    from temporal.pydanticai.codeact.agents.base.base_agent import BaseAgent
    from temporal.pydanticai.codeact.datamodels.agent_builder import AgentBuilder
    from temporal.pydanticai.codeact.datamodels.codeact import CodeActAgentDeps
    from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import StatelessPersistentSandbox
    from temporal.pydanticai.codeact.utils.function_serializer import serialize_functions


class CodeActAgent(BaseAgent):
    """
    Agent with code execution capabilities in Docker sandbox environments.

    This agent extends BaseAgent to provide code execution tools via Docker
    containers. It uses StatelessPersistentSandbox to instrument the agent
    with sandbox operations (execute_python, execute_bash, file operations, etc.)
    while blacklisting container lifecycle operations.

    The agent supports dynamic instruction rendering via Jinja2 templates,
    allowing instructions to be customized based on runtime dependencies.

    MCP Server Integration:
        The agent automatically integrates Model Context Protocol (MCP) servers
        defined in _get_mcp_toolsets(). MCP tools are:
        1. Serialized and passed to the Docker sandbox for code execution
        2. Extracted as Python function signatures and included in instructions
        3. Made available as callable tools within sandbox Python executions

        This enables agents to use external tools (time, fetch, filesystem, etc.)
        seamlessly in generated code.

    Attributes:
        agent_name: Fixed identifier 'codeact_agent' for this agent type.
        deps_type: CodeActAgentDeps - requires container_id and package lists.
        output_type: str - agent returns string output.

    Example:
        >>> class MyAgent(CodeActAgent):
        ...     @staticmethod
        ...     async def _get_mcp_toolsets(**kwargs):
        ...         return {
        ...             'time': WrapperToolset(MCPServerStdio("uvx", ["mcp-server-time"]))
        ...         }
        >>> # Agent can now use time tools in sandbox code execution
    """
    agent_name = 'codeact_agent'
    deps_type = CodeActAgentDeps
    output_type = str

    def instructions(self, **kwargs) -> Instructions[AgentDepsT]:
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
            return await CodeActAgent._render_instructions(self._prompts.instructions or '', context.deps,
                                                           kwargs.get('tools_as_func', None))

        return _instructions_cb

    @staticmethod
    async def _render_instructions(base_instruction: str, deps: CodeActAgentDeps,
                                   tools_as_func: Optional[List[str]] = None):
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
            from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox
            pcs = PersistentContainerSandbox()
            variables, files = await asyncio.gather(*[
                pcs.list_state_variables(input_model=model_input),
                pcs.list_files(input_model=model_input),
            ])

        deps_args = deps.model_dump()
        deps_args['sandbox_variable_names'] = variables
        deps_args['sandbox_files'] = files["files"]
        deps_args['tools_as_func'] = tools_as_func

        if workflow.in_workflow():
            rendered_prompt = await workflow.execute_activity(
                activity='render_jinja',
                args=[base_instruction, deps_args],
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            from temporal.pydanticai.codeact.activities.common import render_jinja
            rendered_prompt = await render_jinja(base_instruction, deps_args)
        return rendered_prompt

    async def _build_agent(self, agent_builder: AgentBuilder,
                           event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                           tools: Tool[AgentDepsT] | None = None,
                           **kwargs):
        """
        Build a code-execution-enabled agent with sandbox tools and MCP integration.

        Creates the base agent and instruments it with Docker sandbox tools.
        Container lifecycle operations are blacklisted since container management
        is handled by the workflow layer.

        MCP Server Processing:
            1. Retrieves MCP toolsets from _get_mcp_toolsets()
            2. Serializes MCP server configurations for container execution
            3. Extracts tool schemas as Python function signatures
            4. Passes function signatures to instruction renderer
            5. Provides serialized servers to sandbox instrumentation

        Args:
            agent_builder: Configuration for building the agent (prompts, model, etc.).
            event_stream_handler: Optional handler for streaming agent events.
            **kwargs: Additional arguments passed to base agent builder and MCP setup.

        Returns:
            Agent: PydanticAI agent instrumented with sandbox execution tools
                and MCP server configurations.

        Note:
            Blacklisted tools (container lifecycle operations) are not exposed
            to the agent as these are managed by CodeActAgentWorkflow.
        """

        # Process MCP toolsets
        toolsets = await self._get_mcp_toolsets(**kwargs)
        wrapped_toolsets = [w.wrapped for w in toolsets.values()]
        serialized_servers = serialize_mcp_servers(wrapped_toolsets)
        if toolsets:
            if workflow.in_workflow():
                tools_as_func = await workflow.execute_activity(activity='extract_mcp_tools_as_functions',
                                                                arg=serialized_servers,
                                                                start_to_close_timeout=timedelta(minutes=10),
                                                                )
            else:
                from temporal.pydanticai.codeact.activities.mcp_functions import extract_mcp_tools_as_functions
                tools_as_func = await extract_mcp_tools_as_functions(serialized_servers)
        else:
            tools_as_func = None

        # Process custom functions
        custom_funcs = await self._get_custom_functions(**kwargs)
        if custom_funcs:
            custom_functions_config = serialize_functions(custom_funcs)
            custom_functions_signatures = custom_functions_config.get_all_signatures()
        else:
            custom_functions_config = None
            custom_functions_signatures = None

        if custom_functions_signatures:
            tools_as_func.extend(custom_functions_signatures)

        serverless_sandbox = StatelessPersistentSandbox()
        code_sandbox_tools = await serverless_sandbox.code_sandbox_tools(
            blacklist=[
                'start_container',
                'stop_container',
                'restart_container',
                'get_container_info',
                'get_all_containers',
                'cleanup_containers'
            ],
            mcp_servers=serialized_servers,
            custom_functions=custom_functions_config
        )
        if not tools:
            tools = []

        tools.extend(code_sandbox_tools)

        base_agent = Agent(name=self.agent_name,
                           model=await self._get_llm_model(agent_builder.model_configs),
                           tools=tools,
                           system_prompt=self.system_prompt,
                           instructions=self.instructions(
                               tools_as_func=tools_as_func,
                               custom_functions_signatures=custom_functions_signatures
                           ),
                           event_stream_handler=event_stream_handler,
                           deps_type=self.deps_type,
                           output_type=self.output_type
                           )
        return base_agent

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
