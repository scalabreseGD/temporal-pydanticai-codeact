"""
FastAPI application for code execution agent API.

This module provides REST API endpoints for interacting with the CodeActAgent
through Temporal workflows. It exposes endpoints for:
- Executing agent tasks with code execution
- Downloading generated files from agent executions
"""
import asyncio
import io
import os
import tarfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any

import docker
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy

from temporal.pydanticai.codeact.activities.common import load_config, get_temporal_client, create_unique_id
from temporal.pydanticai.codeact.datamodels.codeact import CodeActAgentOutput
from temporal.pydanticai.codeact.docker_sandbox.container_sandbox import PersistentContainerSandbox

load_dotenv(find_dotenv())

# Global state for sandbox and temporal client
app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.

    This context manager handles startup and shutdown logic:
    - Startup: Initialize Temporal client and sandbox
    - Shutdown: Clean up resources
    """
    # Startup: Initialize resources
    app_configurations = load_config()
    app_state["temporal_client"] = await get_temporal_client(
        app_configurations['temporal'],
        plugins=[PydanticAIPlugin()],
    )
    app_state["sandbox"] = PersistentContainerSandbox()

    print("✓ Temporal client initialized")
    print("✓ Sandbox initialized")

    yield

    # Shutdown: Clean up resources
    app_state.clear()
    print("✓ Application shutdown complete")


app = FastAPI(
    lifespan=lifespan,
    title="CodeAct Agent API",
    description="API for executing code tasks with CodeActAgent and downloading generated files",
    version="0.1.0"
)


@app.get("/", response_class=HTMLResponse)
async def home():
    """
    Serve the chat UI interface.

    Returns:
        HTML page with the interactive chat interface
    """
    template_path = Path(__file__).parent / "templates" / "chat.html"
    with open(template_path, "r") as f:
        return f.read()


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""
    task: str = Field(..., description="User task description for the agent to execute")
    workflow_id: Optional[str] = Field(default=None,
                                       description="Workflow ID representing the open workflow for the agent")


class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""
    message: str = Field(description="Agent's response message")
    container_id: str = Field(description="Container ID used for execution")
    file_paths: list[str] = Field(description="List of file paths available for download")
    workflow_id: str = Field(description="Workflow ID for this execution")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Execute a code task using the CodeActAgent.

    This endpoint accepts a natural language task description, executes it
    using the SimpleAgentWorkflow with code execution capabilities, and
    returns the agent's output along with any generated files.

    Args:
        request: ChatRequest containing the task description

    Returns:
        ChatResponse with the agent's message, container ID, available files, and workflow ID

    Raises:
        HTTPException: If workflow execution fails

    Example:
        ```json
        POST /chat
        {
            "task": "Generate a plot showing NVIDIA stock trends",
            "workflow_id": "custom-task-123"
        }
        ```
    """
    temporal_client: Client = app_state.get("temporal_client")
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")

    # Generate workflow ID if not provided
    task_queue = os.getenv('TASK_QUEUE', 'sample_queue')

    try:

        if request.workflow_id:
            workflow_id = request.workflow_id
            workflow_handle = temporal_client.get_workflow_handle(workflow_id=workflow_id)

            desc = await workflow_handle.describe()
            if desc.status == WorkflowExecutionStatus.RUNNING:
                await workflow_handle.signal(signal='send_user_task', arg=request.task)
        else:
            workflow_id = f"chat-{create_unique_id(request.task)}"
            workflow_handle = await temporal_client.start_workflow(
                'SimpleAgentWorkflow',
                id=workflow_id,
                task_queue=task_queue,
                id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
                result_type=str,
                start_signal='send_user_task',
                start_signal_args=[request.task],
            )
        result = None
        while not result:
            result = await workflow_handle.query(query='agent_output', result_type=Optional[CodeActAgentOutput | str])
            if not result:
                await asyncio.sleep(1)

        # Return the agent output
        return ChatResponse(
            message=result.message,
            container_id=result.container_id,
            file_paths=result.file_paths,
            workflow_id=workflow_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@app.get("/download_file")
async def download_file(
        container_id: str = Query(..., description="Container ID where the file is located"),
        file_path: str = Query(..., description="Path to the file within the container")
):
    """
    Download a file from a Docker container.

    This endpoint retrieves a file from a specific container and returns it
    as a downloadable response. Handles both text and binary files correctly.

    Args:
        container_id: ID of the container containing the file
        file_path: Path to the file within the container (e.g., '/workspace/plot.png')

    Returns:
        StreamingResponse with the requested file

    Raises:
        HTTPException: If file reading fails or container not found

    Example:
        ```
        GET /download_file?container_id=abc123&file_path=/workspace/plot.png
        ```
    """
    sandbox = app_state.get("sandbox")
    if sandbox is None:
        raise HTTPException(status_code=503, detail="Sandbox not initialized")

    try:
        # Get the container using the sandbox's method
        container = sandbox._get_container_by_id(container_id)
        if not container:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")

        # Use Docker's get_archive to retrieve file as raw bytes
        # This returns a tar archive containing the file
        try:
            bits, stat = container.get_archive(file_path)
        except docker.errors.NotFound:
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error accessing file: {str(e)}")

        # Extract the file from the tar archive
        tar_stream = io.BytesIO()
        for chunk in bits:
            tar_stream.write(chunk)
        tar_stream.seek(0)

        # Open the tar archive and extract the file
        with tarfile.open(fileobj=tar_stream, mode='r') as tar:
            # Get the file name from the path
            filename = Path(file_path).name

            # Find the file in the archive
            member = None
            for m in tar.getmembers():
                if m.name == filename or m.name.endswith('/' + filename):
                    member = m
                    break

            if not member:
                raise HTTPException(status_code=404, detail=f"File not found in archive")

            # Extract file content
            file_obj = tar.extractfile(member)
            if file_obj is None:
                raise HTTPException(status_code=500, detail="Cannot extract file content")

            file_content = file_obj.read()

        # Determine media type based on file extension
        suffix = Path(file_path).suffix.lower()
        media_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.html': 'text/html',
            '.py': 'text/x-python',
            '.svg': 'image/svg+xml',
        }
        media_type = media_type_map.get(suffix, 'application/octet-stream')

        # Return file as streaming response with raw bytes
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading file: {str(e)}"
        )


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns:
        Status of the API service
    """
    return {
        "status": "healthy",
        "temporal_connected": app_state.get("temporal_client") is not None,
        "sandbox_initialized": app_state.get("sandbox") is not None
    }

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
