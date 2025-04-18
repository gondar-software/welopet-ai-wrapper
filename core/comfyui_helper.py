import json
import time
from urllib import request, parse

from .enums import *
from .types import *
from .constants import *

class ComfyUIHelper:
    def __init__(
        self, 
        server_url: str, 
    ):
        self.url = server_url
        self.progress = 0

    def prompt(
        self, 
        prompt: Prompt
    ) -> str:
        with open(f"./workflows/{prompt.workflow_type.value}.json", 'r', encoding='utf-8') as file:
            workflow = json.load(file)
        workflow = self.apply_input(workflow, prompt.input_url)

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
            raise Exception("Max retries reached while waiting for generation")
        
        history = history[prompt_id]
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    output = self.get_data(image['filename'], image['subfolder'], image['type'])
            elif 'gifs' in node_output:
                for video in node_output['gifs']:
                    output = self.get_data(video['filename'], video['subfolder'], video['type'])

        print(output)

    def get_data(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = parse.urlencode(data)
        with request.urlopen("http://{}/view?{}".format(self.url, url_values)) as response:
            return response.read()

    def get_history(self, prompt_id):
        with request.urlopen(f"{self.url}/{prompt_id}") as response:
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
        req = request.Request(f"{self.url}/prompt", data=data)

        return json.loads(request.urlopen(req).read())