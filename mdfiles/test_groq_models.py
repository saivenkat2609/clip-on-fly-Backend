"""
Test which Groq models are available on your API key
"""
import json
import urllib.request

# Replace with your API key
GROQ_API_KEY = "PASTE_YOUR_KEY_HERE"

# List of models to test
models_to_test = [
    "llama-3.3-70b-versatile",  # Current model (might not exist)
    "llama-3.1-70b-versatile",  # Stable LLaMA 3.1 70B
    "llama-3.1-8b-instant",     # Fast LLaMA 3.1 8B
    "mixtral-8x7b-32768",       # Mixtral
    "gemma2-9b-it",             # Gemma 2
]

url = "https://api.groq.com/openai/v1/chat/completions"

for model in models_to_test:
    print(f"\nTesting model: {model}")

    request_data = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "max_tokens": 10
    }

    json_data = json.dumps(request_data).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=json_data,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"  ✓ SUCCESS - {model} is available")
    except Exception as e:
        error_str = str(e)
        if "403" in error_str:
            print(f"  ✗ BLOCKED (403) - Cloudflare blocking urllib")
        elif "404" in error_str:
            print(f"  ✗ NOT FOUND - Model doesn't exist")
        elif "401" in error_str:
            print(f"  ✗ AUTH ERROR - Check API key")
        else:
            print(f"  ✗ ERROR - {error_str}")
