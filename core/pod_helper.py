import time
import requests
import os
import subprocess

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
OUTPUT_DIRECTORY = os.getenv('OUTPUT_DIRECTORY')
SERVER_CHECK_RETRIES = int(os.getenv('SERVER_CHECK_RETRIES', 1200))
SERVER_CHECK_DELAY = int(os.getenv('SERVER_CHECK_DELAY', 500))

def create_pod_with_network_volume(
    network_volume_id, 
    pod_name, 
    gpu_type_ids=BASE_GPU_TYPE_IDS, 
    env_variables=BASE_ENV_VARIABLES, 
    gpu_count=BASE_GPU_COUNT, 
    ports=BASE_PORTS
):
    try:
        response = requests.post("https://rest.runpod.io/v1/pods",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {RUNPOD_API}"
            },
            json={
                "env": env_variables,
                "gpuCount": gpu_count,
                "gpuTypeIds": gpu_type_ids,
                "imageName": "runpod/vscode-server:0.0.0",
                "name": pod_name,
                "networkVolumeId": network_volume_id,
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
            "message": f"{e}"
        }

def get_pod_info(
    pod_id,
    retries=SERVER_CHECK_RETRIES, 
    delay=SERVER_CHECK_DELAY
):
    try:
        for i in range(retries):
            response = requests.get(f"https://rest.runpod.io/v1/pods/{pod_id}",
                headers={
                    "Authorization": f"Bearer {RUNPOD_API}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("portMappings", None) is None or data.get("publicIp", "") == "":
                    time.sleep(delay / 1000)
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
            "message": f"{e}"
        }

def delete_pod(
    pod_id
):
    try:
        response = requests.delete(f"https://rest.runpod.io/v1/pods/{pod_id}",
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
            "message": f"{e}"
        }

def command_to_pod(
    command, 
    public_ip, 
    port_mappings
):
    ssh_port = port_mappings.get("22", 22)
    command = (
        f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"root@{public_ip} -p {ssh_port} -i ./runpod.pem '{command}'"
    )
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print(result.stdout)
    
def run_comfyui_server(
    pod_id, 
    public_ip, 
    port_mappings
):
    command = (
        f"apt update && "
        f"apt install -y screen && "
        f"mkdir -p {OUTPUT_DIRECTORY} && "
        f"cd /workspace/ComfyUI && "
        f"screen -dmS comfyui ./venv/bin/python3 -m main --listen --disable-auto-launch --disable-metadata --output-directory {OUTPUT_DIRECTORY}"
    )
    command_to_pod(command, public_ip, port_mappings)
    if check_comfyui_server_started(pod_id):
        return True
    else:
        return False

def check_comfyui_server_started(
    pod_id, 
    retries=SERVER_CHECK_RETRIES, 
    delay=SERVER_CHECK_DELAY
):
    url = f"https://{pod_id}-8188.proxy.runpod.net/"
    for i in range(retries):
        try:
            response = requests.get(url)

            if response.status_code == 200:
                print(f"ComfyUI server is running on POD.")
                return True
        except requests.RequestException as e:
            return False

        time.sleep(delay / 1000)

    print(
        f"Failed to connect to server at {url} after {retries} attempts."
    )
    return False