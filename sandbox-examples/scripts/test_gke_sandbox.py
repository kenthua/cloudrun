import subprocess
import httpx
import json

def get_id_token():
    res = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True)
    return res.stdout.strip()

token = get_id_token()
base_url = "https://sandbox-sidecar-739169254157.us-central1.run.app"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

client = httpx.Client(base_url=base_url, headers=headers, timeout=60.0)

print("--- 1. Root & Status ---")
print("GET / ->", client.get("/").json())
print("GET /status ->", client.get("/status").json())

print("\n--- 2. Turn 1: Save data in GKE Sandbox ---")
res1 = client.post("/exec", json={
    "command": "python3 -c \"import json; open('/tmp/portfolio.json', 'w').write(json.dumps({'AAPL': 0.45, 'NVDA': 0.55})); print('Portfolio state successfully saved to GKE Sandbox!')\"",
    "session_id": "stateful-gke-session-1"
})
print("Turn 1 Result:", res1.json())

print("\n--- 3. Turn 2: Read data back from GKE Sandbox ---")
res2 = client.post("/exec", json={
    "command": "python3 -c \"import json; data = json.loads(open('/tmp/portfolio.json').read()); print('Recovered state from GKE Sandbox:', data)\"",
    "session_id": "stateful-gke-session-1"
})
print("Turn 2 Result:", res2.json())

print("\n--- 4. Turn 3: Multi-turn Computation & Optimization ---")
res3 = client.post("/exec", json={
    "command": "python3 -c \"import json, numpy as np; data = json.loads(open('/tmp/portfolio.json').read()); weights = np.array(list(data.values())); print('Calculated normalized norm:', float(np.linalg.norm(weights)))\"",
    "session_id": "stateful-gke-session-1"
})
print("Turn 3 Result:", res3.json())


print("\n--- 5. Turn 4: Autonomous Managed Agent Task (Gemini 3.7 Flash -> GKE Sandbox) ---")
agent_res = client.post("/agent/task", json={
    "prompt": "Calculate the roots of the quadratic equation 3x^2 + 10x - 25 = 0 using Python and return the exact numeric solutions and verification.",
    "session_id": "stateful-gke-session-1"
})
print("Agent Response Status:", agent_res.status_code)
print(json.dumps(agent_res.json(), indent=2))
