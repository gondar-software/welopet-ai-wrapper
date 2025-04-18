import threading
import time
import uuid
from queue import Queue
from threading import Thread

from .constants import *
from .pod import *
from .enums import *
from .types import *

class PodManager:
    def __init__(
        self, 
        volume_id: str, 
        gpu_type: GPUType,
        workflow_type: WorkflowType
    ):
        self.volume_id = volume_id
        self.gpu_type = gpu_type
        self.workflow_type = workflow_type
        self.pods = list[Pod]()
        self.queued_prompts = Queue[Prompt]()
        self.processing_prompts = dict[str, Prompt]()
        self.completed_prompts = dict[str, Prompt]()
        self.failed_prompts = dict[str, Prompt]()
        self.lock = threading.Lock()

    def calc_num_pods(
        self
    ) -> int:
        num_prompts = self.queued_prompts.qsize() + len(self.processing_prompts)
        num_pods = num_prompts + max(MIN_EXTRA_POS[self.gpu_type.value], num_prompts * EXTRA_POD_RATE)
        return round(num_pods)

    def process(
        self
    ):
        while True:
            with self.lock:
                num_pods = self.calc_num_pods()
                if num_pods > len(self.pods):
                    number = num_pods - len(self.pods)
                    for _ in range(number):
                        self.pods.append(Pod(
                            self.volume_id,
                            self.gpu_type,
                            self.workflow_type,
                            self
                        ))
                elif num_pods < len(self.pods):
                    for pod in self.pods:
                        if pod.state != PodState.Processing or pod.init:
                            self.pods.remove(pod)
                            continue

                for pod in self.pods:
                    if pod.state == PodState.Processing:
                        continue
                    if self.queued_prompts.empty():
                        break
                    prompt = self.queued_prompts.get()
                    thread = Thread(target=pod.queue_prompt, args=(prompt))
                    thread.start()

            time.sleep(SERVER_CHECK_DELAY / 1000)
        
    def queue_prompt(
        self,
        workflow_type: WorkflowType,
        input_url: str
    ) -> PromptResult:
        prompt_id = str(uuid.uuid4())
        prompt = Prompt(
            prompt_id,
            workflow_type,
            input_url
        )
        self.queued_prompts.put(prompt)

        while True:
            with self.lock:
                prompt = self.completed_prompts.get(
                    prompt_id,
                    self.failed_prompts.get(
                        prompt_id,
                        None
                    )
                )
                if prompt is not None:
                    return prompt.result
            time.sleep(SERVER_CHECK_DELAY / 1000)