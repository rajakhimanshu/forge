from tools.llm_router import safe_print
import requests
import json
import sseclient

def test():
    # Start
    res = requests.post("http://localhost:8000/api/forge/start", data={
        "idea_concept": "A tool to track time spent on coding",
        "idea_context": ""
    })
    session_id = res.json()["session_id"]
    safe_print("Session:", session_id)
    
    # Stream
    resp = requests.get(f"http://localhost:8000/api/forge/stream/{session_id}", stream=True)
    stream = sseclient.SSEClient(resp)
    for msg in stream.events():
        if msg.event == "ping":
            continue
        try:
            data = json.loads(msg.data)
            safe_print(f"Node: {data.get('node')}")
            if data.get('node') in ['complete', 'error']:
                safe_print(data)
                break
        except json.JSONDecodeError:
            safe_print("Could not decode:", msg.data)

if __name__ == "__main__":
    test()