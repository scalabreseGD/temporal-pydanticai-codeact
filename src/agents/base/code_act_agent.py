from pydantic_ai import RunContext
from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.agent import EventStreamHandler, NoneType, Instructions
from pydantic_ai.durable_exec.temporal import TemporalAgent
from pydantic_ai.output import OutputSpec, OutputDataT
from temporalio import workflow

from datamodels.agent_builder import AgentBuilder
from datamodels.sandbox import SandboxBaseArgs
from docker_sandbox.container_sandbox import StatelessPersistentSandbox

with workflow.unsafe.imports_passed_through():
    from agents.base.base_agent import BaseAgent


class CodeActAgent(BaseAgent):
    agent_name = 'codeact_agent'

    def instructions(self) -> Instructions[AgentDepsT]:
        async def _instructions_cb(context: RunContext[AgentDepsT]):
            original_instructions = self._prompts.instructions or ''
            original_instructions += f"\n Container Id must be: {context.deps.container_id}"
            return original_instructions

        return _instructions_cb

    async def _build_agent(self, agent_builder: AgentBuilder,
                           event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
                           deps_type: type[AgentDepsT] = NoneType, output_type: OutputSpec[OutputDataT] = str,
                           **kwargs):
        base_agent = await super()._build_agent(agent_builder, event_stream_handler, deps_type, output_type, **kwargs)
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
        return await super().from_agent_confs(agent_builder=agent_builder,
                                              event_stream_handler=event_stream_handler,
                                              deps_type=SandboxBaseArgs,
                                              **kwargs)
