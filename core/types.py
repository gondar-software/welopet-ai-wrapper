import uuid

from .enums import *
from .constants import *

class PodInfo:
    def __init__(
        self,
        port_mappings,
        public_ip
    ):
        self.port_mappings = port_mappings
        self.public_ip = public_ip

class PromptResult:
    def __init__(
        self,
        prompt_id: str,
        output_state: OutputState,
        output
    ):
        self.prompt_id = prompt_id
        self.output_state = output_state
        self.output = output

class Prompt:
    def __init__(
        self,
        prompt_id: str,
        workflow_type: WorkflowType,
        input_url: str
    ):
        self.prompt_id = prompt_id
        self.workflow_type = workflow_type
        self.input_url = input_url
        self.result: PromptResult = None

    def get_base_prompt(
        workflow_type: WorkflowType
    ):
        return Prompt(
            str(uuid.uuid4()),
            workflow_type,
            ORIGIN_IMAGE_URL
        )