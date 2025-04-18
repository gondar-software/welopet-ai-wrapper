import os
from dotenv import load_dotenv

load_dotenv()

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
RUNPOD_API = os.getenv('RUNPOD_API')
OUTPUT_DIRECTORY = os.getenv('OUTPUT_DIRECTORY')
SERVER_CHECK_RETRIES = int(os.getenv('SERVER_CHECK_RETRIES', 1200))
SERVER_CHECK_DELAY = int(os.getenv('SERVER_CHECK_DELAY', 500))
MIN_EXTRA_POS = [2, 1, 1]
EXTRA_POD_RATE = 0.0075
ORIGIN_IMAGE_URL = os.getenv('ORIGIN_IMAGE_URL', "")