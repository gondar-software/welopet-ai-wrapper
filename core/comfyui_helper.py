import json
import urllib

from .enums import *
from .types import *

class ComfyUIHelper:
    def __init__(
        self, 
        server_url: str, 
        workflow_type: WorkflowType
    ):
        self.url = server_url
        self.type = workflow_type
        self.prompt_id = ""
        self.progress = 0

    def prompt(
        self, 
        workflow: dict, 
        input_url: str
    ) -> str:
        workflow = self.apply_input(workflow, input_url)
        queued_workflow = queued_workflow(workflow)
        self.prompt_id = queued_workflow.get("prompt_id", "")

        return self.prompt_id

    def apply_input(
        self, 
        workflow: dict, 
        input_url: str
    ) -> dict:
        workflow["111"]["inputs"]["url_or_path"] = input_url
        return workflow

    def queue_workflow(
        self, 
        workflow: dict
    ) -> dict:
        data = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(f"{self.url}/prompt", data=data)

        return json.loads(urllib.request.urlopen(req).read())