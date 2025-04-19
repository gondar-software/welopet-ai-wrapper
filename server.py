from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from core.pod_manager import *

easycontrol_manager = PodManager(
    GPUType.RTXA6000,
    WorkflowType.Ghibli
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def log_state():
    while True:
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
        easycontrol_manager.restart()
        return {"message": "OK"}
    except Exception as e:
        raise HTTPException

    
if __name__ == "__main__":
    import uvicorn
    from threading import Thread

    logging_thread = Thread(target=log_state)
    logging_thread.start()

    uvicorn.run(
        app="main:app",
        host="localhost",
        port=8080,
        reload=False
    )