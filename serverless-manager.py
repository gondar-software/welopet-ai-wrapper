import runpod
import requests
import time
import os
from collections import deque
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API = os.getenv('RUNPOD_API')

MAX_WORKERS = [150, 100, 20]
MIN_WORKERS = [2, 1, 1]
IDLE_TIMEOUTS = [5, 30, 30]
NUM_ENDPOINT = 3

runpod.api_key = RUNPOD_API
requests_histories = [deque([0, 0, 0, 0], maxlen=4) for i in range(NUM_ENDPOINT)]
weights = [0.1, 0.2, 0.3, 0.4]
extra_rate = 0.0075

def calc_workers(endpointId):
    endpoint = runpod.Endpoint(os.getenv(f'ENDPOINT_ID{endpointId + 1}'))
    endpoint_health = endpoint.health()
    num_requests = endpoint_health["jobs"]["inProgress"] + endpoint_health["jobs"]["inQueue"]

    requests_histories[endpointId].append(num_requests)
    workers = min(MAX_WORKERS[endpointId], 
        round(sum(value * weight for value, weight in zip(requests_histories[endpointId], weights)) + max(num_requests * extra_rate, MIN_WORKERS[endpointId])))

    return workers

def update_endpoint(endpointId, workers):
    try:
        requests.patch(
            f"https://rest.runpod.io/v1/endpoints/{os.getenv(f'ENDPOINT_ID{endpointId + 1}')}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {RUNPOD_API}"
            },
            json={
                "idleTimeout": IDLE_TIMEOUTS[endpointId],
                "workersMax": MAX_WORKERS[endpointId],
                "workersMin": workers
            }
        )
    
    except Exception as e:
        print(e)


if __name__ == "__main__":
    try:
        while True:
            for i in range(NUM_ENDPOINT):
                workers = calc_workers(i)
                update_endpoint(i, workers)
                
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping manager...")
