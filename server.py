from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.pod_manager import *

easycontrol_manager = None
logging_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global easycontrol_manager, logging_thread
    
    easycontrol_manager = PodManager(
        GPUType.RTXA6000,
        WorkflowType.Ghibli
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

def log_state():
    while True:
        if easycontrol_manager:
            state = easycontrol_manager.get_state()
            print(f"{state["state"].name}  \
        {state["total_pod_num"]}  \
        {state["initializing_pod_num"]}  \
        {state["starting_pod_num"]}  \
        {state["free_pod_num"]}  \
        {state["processing_pod_num"]}  \
        {state["completed_pod_num"]}  \
        {state["terminated_pod_num"]}  \
        {state["queued_prompt_num"]}  \
        {state["processing_prompt_num"]}  \
        {state["completed_prompt_num"]}  \
        {state["failed_prompt_num"]}", end="\r")
            time.sleep(3)

@app.post('/api2/v2/prompt')
def prompt(query: dict):
    try:
        url = query.get("url", ORIGIN_IMAGE_URL)
        result = easycontrol_manager.queue_prompt(
            WorkflowType.Ghibli,
            url
        )
        return Response(
            content=result.output,
            media_type=f"image/jpeg"
        )

    except Exception as e:  
        raise HTTPException(
            status_code=500,
            detail=f"Error during job execution: {str(e)}"
        )

@app.post('/api2/v2/stop')
def stop():
    try:
        if easycontrol_manager:
            easycontrol_manager.stop()
        return {"message": "OK"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error stopping server: {str(e)}"
        )

@app.post('/api2/v2/restart')
def restart():
    try:
        if easycontrol_manager:
            easycontrol_manager.restart()
        return {"message": "OK"}
    except Exception as e:
        raise HTTPException

def start_logging_thread():
    from threading import Thread
    
    global logging_thread

    logging_thread = Thread(target=log_state)
    logging_thread.start()
    
if __name__ == "__main__":
    import uvicorn
    
    start_logging_thread()

    uvicorn.run(
        app="server:app",
        host="localhost",
        port=8080,
        reload=False
    )