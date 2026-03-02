import google.generativeai as genai
import os

# Load your Gemini API key from environment variable
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set in environment.")

genai.configure(api_key=api_key)

# List available models
models = genai.list_models()
print("Available Gemini models:")
for m in models:
    print(f"- {m.name}")
