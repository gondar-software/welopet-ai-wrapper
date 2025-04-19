import json
import time
import websocket
from urllib import request, parse
from PIL import Image
from io import BytesIO

from .enums import *
from .types import *
from .constants import *

class ComfyUIHelper:
    def __init__(
        self, 
        server_url: str, 
        ws_url: str
    ):
        self.url = server_url
        self.ws_url = ws_url
        self.progress = 0

    def prompt(
        self, 
        prompt: Prompt
    ) -> str:
        with open(f"./workflows/{prompt.workflow_type.value}.json", 'r', encoding='utf-8') as file:
            workflow = json.load(file)
        workflow = self.apply_input(workflow, prompt.input_url)

        ws, client_id = self.open_websocket_connection()
        queued_workflow = self.queue_workflow(workflow, client_id)
        prompt_id = queued_workflow.get("prompt_id", "")

        self.track_progress(ws, prompt_id)
        
        history = self.get_history(prompt_id)[prompt_id]
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    output = self.get_data(image['filename'], image['subfolder'], image['type'])
                    png_buffer = BytesIO(output)
                    with Image.open(png_buffer) as img:
                        if img.mode in ('RGBA', 'LA'):
                            img = img.convert('RGB')
                        
                        jpg_buffer = BytesIO()
                        img.save(jpg_buffer, format='JPEG', quality=85)

                        return jpg_buffer.getvalue()
            elif 'gifs' in node_output:
                for video in node_output['gifs']:
                    return self.get_data(video['filename'], video['subfolder'], video['type'])

    def get_data(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = parse.urlencode(data)
        with request.urlopen(f"{self.url}/view?{url_values}") as response:
            return response.read()

    def get_history(self, prompt_id):
        with request.urlopen(f"{self.url}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def apply_input(
        self, 
        workflow, 
        input_url: str
    ):
        workflow["111"]["inputs"]["url_or_path"] = input_url
        return workflow

    def open_websocket_connection(
        self
    ):
        client_id=str(uuid.uuid4())
        ws = websocket.WebSocket()
        ws.connect(f"{self.ws_url}/ws?clientId={client_id}")
        return ws, client_id

    def queue_workflow(
        self, 
        workflow,
        client_id: str
    ):
        data = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
        headers = {'Content-Type': 'application/json'}
        req = request.Request(f"{self.url}/prompt", data=data, headers=headers)

        return json.loads(request.urlopen(req).read())

    
    def track_progress(
        self,
        ws, 
        prompt_id
    ):
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']

                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break
            else:
                continue
        return