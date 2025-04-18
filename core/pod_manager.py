import threading
import time
import uuid
from queue import Queue
from threading import Thread
from collections import deque

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
        self.prompts_histories = deque([0, 0, 0, 0], maxlen=4)
        self.weights = [0.1, 0.2, 0.3, 0.4]

        process_thread = Thread(target=self.process)
        process_thread.start()
        manage_thread = Thread(target=self.manage_pods)
        manage_thread.start()

    def calc_num_pods(
        self
    ) -> int:
        num_prompts = self.queued_prompts.qsize() + len(self.processing_prompts)
        self.prompts_histories.append(num_prompts)
        return round(sum(value * weight for value, weight in zip(self.prompts_histories, self.weights)) + max(num_prompts * EXTRA_POD_RATE, MIN_EXTRA_POS[self.gpu_type.value]))

    def manage_pods(
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
                        if pod.state == PodState.Starting or \
                            pod.state == PodState.Free or \
                            (pod.init and pod.state == PodState.Processing):
                            pod.destroy()
                            self.pods.remove(pod)
                            if num_pods >= len(self.pods):
                                break
            time.sleep(2)

    def process(
        self
    ):
        while True:
            with self.lock:
                for pod in self.pods:
                    if pod.state == PodState.Processing:
                        continue
                    elif pod.state == PodState.Completed:
                        if pod.current_prompt.result.output_state == OutputState.Completed:
                            self.completed_prompts[pod.current_prompt.prompt_id] = pod.current_prompt
                            self.processing_prompts.pop(pod.current_prompt.prompt_id)
                        else:
                            self.failed_prompts[pod.current_prompt.prompt_id] = pod.current_prompt
                            self.processing_prompts.pop(pod.current_prompt.prompt_id)
                        pod.state = PodState.Free

                    if pod.state == PodState.Free:
                        if self.queued_prompts.empty():
                            break
                        prompt = self.queued_prompts.get()
                        self.processing_prompts[prompt.prompt_id] = prompt
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