"""
Default Temporal activity configurations for agent operations.

This module provides sensible default timeouts and retry policies for
Temporal activities used in agent workflows, including general activities,
model calls, and toolset executions.
"""

from datetime import timedelta

from pydantic_ai import WrapperToolset
from temporalio.common import RetryPolicy
from temporalio.workflow import ActivityConfig

DEFAULT_ACTIVITY_CONFIG = ActivityConfig(
    start_to_close_timeout=timedelta(minutes=3),
    retry_policy=RetryPolicy(
        maximum_attempts=50,
        maximum_interval=timedelta(minutes=1)
    )
)
"""
Default configuration for general agent activities.

Provides a 3-minute timeout with up to 50 retry attempts and 1-minute
maximum interval between retries. Suitable for model calls and standard
agent operations.
"""


def default_toolset_activity_config(toolsets: dict[str, WrapperToolset]) -> dict[str, ActivityConfig]:
    """
    Generate activity configurations for agent toolsets.

    Creates a dictionary mapping each toolset ID to an ActivityConfig with
    shorter timeouts suitable for tool execution. Each toolset gets a 1-minute
    timeout with 50 retry attempts.

    Args:
        toolsets: Dictionary of toolset IDs to WrapperToolset objects.

    Returns:
        Dict[str, ActivityConfig]: Mapping of toolset IDs to their activity
            configurations with 1-minute timeouts and retry policies.

    Example:
        ```python
        toolsets = await agent._get_mcp_toolsets()
        configs = default_toolset_activity_config(toolsets)
        # configs = {'mcp_toolset_1': ActivityConfig(...), ...}
        ```
    """
    return {
        toolset_id: ActivityConfig(
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=50,
                                     maximum_interval=timedelta(seconds=20)
                                     )
        ) for toolset_id in toolsets.keys()}
