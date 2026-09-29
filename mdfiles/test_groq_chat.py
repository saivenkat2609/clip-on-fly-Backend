"""
Test Groq Chat Completions API
Run this to verify your API key works for chat completions
"""
import json
import urllib.request
import urllib.error

# Replace with your actual API key
GROQ_API_KEY = "PASTE_YOUR_NEW_KEY_HERE"  # Replace with the new key from Step 1

url = "https://api.groq.com/openai/v1/chat/completions"

request_data = {
    "model": "llama-3.1-70b-versatile",  # Try stable model instead of 3.3
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Say 'Hello, API works!'"
        }
    ],
    "temperature": 0.5,
    "max_tokens": 20
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
    with urllib.request.urlopen(req, timeout=30) as response:
        response_data = response.read().decode('utf-8')
        result = json.loads(response_data)
        print("✓ SUCCESS!")
        print(f"Response: {result['choices'][0]['message']['content']}")
except urllib.error.HTTPError as e:
    error_body = e.read().decode('utf-8') if e.fp else str(e)
    print(f"✗ FAILED!")
    print(f"Status: {e.code}")
    print(f"Error: {error_body}")
except Exception as e:
    print(f"✗ FAILED!")
    print(f"Error: {str(e)}")
