import base64
import asyncio
import aiohttp
import runpod
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from runpod import AsyncioEndpoint, AsyncioJob
from dotenv import load_dotenv
import os
import time
from typing import Dict
from threading import Thread, Lock

from core.pod_manager import *

load_dotenv()

class RequestCounter:
    def __init__(self):
        self._count = 0
        self._lock = Lock()
    
    def increment(self):
        with self._lock:
            self._count += 1
            return self._count
    
    def get(self):
        with self._lock:
            return self._count

class AppState:
    def __init__(self):
        self.counter = RequestCounter()
        self.managers: Dict[str, PodManager] = {}
        self.logging_thread = None
        self.initialized = False

app_state = AppState()

async def log_state():
    while True:
        if app_state.managers.get("easycontrol"):
            state = app_state.managers["easycontrol"].get_state()
            print(
                f"{state['state'].name}  {state['total_pod_num']}  {state['ideal_pod_num']}  "
                f"{state['initializing_pod_num']}  {state['starting_pod_num']}  "
                f"{state['free_pod_num']}  {state['processing_pod_num']}  "
                f"{state['completed_pod_num']}  {state['terminated_pod_num']}  "
                f"{state['queued_prompt_num']}  {state['processing_prompt_num']}  "
                f"{state['completed_prompt_num']}  {state['failed_prompt_num']}",
                end="\r"
            )
        await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.managers["easycontrol"] = PodManager(
        GPUType.RTXA6000,
        VolumeType.EasyControl
    )
    
    app_state.logging_thread = Thread(
        target=lambda: asyncio.run(log_state()),
        daemon=True
    )
    app_state.logging_thread.start()
    app_state.initialized = True
    
    yield
    
    for manager in app_state.managers.values():
        manager.stop()
    if app_state.logging_thread:
        app_state.logging_thread.join(timeout=1)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runpod.api_key = os.getenv("RUNPOD_API")

async def run_remote_job(url: str, workflow_id: int, endpoint_id: int):
    """Generic function to run jobs on remote endpoints"""
    try:
        async with aiohttp.ClientSession() as session:
            endpoint = AsyncioEndpoint(os.getenv(f"ENDPOINT_ID{endpoint_id}"), session)
            job: AsyncioJob = await endpoint.run({
                "url": url,
                "workflow_id": workflow_id
            })

            while True:
                status = await job.status()
                
                if status == "COMPLETED":
                    output = await job.output()
                    return output
                elif status in ["FAILED", "CANCELLED"]:
                    raise RuntimeError(f"Job failed with status: {status}")
                
                await asyncio.sleep(3)
    except Exception as e:
        raise RuntimeError(f"Remote job error: {str(e)}")

@app.post('/api/v3/prompt')
async def process_prompt(query: dict):
    start_time = time.time()
    current_count = app_state.counter.increment()
    
    try:
        url = query.get("url", ORIGIN_IMAGE_URL)
        workflow_id = query.get("workflow_id", 1)
        
        if current_count % 2 == 0:
            if workflow_id in {1, 2, 4}:
                result = await asyncio.to_thread(
                    app_state.managers["easycontrol"].queue_prompt,
                    WorkflowType(workflow_id),
                    url
                )
                
                if result.output_state == OutputState.Completed:
                    print(f"mode1: {(time.time() - start_time):.4f} seconds")
                    return Response(
                        content=result.output,
                        media_type="image/jpeg"
                    )
                raise HTTPException(500, detail=f"Processing error: {result.output}")
        else:
            output = await run_remote_job(
                url,
                workflow_id,
                endpoint_id=5 if workflow_id == workflow_id in {1, 2, 4} else workflow_id
            )
            
            print(f"mode2: {(time.time() - start_time):.4f} seconds")
            base64_image = output["message"]
            return Response(
                content=base64.b64decode(base64_image),
                media_type="image/jpeg"
            )
            
    except Exception as e:
        raise HTTPException(500, detail=f"Error processing request: {str(e)}")

@app.post('/api/v3/stop')
async def stop_service():
    for manager in app_state.managers.values():
        manager.stop()
    if app_state.logging_thread:
        app_state.logging_thread.join(timeout=1)
    return {"status": "stopped"}

@app.post('/api/v3/restart')
async def restart_service():
    await stop_service()
    
    app_state.managers["easycontrol"] = PodManager(
        GPUType.RTXA6000,
        VolumeType.EasyControl
    )
    app_state.logging_thread = Thread(
        target=lambda: asyncio.run(log_state()),
        daemon=True
    )
    app_state.logging_thread.start()
    return {"status": "restarted"}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app="server_ab_test:app",
        host="localhost",
        reload=False,
        port=8080
    )