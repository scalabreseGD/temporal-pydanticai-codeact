from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.base.code_act_agent import CodeActAgent


class SimpleAgent(CodeActAgent):
    agent_name = 'simple_agent'
