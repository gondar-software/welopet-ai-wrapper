import uuid
import threading

from .enums import *
from .pod_helper import *

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
        thread = threading.Thread(target=self.initialize)
        thread.start()

    def initialize(self):
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

        self.state = PodState.Free



