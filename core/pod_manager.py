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
from .utils import *

class PodManager:
    def __init__(
        self, 
        gpu_type: GPUType,
        volume_type: VolumeType
    ):
        self.gpu_type = gpu_type
        self.volume_type = volume_type
        self.pods = list[Pod]()
        self.queued_prompts = Queue[Prompt]()
        self.processing_prompts = dict[str, Prompt]()
        self.completed_prompts = dict[str, Prompt]()
        self.failed_prompts = dict[str, Prompt]()
        self.lock = threading.Lock()
        self.prompts_histories = deque([0, 0, 0, 0], maxlen=4)
        self.weights = [0.1, 0.2, 0.3, 0.4]

        self.process_thread = Thread(target=self.process)
        self.process_thread.start()
        self.manage_thread = Thread(target=self.manage_pods)
        self.manage_thread.start()

        self.state = PodManagerState.Running

    def get_state(
        self
    ):
        with self.lock:
            total_pod_num = len(self.pods)
            initializing_pod_num = sum(1 for pod in self.pods if pod.state == PodState.Initializing)
            starting_pod_num = sum(1 for pod in self.pods if pod.state == PodState.Starting)
            free_pod_num = sum(1 for pod in self.pods if pod.state == PodState.Free)
            processing_pod_num = sum(1 for pod in self.pods if pod.state == PodState.Processing)
            completed_pod_num = sum(1 for pod in self.pods if pod.state == PodState.Completed)
            terminated_pod_num = sum(1 for pod in self.pods if pod.state == PodState.Terminated)

            queued_prompt_num = self.queued_prompts.qsize()
            processing_prompt_num = len(self.processing_prompts)
            completed_prompt_num = len(self.completed_prompts)
            failed_prompt_num = len(self.failed_prompts)

        return {
            "state": self.state,
            "total_pod_num": total_pod_num,
            "initializing_pod_num": initializing_pod_num,
            "starting_pod_num": starting_pod_num,
            "free_pod_num": free_pod_num,
            "processing_pod_num": processing_pod_num,
            "completed_pod_num": completed_pod_num,
            "terminated_pod_num": terminated_pod_num,
            "queued_prompt_num": queued_prompt_num,
            "processing_prompt_num": processing_prompt_num,
            "completed_prompt_num": completed_prompt_num,
            "failed_prompt_num": failed_prompt_num,
        }

    def calc_num_pods(
        self
    ) -> int:
        num_prompts = self.queued_prompts.qsize() + len(self.processing_prompts)
        self.prompts_histories.append(num_prompts)
        return round(sum(value * weight for value, weight in zip(self.prompts_histories, self.weights)) + max(num_prompts * EXTRA_POD_RATE, MIN_EXTRA_POS[self.volume_type.value]))

    def manage_pods(
        self
    ):
        try:
            while True:
                with self.lock:
                    num_pods = self.calc_num_pods()

                    for pod in self.pods:
                        if pod.state == PodState.Terminated:
                            pod.destroy()
                            self.pods.remove(pod)
                            continue

                    if num_pods > len(self.pods):
                        number = num_pods - len(self.pods)
                        for _ in range(number):
                            self.pods.append(Pod(
                                self.gpu_type,
                                self.volume_type
                            ))
                    elif num_pods < len(self.pods):
                        if len(self.pods) > 0:
                            pod = self.pods[-1]
                            if pod and (pod.state == PodState.Starting or \
                                pod.state == PodState.Free or \
                                (pod.init and pod.state == PodState.Processing)):
                                pod.destroy()
                                self.pods.remove(pod)
                            if num_pods >= len(self.pods):
                                break
                        else:
                            break

                time.sleep(2)
        except:
            pass

    def process(
        self
    ):
        try:
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
                            thread = Thread(target=pod.queue_prompt, args=[prompt])
                            thread.start()

                time.sleep(SERVER_CHECK_DELAY / 1000)
        except:
            pass
        
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
        with self.lock:
            self.queued_prompts.put(prompt)

        while True:
            with self.lock:
                prompt = self.completed_prompts.pop(
                    prompt_id,
                    self.failed_prompts.pop(
                        prompt_id,
                        None
                    )
                )
                
                if prompt is not None:
                    if prompt.result.output_state == OutputState.Failed:
                        return prompt.result
                    return prompt.result
            time.sleep(SERVER_CHECK_DELAY / 1000)

    def stop(
        self
    ):
        try:
            with self.lock:
                if self.state == PodManagerState.Running:
                    terminate_thread(self.manage_thread)
                    terminate_thread(self.process_thread)
                    for pod in self.pods:
                        pod.destroy()
                    self.pods = list[Pod]()
                    self.queued_prompts = Queue[Prompt]()
                    self.processing_prompts = dict[str, Prompt]()
                    self.completed_prompts = dict[str, Prompt]()
                    self.failed_prompts = dict[str, Prompt]()
                    self.state = PodManagerState.Stopped
        except Exception as e:
            print(e)
            pass

    def restart(
        self
    ):
        with self.lock:
            if self.state == PodManagerState.Stopped:
                self.process_thread = Thread(target=self.process)
                self.process_thread.start()
                self.manage_thread = Thread(target=self.manage_pods)
                self.manage_thread.start()

                self.state = PodManagerState.Running