import uuid
import threading

from .enums import *
from .pod_helper import *
from .comfyui_helper import *
from .pod_manager import *

class Pod:
    def __init__(
        self, 
        volume_id: str, 
        gpu_type: GPUType, 
        workflow_type: WorkflowType
    ):
        self.volume_id = volume_id
        self.gpu_type = gpu_type
        self.workflow_type = workflow_type
        self.init = True
        self.pod_id = ""
        self.pod_info = None
        self.state = PodState.Initializing
        self.cached_prompt_output = ""
        thread = threading.Thread(target=self.initialize)
        thread.start()
        
    def initialize(
        self
    ):
        try:
            self.state = PodState.Initializing
            self.pod_id = create_pod_with_network_volume(
                self.volume_id,
                f"pod-{self.workflow_type.name}-{uuid.uuid4()}",
                gpu_type_ids=[
                    self.gpu_type.value
                ]
            )
            self.pod_info = get_pod_info(self.pod_id)

            self.state = PodState.Starting
            run_comfyui_server(
                self.pod_id,
                self.pod_info.public_ip,
                self.pod_info.port_mappings
            )

            self.init = False
        except Exception as e:
            print(f"Error initializing pod: {str(e)}")
            try:
                delete_pod(self.pod_id)
            except:
                pass

    def queue_prompt(
        self, 
        prompt: Prompt,
    ) -> PodState | str:
        if self.state != PodState.Free and not self.init:
            return self.state
        
        try:
            self.state = PodState.Processing
            comfyui_helper = ComfyUIHelper(
                f"https://{self.pod_id}-8188.proxy.runpod.net",
                self.workflow_type
            )
            self.prompt_id = comfyui_helper.prompt(prompt)
        except Exception as e:
            print(f"Error queueing prompt: {str(e)}")
            self.state = PodState.Free
            return self.state
        