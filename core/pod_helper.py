import time
import requests
import subprocess
from typing import Dict, List
from requests.exceptions import RequestException

from .constants import *
from .types import *

class PodHelper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def create_pod(
        self,
        network_volume_id: str,
        pod_name: str,
        gpu_type_ids: List[str] = BASE_GPU_TYPE_IDS,
        env_variables: Dict = BASE_ENV_VARIABLES,
        gpu_count: int = BASE_GPU_COUNT,
        ports: List[str] = BASE_PORTS,
        timeout: int = NORMAL_REQUEST_TIMEOUT
    ) -> str:
        """Create a new pod with network volume."""
        payload = {
            "env": env_variables,
            "gpuCount": gpu_count,
            "gpuTypeIds": gpu_type_ids,
            "imageName": "runpod/vscode-server:0.0.0",
            "name": pod_name,
            "networkVolumeId": network_volume_id,
            "supportPublicIp": True,
            "ports": ports
        }

        while True:
            try:
                response = self.session.post(
                    "https://rest.runpod.io/v1/pods",
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()
                return response.json().get("id", "")
            except:
                time.sleep(1)
                continue

    def get_pod_info(
        self,
        pod_id: str
    ) -> PodInfo:
        """Get information about a specific pod."""
        while True:
            try:
                response = self.session.get(
                    f"https://rest.runpod.io/v1/pods/{pod_id}"
                )
                response.raise_for_status()
                data = response.json()

                if data.get("portMappings") and data.get("publicIp"):
                    return PodInfo(
                        port_mappings=data["portMappings"],
                        public_ip=data["publicIp"]
                    )
                
                time.sleep(1)
            except RequestException as e:
                time.sleep(1)
                continue

    def delete_pod(self, pod_id: str, timeout: int = NORMAL_REQUEST_TIMEOUT) -> bool:
        """Delete a pod."""
        while True:
            try:
                response = self.session.delete(
                    f"https://rest.runpod.io/v1/pods/{pod_id}",
                    timeout=timeout
                )
                response.raise_for_status()
                if response.status_code == 200:
                    return
            except:
                time.sleep(2)

    @staticmethod
    def execute_ssh_command(
        command: str,
        public_ip: str,
        port_mappings: Dict[str, int],
        timeout: int = NORMAL_REQUEST_TIMEOUT
    ) -> subprocess.CompletedProcess:
        """Execute a command on the pod via SSH."""
        ssh_port = port_mappings.get("22", 22)
        ssh_command = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", str(ssh_port),
            "-i", "./runpod.pem",
            f"root@{public_ip}",
            command
        ]
        
        try:
            return subprocess.run(
                ssh_command,
                check=True,
                timeout=timeout,
                capture_output=True,
                text=True
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"SSH command timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"SSH command failed: {e.stderr}")

    def setup_comfyui_server(
        self,
        public_ip: str,
        port_mappings: Dict[str, int],
        retries: int = SERVER_CHECK_RETRIES,
        check_interval: int = SERVER_CHECK_DELAY,
        timeout: int = NORMAL_REQUEST_TIMEOUT
    ) -> bool:
        """Set up and verify ComfyUI server."""
        setup_commands = [
            "apt update -qq",
            "apt install -y screen",
            f"mkdir -p {OUTPUT_DIRECTORY}",
            f"chmod 666 {OUTPUT_DIRECTORY}",
            "cd /workspace/ComfyUI && "
            "screen -dmS comfyui /workspace/ComfyUI/venv/bin/python3 "
            f"/workspace/ComfyUI/main.py --listen --disable-metadata --output-directory {OUTPUT_DIRECTORY}"
        ]

        for cmd in setup_commands:
            self.execute_ssh_command(cmd, public_ip, port_mappings)

        comfyui_port = port_mappings.get("8188", 8188)
        url = f"http://{public_ip}:{comfyui_port}"
        
        for attempt in range(retries):
            try:
                response = requests.get(url, timeout=timeout)
                if response.status_code == 200:
                    return True
            except RequestException:
                pass
            
            time.sleep(check_interval / 1000.)

        raise RuntimeError(f"ComfyUI server not ready after {retries * check_interval / 1000.} seconds")