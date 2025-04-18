import os
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from core.pod_manager import *

manager1 = PodManager(
    os.getenv('VOLUME_ID1', ""),
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

@app.post('/api2/v2/prompt')
async def prompt(query: dict):
    try:
        url = query.get("url", ORIGIN_IMAGE_URL)
        result = manager1.queue_prompt(
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
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app="main:app",
        host="localhost",
        port=8080,
        reload=False
    )