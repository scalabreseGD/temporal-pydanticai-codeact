# CodeAct Agent API

REST API for interacting with the CodeActAgent through Temporal workflows.

## Overview

This FastAPI application provides endpoints for:
- Executing natural language tasks with code execution capabilities
- Downloading files generated during task execution

## Prerequisites

1. **Temporal Server**: Ensure Temporal server is running
2. **Configuration**: Set up `app_conf.yml` and `agent_prompts.yml`
3. **Environment Variables**: Configure `.env` file with necessary settings

## Installation

Dependencies are already included in the main project. Ensure you have run:

```bash
uv sync
```

## Running the API

### Development Mode

```bash
# From the project root
python -m src.api.main
```

Or with uvicorn directly:

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### 1. Health Check

Check if the API is running and services are initialized.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "temporal_connected": true,
  "sandbox_initialized": true
}
```

### 2. Chat (Execute Task)

Execute a natural language task using the CodeActAgent.

**Endpoint:** `POST /chat`

**Request Body:**
```json
{
  "task": "Analyze NVIDIA stock trends and generate a plot",
  "workflow_id": "optional-custom-id"
}
```

**Parameters:**
- `task` (required): Natural language description of the task
- `workflow_id` (optional): Custom workflow ID for tracking. Auto-generated if not provided.

**Response:**
```json
{
  "message": "Agent's response and analysis results",
  "container_id": "abc123def456",
  "file_paths": [
    "/workspace/nvidia_plot.png",
    "/workspace/analysis.csv"
  ],
  "workflow_id": "chat-abc123..."
}
```

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Calculate the mean and standard deviation of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
  }'
```

**Example using Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "task": "Generate a visualization of sine and cosine waves"
    }
)

result = response.json()
print(f"Message: {result['message']}")
print(f"Container ID: {result['container_id']}")
print(f"Available files: {result['file_paths']}")
```

### 3. Download File

Download a file generated during task execution.

**Endpoint:** `GET /download_file`

**Query Parameters:**
- `container_id` (required): Container ID from the chat response
- `file_path` (required): Path to the file within the container

**Example:**
```bash
curl -X GET "http://localhost:8000/download_file?container_id=abc123&file_path=/workspace/plot.png" \
  -o plot.png
```

**Example using Python:**
```python
import requests

params = {
    "container_id": "abc123def456",
    "file_path": "/workspace/plot.png"
}

response = requests.get(
    "http://localhost:8000/download_file",
    params=params
)

# Save the file
with open("downloaded_plot.png", "wb") as f:
    f.write(response.content)
```

## Interactive Documentation

FastAPI provides automatic interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Environment Variables

Required environment variables in `.env`:

```bash
# Temporal Configuration
TASK_QUEUE=sample_queue

# Configuration Paths (optional)
APP_CONFIG_PATH=./app_conf.yml
APP_PROMPTS_PATH=./agent_prompts.yml

# API Keys (if needed by agents)
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP Request
       ▼
┌─────────────────┐
│  FastAPI App    │
│  (lifespan mgr) │
└──────┬──────────┘
       │ Workflow Execution
       ▼
┌─────────────────┐
│ Temporal Server │
└──────┬──────────┘
       │
       ▼
┌──────────────────┐
│ SimpleAgent      │
│ Workflow         │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Docker Container │
│ (Code Execution) │
└──────────────────┘
```

### Modern FastAPI Lifespan

The application uses FastAPI's modern `lifespan` context manager (replacing deprecated `@app.on_event`):
- **Startup**: Initializes Temporal client and Docker sandbox
- **Shutdown**: Cleans up resources automatically

## Error Handling

The API returns standard HTTP status codes:

- `200`: Success
- `404`: File not found or container not found
- `500`: Workflow execution or internal error
- `503`: Service not initialized (Temporal or Sandbox)

## Development Tips

### Testing the API

1. Start Temporal server
2. Start a worker:
   ```bash
   python -m src.workers.sandbox_worker
   ```
3. Start the API:
   ```bash
   python -m src.api.main
   ```
4. Test with curl or visit http://localhost:8000/docs

### Debugging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Limitations

- Container cleanup is currently commented out to allow file downloads
- File downloads work only while the container is running
- Binary files may need encoding adjustments in the download endpoint

## Future Enhancements

- [ ] Add authentication/authorization
- [ ] Implement rate limiting
- [ ] Add WebSocket support for streaming responses
- [ ] Container lifecycle management improvements
- [ ] File caching for better download performance
- [ ] Support for multiple concurrent workflows
