import uuid
import threading

from .enums import *
from .pod_helper import *
from .comfyui_helper import *
from .utils import *

class Pod:
    def __init__(
        self, 
        gpu_type: GPUType, 
        workflow_type: WorkflowType
    ):
        self.volume_id = os.getenv(f"VOLUME_ID{workflow_type.value}", "")
        self.gpu_type = gpu_type
        self.workflow_type = workflow_type
        self.init = True
        self.pod_id = ""
        self.pod_info = None
        self.state = PodState.Initializing
        self.current_prompt = None
        self.init_thread = threading.Thread(target=self.initialize)
        self.init_thread.start()
        
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
                self.pod_info.public_ip,
                self.pod_info.port_mappings
            )

            self.state = PodState.Processing
            self.queue_prompt(Prompt.get_base_prompt(self.workflow_type))

            self.state = PodState.Free
            self.init = False
        except Exception as e:
            print(f"Error initializing pod: {str(e)}")
            self.state = PodState.Terminated

    def queue_prompt(
        self, 
        prompt: Prompt,
    ):
        if self.state != PodState.Free and not self.init:
            return self.state

        self.current_prompt = prompt
        self.state = PodState.Processing
        comfyui_helper = ComfyUIHelper(
            f"http://{self.pod_info.public_ip}:{self.pod_info.port_mappings.get('8188', 8188)}",
            f"ws://{self.pod_info.public_ip}:{self.pod_info.port_mappings.get('8188', 8188)}"
        )
        try:
            result = comfyui_helper.prompt(prompt)

            if self.init:
                self.state = PodState.Free
                return
            else:
                self.current_prompt.result = PromptResult(
                    self.current_prompt.prompt_id,
                    OutputState.Completed,
                    result
                )
        except Exception as e:
            print(str(e))
            if self.init:
                self.state = PodState.Terminated
                return
            else:
                self.current_prompt.result = PromptResult(
                    self.current_prompt.prompt_id,
                    OutputState.Failed,
                    str(e)
                )

        self.state = PodState.Completed

    def destroy(
        self
    ):
        try:
            delete_pod(self.pod_id)
            if self.init_thread:
                terminate_thread(self.init_thread)
        except:
            pass
        