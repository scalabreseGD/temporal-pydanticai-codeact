from typing import List, Optional

from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.agent import EventStreamHandler
from temporalio import workflow

from datamodels.agent_builder import AgentBuilder
from datamodels.prompts import AgentPrompts

with workflow.unsafe.imports_passed_through():
    from agents.base.base_agent import BaseAgent


class CodeActAgent(BaseAgent):
    agent_name = 'codeact_agent'

    def __init__(self,
                 prompts: AgentPrompts,
                 container_id: str = '_placeholder',
                 python_packages: Optional[List[str]] = None,
                 system_packages: Optional[List[str]] = None):
        super().__init__(prompts=prompts)
        self.python_packages = python_packages
        self.system_packages = system_packages
        self.container_id = container_id

    async def _build_agent(self, agent_builder: AgentBuilder,
                           event_stream_handler: EventStreamHandler[AgentDepsT] | None = None, **kwargs):
        base_agent = await super()._build_agent(agent_builder, event_stream_handler, **kwargs)
        # TODO add now the tools
        return base_agent
