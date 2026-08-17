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
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
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
    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

    @app.get("/")
    def read_index():
        return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"status": "running", "message": "Dashboard assets directory not found. API endpoints are operational."}

def start_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    telemetry_db: str = "costopt_telemetry.db",
    cache_db: str = "costopt_cache.db"
) -> None:
    """Configures database connections and launches the API/Dashboard server."""
    set_db_paths(telemetry_db, cache_db)
    print(f"Starting LLM CostOpt Dashboard on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_server()
