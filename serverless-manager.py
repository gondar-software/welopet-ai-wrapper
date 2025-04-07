import runpod
import requests
import time
import os
from collections import deque
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API = os.getenv('RUNPOD_API')
ENDPOINT_ID1 = os.getenv('ENDPOINT_ID1')

runpod.api_key = RUNPOD_API
requests_history = deque(
    [0, 0, 0, 0],
    maxlen=4
)
weights = [0.1, 0.2, 0.3, 0.4]
extra_rate = 0.075

def calc_workers(endpointId):
    endpoint = runpod.Endpoint(endpointId)
    endpoint_health = endpoint.health()
    num_requests = endpoint_health["jobs"]["inProgress"] + endpoint_health["jobs"]["inQueue"]

    requests_history.append(num_requests)
    workers= min(150, max(round(sum(value * weight for value, weight in zip(requests_history, weights)) + num_requests * extra_rate), 2))

    return workers

def update_endpoint(endpointId, workers):
    try:
        requests.patch(
            f"https://rest.runpod.io/v1/endpoints/{endpointId}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {RUNPOD_API}"
            },
            json={
                # "allowedCudaVersions": [
                #     "12.7"
                # ],
                # "cpuFlavorIds": [
                #     "cpu3c"
                # ],
                # "dataCenterIds": [
                #     "EU-RO-1",
                #     "CA-MTL-1"
                # ],
                # "executionTimeoutMs": 600000,
                # "flashboot": true,
                # "gpuCount": 1,
                # "gpuTypeIds": [
                #     "NVIDIA GeForce RTX 4090"
                # ],
                # "idleTimeout": 5,
                # "name": "",
                # "networkVolumeId": "",
                # "scalerType": "QUEUE_DELAY",
                # "scalerValue": 4,
                # "templateId": "30zmvf89kd",
                # "vcpuCount": 2,
                "workersMax": workers,
                "workersMin": workers
            }
        )
    
    except Exception as e:
        print(e)


if __name__ == "__main__":
    try:
        while True:
            workers = calc_workers(ENDPOINT_ID1)
            print(workers)
            update_endpoint(ENDPOINT_ID1, workers)
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nStopping manager...")
