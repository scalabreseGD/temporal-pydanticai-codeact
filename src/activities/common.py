"""Configuration loader for Airflow Spark Knowledge Base packages."""
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from temporalio import activity
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from datamodels.prompts import AgentPrompts, Prompts


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Priority order:
    1. Explicit config_path parameter
    2. APP_CONFIG_PATH environment variable
    3. ./app_conf.yml (current directory)
    4. ~/.config/airflow-spark-kb/app_conf.yml (user config)
    5. /etc/airflow-spark-kb/app_conf.yml (system config, Docker)
    6. Package default (bundled with temporal_pydantic_shared)

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If no config file is found in any location
    """
    config_locations = [
        config_path,
        os.getenv('APP_CONFIG_PATH'),
        './app_conf.yml',
        Path.home() / '.config/app_conf.yml',
        '/etc/app_conf.yml',
        Path(__file__).parent / 'app_conf.yml',  # Package default
    ]

    for location in config_locations:
        if location and Path(location).exists():
            with open(location) as f:
                config = yaml.safe_load(f)
                return _resolve_env_vars(config)

    raise FileNotFoundError(
        "No configuration file found. Checked locations: " +
        ", ".join(str(loc) for loc in config_locations if loc)
    )


def read_prompts(path=None) -> Prompts:
    """
    Read and parse agent prompts from a YAML file.

    Loads a YAML file containing system prompts and instructions for all agents,
    validates them against the AgentPrompts model, and returns a structured
    Prompts object.

    Args:
        path (str): Path to the prompts YAML file.

    Returns:
        Prompts: Parsed and validated prompts for all agents, with each
                 agent's prompts accessible by agent name.

    Raises:
        FileNotFoundError: If the prompts file doesn't exist.
        yaml.YAMLError: If the YAML file is malformed.
        pydantic.ValidationError: If the prompts don't match the expected schema.
    """
    locations = [
        path,
        os.getenv('APP_PROMPTS_PATH'),
        './agent_prompts.yml',
        Path.home() / '.config/agent_prompts.yml',
        '/etc/agent_prompts.yml',
        Path(__file__).parent / 'agent_prompts.yml',  # Package default
    ]
    for location in locations:
        if location and Path(location).exists():
            with open(location, "r") as f:
                all_prompts = yaml.safe_load(f)
                agent_prompts = {}
                for name, prompts in all_prompts.items():
                    agent_prompts[name] = AgentPrompts.model_validate(prompts)
            return Prompts(agent_prompts=agent_prompts)

    raise FileNotFoundError(
        "No prompts file found. Checked locations: " +
        ", ".join(str(loc) for loc in locations if loc)
    )


async def get_temporal_client(temporal_config: Dict[str, Any], **kwargs) -> Client:
    """
    Establish a connection to the Temporal server and return a client object.

    This function creates and configures a Temporal client using the provided
    configuration settings. It supports custom namespaces and uses Pydantic
    data converter for enhanced type handling and serialization.

    Args:
        temporal_config (Dict[str, Any]): Dictionary containing Temporal server configuration:
            - url (str): The Temporal server URL
            - namespace (str, optional): Namespace (defaults to 'default')
        **kwargs: Additional arguments to pass to Client.connect(), such as:
            - plugins (List): Temporal plugins (e.g., PydanticAIPlugin, LogfirePlugin)
            - tls (TLSConfig): TLS configuration if using secure connection
            - rpc_metadata (Dict): Additional RPC metadata

    Returns:
        Client: A configured Temporal client instance ready for workflow operations.

    Raises:
        temporalio.service.RPCError: If connection to Temporal server fails.

    Example:
        config = {'url': 'localhost:7233', 'namespace': 'default'}
        client = await get_temporal_client(config)
    """
    all_kwargs = temporal_config | kwargs
    return await Client.connect(data_converter=pydantic_data_converter,
                                **all_kwargs)


def _resolve_env_vars(config: Any) -> Any:
    """
    Recursively resolve environment variable references in config.

    If a string value matches an environment variable name, it will be replaced
    with the actual env var value.

    Args:
        config: Configuration dict or value

    Returns:
        Configuration with resolved environment variables
    """
    if isinstance(config, dict):
        return {key: _resolve_env_vars(value) for key, value in config.items()}
    elif isinstance(config, list):
        return [_resolve_env_vars(item) for item in config]
    elif isinstance(config, str):
        # Check if the string is an env var reference
        env_value = os.getenv(config)
        if env_value is not None:
            return env_value
        return config
    return config


def create_unique_id(input_string: str) -> str:
    """
    Generate a unique workflow ID from an input string.

    Args:
        input_string: String to hash (typically a file path).

    Returns:
        str: SHA256 hash of the input string.
    """
    return hashlib.sha256(input_string.encode('utf-8')).hexdigest()


@activity.defn
async def get_configs() -> dict[str, Any]:
    return load_config()


@activity.defn
async def get_prompts() -> Prompts:
    return read_prompts()
