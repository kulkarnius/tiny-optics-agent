# tiny-optics-agent

A set of three MCP (Model Context Protocol) servers that give an LLM the ability to control optical hardware, search technical documentation, and run sandboxed Python code.

| Server | File | What it does |
|---|---|---|
| **Hardware Controller** | `hardware_server.py` | Move a motor, capture images from a camera (real or mock) |
| **RAG Document Search** | `rag_server.py` | Semantic search over your markdown documentation |
| **Python Scratchpad** | `scratchpad_server.py` | Run Python code in a sandboxed Docker container |

Each server is independent — use one, two, or all three.

---

## Prerequisites

- Python 3.11+
- [Docker Desktop](https://docs.docker.com/get-docker/) (required only for the Scratchpad server)
- Real hardware drivers (optional — all servers fall back to mock implementations automatically)

---

## Installation

```bash
# Clone the repo
git clone <repo-url>
cd tiny-optics-agent

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

`.env` options:

```
# Motor: "pdxc" | "mock" | "auto" (default)
MOTOR_TYPE=auto

# Camera: "imaging_source" | "mock" | "auto" (default)
CAMERA_TYPE=auto

# Required only when CAMERA_TYPE=imaging_source or auto
CAMERA_SERIAL_NUMBER=1234567890
GENTL_CTI_PATH=/path/to/your/gentl.cti
```

With `auto` (the default), each server tries to connect to real hardware first and silently falls back to a mock if hardware is not found. You do not need to change anything to get started.

---

## Testing

Run the tests before connecting a server to your LLM to confirm everything is working.

### Hardware (mock devices, no real hardware needed)

```bash
python hardware_test.py
```

Expected output: motor move and camera capture succeed with mock devices.

### RAG pipeline

```bash
python -m pytest test_rag.py -v
```

This tests chunking, embedding, and vector search in isolation using temporary directories. No documents need to be in `documents/` beforehand.

### Scratchpad (requires Docker)

Build the sandbox image first, then run the tests:

```bash
docker build -f Dockerfile.scratchpad -t scratchpad-sandbox .
python -m pytest test_scratchpad.py -v
```

Tests cover: arithmetic, NumPy/SciPy/SymPy, matplotlib auto-save, stateful execution, session reset, timeout enforcement, network isolation, and read-only filesystem.

---

## Connecting a Server to Your LLM

All three servers speak the MCP stdio transport — they are launched as subprocesses by the LLM host.

### Claude Desktop / Claude Code

Add entries to your MCP config file. On macOS this is `~/Library/Application Support/Claude/claude_desktop_config.json`; on Windows it is `%APPDATA%\Claude\claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "hardware": {
      "command": "python",
      "args": ["/absolute/path/to/tiny-optics-agent/hardware_server.py"],
      "env": {
        "MOTOR_TYPE": "auto",
        "CAMERA_TYPE": "auto"
      }
    },
    "rag": {
      "command": "python",
      "args": ["/absolute/path/to/tiny-optics-agent/rag_server.py"]
    },
    "scratchpad": {
      "command": "python",
      "args": ["/absolute/path/to/tiny-optics-agent/scratchpad_server.py"]
    }
  }
}
```

If you are using a virtual environment, replace `"python"` with the full path to the interpreter, e.g. `/absolute/path/to/tiny-optics-agent/.venv/bin/python`.

Restart Claude Desktop after editing the config.

### Claude Code (CLI)

```bash
# Add a server (run from the repo root)
claude mcp add hardware python hardware_server.py
claude mcp add rag     python rag_server.py
claude mcp add scratchpad python scratchpad_server.py
```

### Other MCP-compatible LLM hosts

Use `python <server_file>.py` as the command. The servers communicate over stdio with no additional flags required. Refer to your host's documentation for how to register an MCP stdio server.

---

## Using the Servers

### Hardware Controller

Once connected, the LLM can:

| Tool | Description |
|---|---|
| `move_motor(target_position)` | Move the motor to an absolute position (degrees) |
| `home_motor()` | Home the motor (required before closed-loop moves on real hardware) |
| `refresh_motor()` | Sync internal state with the current hardware position |
| `configure_camera(exposure_ms)` | Set exposure time (1–2000 ms) |
| `capture_image()` | Capture and save an image to disk |

The LLM can also read:
- `hardware://inventory` — current state of all devices as JSON
- `camera://latest` — the most recently captured image (binary JPEG)

**Adding documents for the RAG server:** Place any `.md` files in the `documents/` directory. The server indexes them automatically on startup and re-indexes changed files on subsequent starts.

### RAG Document Search

| Tool | Description |
|---|---|
| `search_documents(query, top_k=5)` | Semantic search across all indexed documents |
| `get_full_section(source_file, section_heading)` | Retrieve the full text of a named heading |

The LLM can also read:
- `rag://document-list` — all indexed documents with their heading outlines

Documents are embedded using [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) (downloaded automatically on first run, ~90 MB).

### Python Scratchpad

| Tool | Description |
|---|---|
| `run_code(code, timeout=30)` | Execute Python in a persistent session; variables survive between calls |
| `reset_session()` | Clear all variables and restart the executor |
| `list_figures()` | List all figures saved to the shared output directory |

The LLM can also read:
- `scratchpad://status` — container status, executor state, and saved figures

The sandbox has `numpy`, `scipy`, `sympy`, `matplotlib`, and `cv2` pre-imported. Matplotlib figures are auto-saved as PNGs on every execution. The container has no network access and a read-only filesystem (except `/shared` and `/tmp`).

The Docker image is built automatically the first time the server starts. Subsequent starts reuse the cached image.

---

## Repository Layout

```
tiny-optics-agent/
├── hardware_server.py       # MCP server — hardware control
├── rag_server.py            # MCP server — document search
├── scratchpad_server.py     # MCP server — Python sandbox
├── devices/                 # Motor and camera drivers
│   ├── motor.py             # Mock motor
│   ├── pdxc_motor.py        # Thorlabs PDXC piezo motor
│   ├── camera.py            # Mock camera
│   ├── imaging_source_camera.py  # ImagingSource GigE camera
│   └── vendor/              # Thorlabs SDK wrapper
├── rag/                     # RAG pipeline
│   ├── chunker.py           # Markdown-aware chunking
│   ├── embedder.py          # Sentence-transformer wrapper
│   └── index.py             # ChromaDB index with change detection
├── scratchpad/              # Scratchpad backend
│   ├── docker_backend.py    # Host-side Docker orchestration
│   └── executor.py          # In-container persistent REPL
├── Dockerfile.scratchpad    # Docker image for the sandbox
├── documents/               # Place your .md files here (RAG server)
├── data/                    # Auto-created: ChromaDB and hash index
├── hardware_test.py         # Smoke test for mock hardware
├── test_rag.py              # pytest suite for RAG pipeline
└── test_scratchpad.py       # pytest suite for Docker scratchpad
```
