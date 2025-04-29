import json
import websocket
import uuid
from urllib import request, parse
from PIL import Image
from io import BytesIO
from typing import Dict

from .constants import *
from .types import *

class ComfyUIHelper:
    def __init__(self, server_url: str, ws_url: str):
        self.url = server_url.rstrip('/')
        self.ws_url = ws_url.rstrip('/')
        self._workflow_cache: Dict[str, Dict] = {}

    def prompt(self, prompt: Prompt, is_init: bool = False) -> bytes:
        """Execute a prompt and return the resulting image/video data."""
        try:
            workflow = self._get_workflow(prompt.workflow_type)
            workflow = self._apply_input(workflow, prompt.input_url)

            ws, client_id = self._open_websocket_connection()
            prompt_id = self._queue_workflow(workflow, client_id)
            self._track_progress(ws, prompt_id, is_init)
            return self._get_output_data(prompt_id)
        except Exception as e:
            raise RuntimeError(f"Prompt execution failed: {str(e)}")

    def _get_workflow(self, workflow_type: WorkflowType) -> Dict:
        """Get workflow JSON with caching."""
        if workflow_type.value not in self._workflow_cache:
            with open(f"./workflows/{workflow_type.value}.json", 'r', encoding='utf-8') as file:
                self._workflow_cache[workflow_type.value] = json.load(file)
        return self._workflow_cache[workflow_type.value]

    def _apply_input(self, workflow: Dict, input_url: str) -> Dict:
        """Apply input URL to workflow."""
        workflow["111"]["inputs"]["url_or_path"] = input_url
        return workflow
    
    def _open_websocket_connection(self):
        client_id=str(uuid.uuid4())
        ws = websocket.WebSocket()
        ws.connect(f"{self.ws_url}/ws?clientId={client_id}")
        return ws, client_id

    def _queue_workflow(self, workflow: Dict, client_id: str) -> str:
        """Queue workflow and return prompt ID."""
        data = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
        req = request.Request(
            f"{self.url}/prompt",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        response = request.urlopen(req)
        return json.loads(response.read()).get("prompt_id", "")

    def _track_progress(self, ws: websocket.WebSocket, prompt_id: str, is_init: bool) -> None:
        """Track execution progress via WebSocket."""
        max_retries = COLD_TIMEOUT_RETRIES if is_init else TIMEOUT_RETRIES
        for _ in range(max_retries):
            try:
                message = json.loads(ws.recv())
                msg_type = message.get('type', '')
                
                if msg_type == 'executing':
                    if (message['data']['node'] is None and 
                        message['data']['prompt_id'] == prompt_id):
                        return
                elif msg_type == 'execution_success':
                    if message['data']['prompt_id'] == prompt_id:
                        return
                elif msg_type == 'execution_error':
                    raise RuntimeError(message['data']['exception_message'])
                    continue
                elif msg_type == 'execution_interrupted':
                    raise RuntimeError('Execution interrupted')
            except (websocket.WebSocketTimeoutException, json.JSONDecodeError):
                continue
        raise TimeoutError("Execution timed out")

    def _get_output_data(self, prompt_id: str) -> bytes:
        """Get output data from prompt results."""
        history = self._get_history(prompt_id).get(prompt_id)
        if not history:
            raise RuntimeError("No execution history found")

        for node_output in history['outputs'].values():
            if 'images' in node_output:
                return self._process_image_output(node_output['images'])
            elif 'gifs' in node_output:
                return self._get_binary_output(node_output['gifs'])
        raise RuntimeError("No valid output found in execution results")

    def _get_history(self, prompt_id: str) -> Dict:
        """Get execution history for a prompt."""
        with request.urlopen(f"{self.url}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def _process_image_output(self, images: list) -> bytes:
        """Process image output and convert to JPEG."""
        for image in images:
            img_data = self._get_binary_output([image])
            with Image.open(BytesIO(img_data)) as img:
                if img.mode in ('RGBA', 'LA'):
                    img = img.convert('RGB')
                jpg_buffer = BytesIO()
                img.save(jpg_buffer, format='JPEG', quality=85)
                return jpg_buffer.getvalue()
        raise RuntimeError("No valid image output found")

    def _get_binary_output(self, items: list) -> bytes:
        """Get binary data for output items."""
        for item in items:
            params = parse.urlencode({
                "filename": item['filename'],
                "subfolder": item['subfolder'],
                "type": item['type']
            })
            with request.urlopen(f"{self.url}/view?{params}") as response:
                return response.read()
        raise RuntimeError("No binary data available")