from dotenv import load_dotenv
load_dotenv()

from core.pod_helper import create_pod_with_network_volume, get_pod_info, delete_pod, run_comfyui_server

if __name__ == "__main__":
    pod = create_pod_with_network_volume("0mdsp6d0ht", "test1")
    print(pod)
    pod_id = pod.get("id", "")
    pod_info = get_pod_info(pod_id)
    print(pod_info)
    public_ip, port_mappings = pod_info.get("publicIp", ""), pod_info.get("portMappings", None)
    run_comfyui_server(pod_id, public_ip, port_mappings)