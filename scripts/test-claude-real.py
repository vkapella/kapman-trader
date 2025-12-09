import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

api_key = os.getenv("CLAUDE_API_KEY")
print(f"API Key present: {bool(api_key)}")
print(f"API Key length: {len(api_key) if api_key else 0}")
print(f"API Key starts with: {api_key[:20] if api_key else 'None'}...")

client = anthropic.Anthropic(api_key=api_key)

try:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": "Say 'API works!'"}]
    )
    print("\n✅ SUCCESS!")
    print(f"Response: {response.content[0].text}")
except Exception as e:
    print(f"\n❌ FAILED: {e}")
