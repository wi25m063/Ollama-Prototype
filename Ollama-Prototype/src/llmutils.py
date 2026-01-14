import os, json, re
from ollama import Client

def get_client():
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return Client(host=host)

def extract_json(text: str) -> dict:
    text = text.strip()

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in model output.")

    candidate = m.group(0)

    candidate = re.sub(r"[\x00-\x1F\x7F]", "", candidate)

    return json.loads(candidate)

def chat_json(model: str, system: str, user: str) -> dict:
    client = get_client()
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format="json",      # Important
        options={"temperature": 0}      # stable Output
    )
    return extract_json(resp["message"]["content"])
