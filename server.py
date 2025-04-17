from dotenv import load_dotenv
load_dotenv()

from core.pod_helper import create_pod_with_network_volume, get_pod_info, delete_pod

if __name__ == "__main__":
    pod_id = create_pod_with_network_volume("0mdsp6d0ht", "test1").get("id", "")
    pod_info = get_pod_info(pod_id)
    public_ip, port_mappings = pod_info.get("publicIp", ""), pod_info.get("portMappings")
    run_comfyui_server(pod_id, public_ip, port_mappings)