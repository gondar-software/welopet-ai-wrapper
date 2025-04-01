import runpod
import os
import asyncio
import aiohttp
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from runpod import AsyncioEndpoint, AsyncioJob

load_dotenv()
runpod.api_key = os.getenv("RUNPOD_API")
# MAX_WORKER = os.getenv("MAX_WORKER", 30)
ORIGIN_IMAGE_URL = os.getenv('ORIGIN_IMAGE_URL')
# FILLED_URGENT_PODS = False

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

images = {}

# def calc_available():
#     global AVAILABLE_NORMAL_WORKER, AVAILABLE_URGENT_WORKER, FILLED_URGENT_PODS, FILLED_NORMAL_PODS

#     endpoint = runpod.Endpoint(URGENT_ENDPOINT_ID)
#     endpoint_health = endpoint.health()
#     AVAILABLE_URGENT_WORKER = endpoint_health["workers"]["running"] - endpoint_health["jobs"]["inProgress"]
#     FILLED_URGENT_PODS = AVAILABLE_URGENT_WORKER == 0 and endpoint_health["workers"]["running"] == MAX_URGENT_WORKER
    
#     endpoint = runpod.Endpoint(NORMAL_ENDPOINT_ID)
#     endpoint_health = endpoint.health()
#     AVAILABLE_NORMAL_WORKER = endpoint_health["workers"]["running"] - endpoint_health["jobs"]["inProgress"]
#     FILLED_NORMAL_PODS = AVAILABLE_NORMAL_WORKER == 0 and endpoint_health["workers"]["running"] == MAX_NORMAL_WORKER

async def run(url: str = None, urgent: bool = False, workflow_id: int = 1):
    try:
        async with aiohttp.ClientSession() as session:
            # endpoint = AsyncioEndpoint(NORMAL_ENDPOINT_ID if not urgent else URGENT_ENDPOINT_ID, session)
            endpoint = AsyncioEndpoint(os.getenv(f"ENDPOINT_ID{workflow_id}"), session)
            job: AsyncioJob = await endpoint.run({ 
                "url": ORIGIN_IMAGE_URL if url is None else url
            })

            while True:
                status = await job.status()
                
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

# @app.post('/api/start')
# async def start():
#     try:
#         calc_available()
        
#         if AVAILABLE_NORMAL_WORKER == 0:
#             if not FILLED_NORMAL_PODS:
#                 return await run()
#             else:
#                 raise HTTPException(
#                     status_code=429,
#                     detail="No available workers at this time"
#                 )
            
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error checking worker availability: {str(e)}"
#         )
    
@app.post('/api/prompt')
async def prompt(query: dict):
    try:
        # isUrgent = query.get("urgent", False)
        url = query.get("url", ORIGIN_IMAGE_URL)
        # calc_available()

        # if isUrgent:
            # if AVAILABLE_NORMAL_WORKER > 0:
                # output = await run(url)
            # else:
            #     if AVAILABLE_NORMAL_WORKER == 0 and FILLED_NORMAL_PODS:
            #         print("URGENT: (NORMAL MODE) Need to increase max value of workers")
        output = await run(url, urgent=True)
        # else:
        #     if AVAILABLE_URGENT_WORKER == 0 and FILLED_URGENT_PODS:
        #         print("URGENT: (URGENT MODE) Need to increase number of full time active workers")
        #     output = await run(url)

        base64_image = output["message"]
        decoded_bytes = base64.b64decode(base64_image)
        return Response(
            content=decoded_bytes,
            media_type=f"image/jpeg"
        )

    except Exception as e:  
        raise HTTPException(
            status_code=500,
            detail=f"Error during job execution: {str(e)}"
        )
    
@app.post('/api/v2/prompt')
async def prompt2(query: dict):
    try:
        url = query.get("url", ORIGIN_IMAGE_URL)
        workflow_id = query.get("workflow_id", 1)

        output = await run(url, urgent=True, workflow_id=workflow_id)

        base64_image = output["message"]
        decoded_bytes = base64.b64decode(base64_image)
        return Response(
            content=decoded_bytes,
            media_type=f"image/jpeg"
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