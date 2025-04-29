import uuid
import threading
import time
import os
from typing import Optional

from .enums import *
from .pod_helper import *
from .comfyui_helper import *
from .utils import *
from .constants import *

class Pod:
    def __init__(self, gpu_type: GPUType, volume_type: VolumeType):
        self.pod_helper = PodHelper(RUNPOD_API)
        self.volume_id = self._get_volume_id(volume_type)
        self.gpu_type = gpu_type
        self.volume_type = volume_type
        self._lock = threading.Lock()
        self._state = PodState.Initializing
        self._init = True
        self.pod_id = ""
        self.pod_info = None
        self.current_prompt = None
        self.count = 0
        self._init_thread = threading.Thread(
            target=self._initialize_pod,
            name=f"PodInit-{volume_type.name}-{uuid.uuid4()}"
        )
        self._init_thread.daemon = True
        self._init_thread.start()

    @property
    def state(self) -> PodState:
        with self._lock:
            return self._state

    @state.setter
    def state(self, value: PodState) -> None:
        with self._lock:
            self._state = value

    @property
    def init(self) -> bool:
        with self._lock:
            return self._init

    @init.setter
    def init(self, value: bool) -> None:
        with self._lock:
            self._init = value

    def _get_volume_id(self, volume_type: VolumeType) -> str:
        """Get volume ID from environment with validation"""
        volume_id = os.getenv(f"VOLUME_ID{volume_type.value}", "")
        if not volume_id:
            raise ValueError(f"Volume ID not found for type {volume_type}")
        return volume_id

    def _initialize_pod(self) -> None:
        """Thread-safe pod initialization"""
        try:
            self.state = PodState.Initializing
            self.pod_id = self._create_pod()
            self.pod_info = self._wait_for_pod_info()
            self._setup_comfyui_server()
            self._warm_up_pod()
        except Exception as e:
            print(f"Pod initialization failed: {e}")
            self.state = PodState.Terminated

    def _create_pod(self) -> str:
        """Create pod and return pod ID"""
        return self.pod_helper.create_pod(
            self.volume_id,
            f"pod-{self.volume_type.name}-{uuid.uuid4()}",
            gpu_type_ids=[self.gpu_type.value]
        )

    def _wait_for_pod_info(self, retries: int = POD_REQUEST_RETRIES, delay: float = 3.0) -> PodInfo:
        """Wait for pod info to become available"""
        for attempt in range(retries):
            try:
                pod_info = self.pod_helper.get_pod_info(self.pod_id)
                if pod_info and pod_info.public_ip and pod_info.port_mappings:
                    self.count = 0
                    self.state = PodState.Starting
                    return pod_info
            except Exception as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"Failed to get pod info after {retries} attempts: {e}")
            time.sleep(delay)
        raise RuntimeError("Pod info not available")

    def _setup_comfyui_server(self) -> None:
        """Set up ComfyUI server with retries"""
        self.pod_helper.setup_comfyui_server(
            self.pod_info.public_ip,
            self.pod_info.port_mappings
        )
        self.state = PodState.Processing

    def _warm_up_pod(self) -> None:
        """Warm up pod with base prompt"""
        try:
            self.queue_prompt(Prompt.get_base_prompt(self.volume_type))
            with self._lock:
                self.count = 0
                self._init = False
                self._state = PodState.Free
        except Exception as e:
            print(f"Pod warm-up failed: {e}")
            self.state = PodState.Terminated

    def queue_prompt(self, prompt: Prompt) -> Optional[PodState]:
        """Process a prompt in a thread-safe manner"""
        with self._lock:
            self.current_prompt = prompt
            self._state = PodState.Processing

        comfyui_helper = ComfyUIHelper(
            f"http://{self.pod_info.public_ip}:{self.pod_info.port_mappings.get('8188', 8188)}",
            f"ws://{self.pod_info.public_ip}:{self.pod_info.port_mappings.get('8188', 8188)}"
        )

        try:
            result = comfyui_helper.prompt(prompt, self.init)
            with self._lock:
                self.count = 0

                if self._init:
                    self._state = PodState.Free
                    return None
                
                prompt.result = PromptResult(
                    prompt.prompt_id,
                    OutputState.Completed,
                    result
                )
        except Exception as e:
            print(f"Prompt processing failed: {e}")
            with self._lock:
                if self._init:
                    self._state = PodState.Terminated
                    return None
                
                prompt.result = PromptResult(
                    prompt.prompt_id,
                    OutputState.Failed,
                    str(e)
                )

        with self._lock:
            self.count = 0
            self._state = PodState.Completed
            return None

    def destroy(self) -> bool:
        """Safely destroy the pod"""
        try:
            if self._init_thread and self._init_thread.is_alive():
                terminate_thread(self._init_thread)
            return self.pod_helper.delete_pod(self.pod_id)
        except Exception as e:
            print(f"Pod destruction failed: {e}")
            return False