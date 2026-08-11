import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY is missing.")
    print("Create a .env file and add:")
    print("GEMINI_API_KEY=your_api_key")
    raise SystemExit(1)

try:
    client = genai.Client(api_key=api_key)

    print("\n" + "=" * 70)
    print("AVAILABLE GEMINI MODELS")
    print("=" * 70)

    found = False

    for model in client.models.list():

        name = getattr(model, "name", "")
        actions = getattr(model, "supported_actions", None)

        if not name:
            continue

        print(f"\nModel: {name}")

        if actions:
            print(f"Supported actions: {actions}")

        found = True

    if not found:
        print("No models were returned.")

    print("\n" + "=" * 70)
    print("MODEL CHECK COMPLETED")
    print("=" * 70)

except Exception as e:

    print("\n❌ Connection/API error")
    print(str(e))