from datetime import timedelta

from pydantic_ai import WrapperToolset
from temporalio.common import RetryPolicy
from temporalio.workflow import ActivityConfig

DEFAULT_ACTIVITY_CONFIG = ActivityConfig(start_to_close_timeout=timedelta(minutes=3),
                                         retry_policy=RetryPolicy(
                                             maximum_attempts=50,
                                             maximum_interval=timedelta(minutes=1)
                                         ))


def default_toolset_activity_config(toolsets: dict[str, WrapperToolset]):
    return {
        toolset_id: ActivityConfig(
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=50,
                                     maximum_interval=timedelta(seconds=20)
                                     )
        ) for toolset_id in toolsets.keys()}
