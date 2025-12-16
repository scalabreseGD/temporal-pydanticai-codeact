from typing import Any

from temporalio import activity

from temporal.pydanticai.codeact.datamodels.prompts import Prompts
from temporal.pydanticai.codeact.utils.common_utils import load_config, read_prompts, render_jinja_template


@activity.defn
async def get_configs() -> dict[str, Any]:
    return load_config()


@activity.defn
async def get_prompts() -> Prompts:
    return read_prompts()


@activity.defn
async def render_jinja(template_str: str, arguments: dict[str, Any]):
    return render_jinja_template(template_str, arguments)
