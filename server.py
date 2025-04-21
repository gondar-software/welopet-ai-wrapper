from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.pod_manager import *

_3d_cartoon_manager = None
# magicvideo_manager = None
logging_thread = None

def log_state():
    while True:
        if _3d_cartoon_manager:
            _3d_cartoon_state = _3d_cartoon_manager.get_state()
            print(f"{_3d_cartoon_state["state"].name}  \
  {_3d_cartoon_state["total_pod_num"]}  \
  {_3d_cartoon_state["initializing_pod_num"]}  \
  {_3d_cartoon_state["starting_pod_num"]}  \
  {_3d_cartoon_state["free_pod_num"]}  \
  {_3d_cartoon_state["processing_pod_num"]}  \
  {_3d_cartoon_state["completed_pod_num"]}  \
  {_3d_cartoon_state["terminated_pod_num"]}  \
  {_3d_cartoon_state["queued_prompt_num"]}  \
  {_3d_cartoon_state["processing_prompt_num"]}  \
  {_3d_cartoon_state["completed_prompt_num"]}  \
  {_3d_cartoon_state["failed_prompt_num"]}", end="\r")
            time.sleep(3)

def start_logging_thread():
    from threading import Thread
    
    global logging_thread

    logging_thread = Thread(target=log_state)
    logging_thread.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _3d_cartoon_manager, logging_thread
    
    _3d_cartoon_manager = PodManager(
        GPUType.RTXA6000,
        WorkflowType._3DCartoon
    )
    
    logging_thread = Thread(target=log_state, daemon=True)
    logging_thread.start()
    
    yield
    
    if _3d_cartoon_manager:
        _3d_cartoon_manager.stop()
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

@app.post('/api/v2/prompt')
def prompt(query: dict):
    try:
        url = query.get("url", ORIGIN_IMAGE_URL)
        workflow_id = query.get("workflow_id", 0)
        if workflow_id == 1 or \
            workflow_id == 2 or \
            workflow_id == 4:
            result = _3d_cartoon_manager.queue_prompt(
                WorkflowType(workflow_id),
                url
            )
            if result.output_state == OutputState.Completed:
                return Response(
                    content=result.output,
                    media_type=f"image/jpeg"
                )
            else: 
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

@app.post('/api/v2/stop')
def stop():
    if _3d_cartoon_manager:
        _3d_cartoon_manager.stop()
    if logging_thread:
        terminate_thread(logging_thread)

@app.post('/api/v2/restart')
def restart():
    if _3d_cartoon_manager:
        _3d_cartoon_manager.stop()
    if logging_thread:
        terminate_thread(logging_thread)
    logging_thread = Thread(target=log_state, daemon=True)
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