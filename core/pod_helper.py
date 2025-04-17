import time
import requests
import os

BASE_GPU_TYPE_IDS = [
    "NVIDIA RTX A6000"
]
BASE_ENV_VARIABLES = {
}
BASE_GPU_COUNT = 1
BASE_PORTS = [
    "8188/http", # ComfyUI external port
    "8888/http", # JupyterLab port
    "22/tcp"     # ssh access port
]
RUNPOD_API = os.getenv('RUNPOD_API')

def create_pod_with_network_volume(
    networkVolumeId, 
    podName, 
    gpuTypeIds = BASE_GPU_TYPE_IDS, 
    envVariables = BASE_ENV_VARIABLES, 
    gpuCount = BASE_GPU_COUNT, 
    ports = BASE_PORTS
):
    try:
        response = requests.post("https://rest.runpod.io/v1/pods",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {RUNPOD_API}"
            },
            json={
                "env": envVariables,
                "gpuCount": gpuCount,
                "gpuTypeIds": gpuTypeIds,
                "imageName": "runpod/vscode-server:0.0.0",
                "name": podName,
                "networkVolumeId": networkVolumeId,
                "supportPublicIp": True,
                "ports": ports
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            return {
                "type": "success",
                "id": data.get("id", "")
            }
        else:
            print(f"Error creating pod: {response.status_code}")
            print(response.text)
            return {
                "type": "error",
                "message": f"{response.text}"
            }
    
    except Exception as e:
        print(e)
        return {
            "type": "error",
            "message": f"{e.message}"
        }

def get_pod_info(podId):
    try:
        while True:
            response = requests.get(f"https://rest.runpod.io/v1/pods/{podId}",
                headers={
                    "Authorization": f"Bearer {RUNPOD_API}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("portMappings", None) is None or data.get("publicIp", "") == "":
                    time.sleep(1000)
                    continue
                    
                return {
                    "type": "success",
                    "portMappings": data.get("portMappings", None),
                    "publicIp": data.get("publicIp", "")
                }
            else:
                print(f"Error getting pod info: {response.status_code}")
                print(response.text)
                return {
                    "type": "error",
                    "message": f"{response.text}"
                }
    
    except Exception as e:
        print(e)
        return {
            "type": "error",
            "message": f"{e.message}"
        }

def delete_pod(podId):
    try:
        response = requests.delete(f"https://rest.runpod.io/v1/pods/{podId}",
            headers={
                "Authorization": f"Bearer {RUNPOD_API}"
            }
        )
            
        if response.status_code == 200:
            return {
                "type": "success"
            }
        else:
            print(f"Error getting pod info: {response.status_code}")
            print(response.text)
            return {
                "type": "error",
                "message": f"{response.text}"
            }

    except Exception as e:
        print(e)
        return {
            "type": "error",
            "message": f"{e.message}"
        }