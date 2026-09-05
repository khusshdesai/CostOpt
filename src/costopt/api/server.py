import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from costopt.api.routes import router, set_db_paths

app = FastAPI(
    title="LLM CostOpt API",
    description="Cost optimization API serving the developer dashboard",
    version="0.1.0"
)

# Enable CORS for local cross-origin dashboard testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8400", "http://localhost:8400",
        "http://127.0.0.1:8000", "http://localhost:8000",
        "http://127.0.0.1:3000", "http://localhost:3000"
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach routes
app.include_router(router, prefix="/api")

# Serve dashboard static folder
DASHBOARD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "dashboard")
)

if os.path.exists(DASHBOARD_DIR):
    class NoCacheStaticFiles(StaticFiles):
        def is_not_modified(self, response_headers, request_headers) -> bool:
            return False

        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    app.mount("/static", NoCacheStaticFiles(directory=DASHBOARD_DIR), name="static")

    @app.get("/")
    def read_index():
        return FileResponse(
            os.path.join(DASHBOARD_DIR, "index.html"),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
else:
    @app.get("/")
    def read_root():
        return {"status": "running", "message": "Dashboard assets directory not found. API endpoints are operational."}

def is_port_in_use(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def is_costopt_server(host: str, port: int) -> bool:
    import requests
    try:
        url = f"http://{host}:{port}/api/vscode/health"
        resp = requests.get(url, headers={'User-Agent': 'CostOpt-Ping'}, timeout=1.5)  # nosemgrep
        return resp.status_code == 200
    except Exception:
        return False

def start_server(
    host: str = "127.0.0.1",
    port: int = 8400,
    telemetry_db: str = "costopt_telemetry.db",
    cache_db: str = "costopt_cache.db"
) -> None:
    """Configures database connections and launches the API/Dashboard server with automatic port detection."""
    set_db_paths(telemetry_db, cache_db)
    
    target_port = port
    if is_port_in_use(host, target_port):
        if is_costopt_server(host, target_port):
            print(f"Notice: CostOpt Dashboard server is already running at http://{host}:{target_port}")
            return
        else:
            print(f"Notice: Port {target_port} is occupied by another service (e.g. vLLM or Ollama).")
            for alt_port in range(port + 1, port + 20):
                if not is_port_in_use(host, alt_port):
                    target_port = alt_port
                    break
            print(f"Starting LLM CostOpt Dashboard on fallback port: http://{host}:{target_port}")
            print(f"💡 Note: Update your VS Code setting 'costopt.endpoint' to 'http://{host}:{target_port}' if using the extension.")
    else:
        print(f"Starting LLM CostOpt Dashboard on http://{host}:{target_port}")

    uvicorn.run(app, host=host, port=target_port)


if __name__ == "__main__":
    start_server()
