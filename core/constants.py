import os
import json

with open("./env.json", 'r', encoding='utf-8') as file:
    envs = json.load(file)

BASE_GPU_TYPE_IDS = [
    "NVIDIA RTX A6000"
]
BASE_ENV_VARIABLES = {
}
BASE_GPU_COUNT = 1
BASE_PORTS = [
    "8188/tcp", # ComfyUI external port
    "8888/http", # JupyterLab port
    "22/tcp"     # ssh access port
]
RUNPOD_API = envs.get('RUNPOD_API', '')
OUTPUT_DIRECTORY = envs.get('OUTPUT_DIRECTORY', '')
SERVER_CHECK_RETRIES = envs.get('SERVER_CHECK_RETRIES', 600)
COLD_TIMEOUT_RETRIES = envs.get('COLD_TIMEOUT_RETRIES', 240)
TIMEOUT_RETRIES = envs.get('TIMEOUT_RETRIES', 60)
FREE_MAX_REMAINS = envs.get('FREE_MAX_REMAINS', 20)
SERVER_CHECK_DELAY = envs.get('SERVER_CHECK_DELAY', 500)
MIN_EXTRA_POS = [2, 1]
EXTRA_POD_RATE = 0.0075
ORIGIN_IMAGE_URL = envs.get('ORIGIN_IMAGE_URL', '')