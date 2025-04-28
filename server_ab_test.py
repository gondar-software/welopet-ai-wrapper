import base64
import asyncio
import aiohttp
import runpod
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from runpod import AsyncioEndpoint, AsyncioJob
from dotenv import load_dotenv

from core.pod_manager import *

load_dotenv()

easycontrol_manager = None
# magicvideo_manager = None
logging_thread = None

def log_state():
    while True:
        if easycontrol_manager:
            easycontrol_manager_state = easycontrol_manager.get_state()
            print(f"{easycontrol_manager_state["state"].name}  \
  {easycontrol_manager_state["total_pod_num"]}  \
  {easycontrol_manager_state["initializing_pod_num"]}  \
  {easycontrol_manager_state["starting_pod_num"]}  \
  {easycontrol_manager_state["free_pod_num"]}  \
  {easycontrol_manager_state["processing_pod_num"]}  \
  {easycontrol_manager_state["completed_pod_num"]}  \
  {easycontrol_manager_state["terminated_pod_num"]}  \
  {easycontrol_manager_state["queued_prompt_num"]}  \
  {easycontrol_manager_state["processing_prompt_num"]}  \
  {easycontrol_manager_state["completed_prompt_num"]}  \
  {easycontrol_manager_state["failed_prompt_num"]}", end="\r")
            time.sleep(1)

def start_logging_thread():
    from threading import Thread
    
    global logging_thread

    logging_thread = Thread(target=log_state)
    logging_thread.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global easycontrol_manager, logging_thread
    
    easycontrol_manager = PodManager(
        GPUType.RTXA6000,
        VolumeType.EasyControl
    )
    
    logging_thread = Thread(target=log_state, daemon=True)
    logging_thread.start()
    
    yield
    
    if easycontrol_manager:
        easycontrol_manager.stop()
    if logging_thread:
        terminate_thread(logging_thread)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runpod.api_key = RUNPOD_API

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
    
async def run_easycontrol(url: str = None, workflow_id: int = 1):
    try:
        async with aiohttp.ClientSession() as session:
            endpoint = AsyncioEndpoint(os.getenv(f"ENDPOINT_ID5"), session)
            job: AsyncioJob = await endpoint.run({ 
                "url": ORIGIN_IMAGE_URL if url is None else url,
                "workflow_id": workflow_id
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

count = 0

@app.post('/api/v3/prompt')
async def prompt(query: dict):
    start_time = time.time()

    global count
    count += 1
    if count == 1000:
        count = 0

    if count % 2 == 0:
        try:
            url = query.get("url", ORIGIN_IMAGE_URL)
            workflow_id = query.get("workflow_id", 0)
            if workflow_id == 1 or \
                workflow_id == 2 or \
                workflow_id == 4:
                result = easycontrol_manager.queue_prompt(
                    WorkflowType(workflow_id),
                    url
                )
                print(f"mode1: {(time.time() - start_time):.4} seconds are taken to process request")
                if result.output_state == OutputState.Completed:
                    return Response(
                        content=result.output,
                        media_type=f"image/jpeg"
                    )
                else: 
                    print(result.output)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error during job execution: {result.output}"
                    )
            else:
                # result = magicvideo_manager.queue_prompt(
                #     WorkflowType(workflow_id),
                #     url
                # )
                # return Response(
                #     content=result.output,
                #     media_type=f"video/mp4"
                # )
                return

        except Exception as e:  
            raise HTTPException(
                status_code=500,
                detail=f"Error during job execution: {str(e)}"
            )

    else:
        try:
            url = query.get("url", ORIGIN_IMAGE_URL)
            workflow_id = query.get("workflow_id", 1)

            output = await run_easycontrol(url, workflow_id=workflow_id)
            
            print(f"mode2: {(time.time() - start_time):.4} seconds are taken to process request")

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

@app.post('/api/v3/stop')
def stop():
    if easycontrol_manager:
        easycontrol_manager.stop()
    if logging_thread:
        terminate_thread(logging_thread)

@app.post('/api/v3/restart')
def restart():
    if easycontrol_manager:
        easycontrol_manager.stop()
    if logging_thread:
        terminate_thread(logging_thread)
    logging_thread = Thread(target=log_state, daemon=True)
    logging_thread.start()
    
if __name__ == "__main__":
    import uvicorn
    
    start_logging_thread()

    uvicorn.run(
        app="server_ab_test:app",
        host="localhost",
        port=8080,
        reload=False
    )