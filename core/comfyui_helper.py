import json
import urllib
import time

from .enums import *
from .types import *
from .constants import *

class ComfyUIHelper:
    def __init__(
        self, 
        server_url: str, 
        workflow_type: WorkflowType
    ):
        self.url = server_url
        self.type = workflow_type
        self.progress = 0

    def prompt(
        self, 
        prompt: Prompt
    ) -> str:
        workflow = self.apply_input(workflow, input_url)
        queued_workflow = queued_workflow(workflow)
        prompt_id = queued_workflow.get("prompt_id", "")

        retries = 0
        while retries < SERVER_CHECK_RETRIES:
            history = self.get_history(prompt_id)

            if prompt_id in history:
                if history[prompt_id].get("outputs"):
                    break
                else:
                    raise Exception("Excusion failed")
            else:
                time.sleep(SERVER_CHECK_DELAY / 1000)
                retries += 1
        else:
            raise Exception("Max retries reached while waiting for image generation")

    

    def get_history(self, prompt_id):
        with urllib.request.urlopen(f"{self.url}/{prompt_id}") as response:
            return json.loads(response.read())

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