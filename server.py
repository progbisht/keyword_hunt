import os
import uuid
import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from main import run_discovery
from db.database import init_db, save_discovery_result, get_job_history, get_keywords_by_job_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

app = FastAPI(title="Keyword Discovery Agent Dashboard API")

# Enable CORS for convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active jobs tracking (running in memory)
# job_id -> {"job_id": str, "seed_keyword": str, "status": str, "logs": list, "progress": int, "total_keywords": int}
active_jobs: Dict[str, Dict] = {}

class DiscoverRequest(BaseModel):
    seed: str
    rounds: int = 1
    force_refresh: bool = False

async def run_discovery_task(job_id: str, seed: str, rounds: int, force_refresh: bool):
    active_jobs[job_id]["status"] = "running"
    
    def progress_callback(msg: str):
        active_jobs[job_id]["logs"].append(msg)
        if "Step 1/5" in msg:
            active_jobs[job_id]["progress"] = 20
        elif "Step 2/5" in msg:
            active_jobs[job_id]["progress"] = 40
        elif "Step 3/5" in msg:
            active_jobs[job_id]["progress"] = 60
        elif "Step 4/5" in msg:
            active_jobs[job_id]["progress"] = 80
        elif "Step 5/5" in msg:
            active_jobs[job_id]["progress"] = 90
        elif "Finished discovery" in msg or "Loaded from Upstash Redis cache" in msg:
            active_jobs[job_id]["progress"] = 100

    try:
        result = await run_discovery(
            seed_keyword=seed,
            rounds=rounds,
            force_refresh=force_refresh,
            progress_callback=progress_callback,
            job_id=job_id
        )
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["total_keywords"] = len(result.keywords)
        active_jobs[job_id]["progress"] = 100
        logger.info(f"Background job completed: {job_id}")
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["logs"].append(f"❌ Error occurred: {str(e)}")
        active_jobs[job_id]["progress"] = 100
        logger.error(f"Background job failed: {job_id}, error: {e}")

@app.on_event("startup")
async def startup_event():
    # Attempt to initialize Supabase DB tables on startup
    await init_db()

@app.post("/api/discover")
async def start_discover(req: DiscoverRequest, background_tasks: BackgroundTasks):
    if not req.seed.strip():
        raise HTTPException(status_code=400, detail="Seed keyword cannot be empty")
    
    job_id = str(uuid.uuid4())
    active_jobs[job_id] = {
        "job_id": job_id,
        "seed_keyword": req.seed.strip(),
        "status": "pending",
        "logs": [f"🚀 Initializing discovery for '{req.seed}'..."],
        "progress": 5,
        "total_keywords": 0
    }
    
    background_tasks.add_task(
        run_discovery_task,
        job_id,
        req.seed.strip(),
        req.rounds,
        req.force_refresh
    )
    
    return {"job_id": job_id, "seed_keyword": req.seed, "status": "pending"}

@app.get("/api/jobs")
async def list_jobs():
    # Fetch historical jobs from database
    history = await get_job_history(limit=50)
    
    # Merge with active in-memory running jobs
    history_ids = {job["job_id"] for job in history}
    
    merged_jobs = []
    # Add active/running jobs first if they aren't persisted yet
    for j_id, job in active_jobs.items():
        if j_id not in history_ids:
            merged_jobs.append({
                "job_id": j_id,
                "seed_keyword": job["seed_keyword"],
                "total_keywords": job["total_keywords"],
                "status": job["status"],
                "progress": job["progress"],
                "created_at": None
            })
            
    # Add database history
    for job in history:
        # Check if it exists in active_jobs (for status/progress enrichment)
        status = "completed"
        progress = 100
        if job["job_id"] in active_jobs:
            status = active_jobs[job["job_id"]]["status"]
            progress = active_jobs[job["job_id"]]["progress"]
            
        merged_jobs.append({
            "job_id": job["job_id"],
            "seed_keyword": job["seed_keyword"],
            "total_keywords": job["total_keywords"],
            "status": status,
            "progress": progress,
            "created_at": job["created_at"]
        })
        
    return merged_jobs

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    # Check memory first for live logs
    if job_id in active_jobs:
        return active_jobs[job_id]
        
    # Check history db
    history = await get_job_history(limit=100)
    for job in history:
        if job["job_id"] == job_id:
            return {
                "job_id": job["job_id"],
                "seed_keyword": job["seed_keyword"],
                "status": "completed",
                "logs": ["⚡ Loaded from archive."],
                "progress": 100,
                "total_keywords": job["total_keywords"]
            }
            
    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/api/jobs/{job_id}/keywords")
async def get_job_keywords(job_id: str):
    keywords = await get_keywords_by_job_id(job_id)
    return keywords

# Mount static folder
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
