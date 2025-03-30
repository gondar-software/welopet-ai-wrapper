import runpod
import json
import os
import asyncio
import aiohttp
import base64
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from runpod import AsyncioEndpoint, AsyncioJob
from typing import Dict, Any, Optional, Tuple

load_dotenv()
runpod.api_key = os.getenv("RUNPOD_API")
URGENT_ENDPOINT_ID = os.getenv("URGENT_ENDPOINT_ID")
NORMAL_ENDPOINT_ID = os.getenv("NORMAL_ENDPOINT_ID")
MAX_URGENT_WORKER = os.getenv("MAX_URGENT_WORKER", 2)
MAX_NORMAL_WORKER = os.getenv('MAX_URGENT_WORKER', 3)
ORIGIN_IMAGE_URL = os.getenv('ORIGIN_IMAGE_URL')
AVAILABLE_URGENT_WORKER = MAX_URGENT_WORKER
AVAILABLE_NORMAL_WORKER = 0
FILLED_URGENT_PODS = False
FILLED_NORMAL_POS = True

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

images = {}

def calc_available():
    global AVAILABLE_NORMAL_WORKER, AVAILABLE_URGENT_WORKER, FILLED_URGENT_PODS, FILLED_NORMAL_POS

    endpoint = runpod.Endpoint(URGENT_ENDPOINT_ID)
    endpoint_health = endpoint.health()
    AVAILABLE_URGENT_WORKER = endpoint_health["workers"]["running"] - endpoint_health["jobs"]["inProgress"]
    FILLED_URGENT_PODS = AVAILABLE_URGENT_WORKER and endpoint_health["workers"]["running"] == MAX_URGENT_WORKER
    
    endpoint = runpod.Endpoint(NORMAL_ENDPOINT_ID)
    endpoint_health = endpoint.health()
    AVAILABLE_NORMAL_WORKER = endpoint_health["workers"]["running"] - endpoint_health["jobs"]["inProgress"]
    FILLED_NORMAL_POS == AVAILABLE_NORMAL_WORKER == 0 and endpoint_health["workers"]["running"] == MAX_NORMAL_WORKER

async def run(url: str = None, urgent: bool = False):
    try:
        async with aiohttp.ClientSession() as session:
            endpoint = AsyncioEndpoint(NORMAL_ENDPOINT_ID if not urgent else URGENT_ENDPOINT_ID, session)
            job: AsyncioJob = await endpoint.run(ORIGIN_IMAGE_URL if url is None else url)

            while True:
                status = await job.status()
                print(f"Current job status: {status}")
                
                if status == "COMPLETED":
                    output = await job.output()
                    return output
                
                elif status in ["FAILED", "CANCELLED"]:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Job failed with status: {status}"
                    )
                
                await asyncio.sleep(3)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )

@app.post('/api/start')
async def start():
    try:
        calc_available()
        
        if AVAILABLE_NORMAL_WORKER == 0:
            if not FILLED_NORMAL_POS:
                return await run()
            else:
                raise HTTPException(
                    status_code=429,
                    detail="No available workers at this time"
                )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking worker availability: {str(e)}"
        )
    
@app.post('/api/prompt')
async def prompt(query: dict):
    try:
        isUrgent = query.get("urgent", False)
        url = query.get("url", ORIGIN_IMAGE_URL)
        calc_available()

        if isUrgent:
            if AVAILABLE_NORMAL_WORKER > 0:
                return await run(url)
            elif AVAILABLE_URGENT_WORKER > 0:
                return await run(url, urgent=True)
            else:
                raise HTTPException(
                    status_code=500,
                    detail="No available workers at this time"
                )
        else:
            if AVAILABLE_NORMAL_WORKER > 0:
                return await run(url)
            else:
                raise HTTPException(
                    status_code=500,
                    detail="No available workers at this time"
                )

    except Exception as e:  
        raise HTTPException(
            status_code=500,
            detail=f"Error during job execution: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app="main:app",
        host="localhost",
        port=8000,
        reload=True
    )