import time
import requests
import subprocess

from .constants import *
from .types import *

def create_pod_with_network_volume(
    network_volume_id: str, 
    pod_name: str, 
    gpu_type_ids: list = BASE_GPU_TYPE_IDS, 
    env_variables: dict = BASE_ENV_VARIABLES, 
    gpu_count: int = BASE_GPU_COUNT, 
    ports: list = BASE_PORTS
) -> str:
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
        return data.get("id", "")
    else:
        raise Exception(response)

def get_pod_info(
    pod_id: str,
    retries: int = SERVER_CHECK_RETRIES, 
    delay: int = SERVER_CHECK_DELAY
) -> PodInfo:
    for _ in range(retries):
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
                
            return PodInfo(
                data.get("portMappings", None),
                data.get("publicIp", "")
            )
        else:
            raise Exception(response)

def delete_pod(
    pod_id: str
):
    response = requests.delete(f"https://rest.runpod.io/v1/pods/{pod_id}",
        headers={
            "Authorization": f"Bearer {RUNPOD_API}"
        }
    )
        
    if response.status_code == 200:
        pass
    else:
        raise Exception(response)

def command_to_pod(
    command: str, 
    public_ip: str, 
    port_mappings: dict
):
    ssh_port = port_mappings.get("22", 22)
    command = (
        f"ssh -o StrictHostKeyChecking=no "
        f"root@{public_ip} -p {ssh_port} -i ./runpod.pem '{command}'"
    )
    subprocess.run(command, shell=True, capture_output=True, text=True)
    
def run_comfyui_server(
    public_ip: str, 
    port_mappings: dict
):
    command = (
        f"apt update && "
        f"apt install -y screen && "
        f"mkdir -p {OUTPUT_DIRECTORY} && "
        f"chmod 666 {OUTPUT_DIRECTORY} && "
        f"cd /workspace/ComfyUI && "
        f"screen -dmS comfyui ./venv/bin/python3 -m main --listen --disable-metadata --output-directory {OUTPUT_DIRECTORY}"
    )
    command_to_pod(command, public_ip, port_mappings)
    check_comfyui_server_started(public_ip, port_mappings)
    pass
    
def check_comfyui_server_started(
    public_ip,
    port_mappings, 
    retries=SERVER_CHECK_RETRIES, 
    delay=SERVER_CHECK_DELAY
):
    url = f"http://{public_ip}:{port_mappings.get('8188', 8188)}"
    for _ in range(retries):
        try:
            response = requests.get(url)

            if response.status_code == 200:
                return
        except:
            pass

        time.sleep(delay / 1000)

    raise Exception(f"Failed to connect to server at {url} after {retries} attempts.")