import os
import requests
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("AI PROVIDER TEST")
print("=" * 60)


# =========================================================
# GEMINI
# =========================================================

def test_gemini():
    print("\n[1] Testing Gemini...")

    api_key = os.getenv("GEMINI_API_KEY_1")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    if not api_key:
        print("❌ Gemini: API key not found")
        return

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Reply with exactly: Gemini is working"
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        if response.ok:
            result = response.json()

            text = (
                result
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text")
            )

            print("✅ Gemini: WORKING")
            print("Response:", text or "(empty response)")

        else:
            print("❌ Gemini: FAILED")
            print("Status:", response.status_code)
            print("Error:", response.text[:1000])

    except Exception as e:
        print("❌ Gemini: ERROR")
        print(e)


# =========================================================
# GROQ
# =========================================================

def test_groq():
    print("\n[2] Testing Groq...")

    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-120b"
    )

    if not api_key:
        print("❌ Groq: API key not found")
        return

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly: Groq is working"
            }
        ],
        "max_tokens": 500,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        if response.ok:
            result = response.json()

            message = result["choices"][0]["message"]

            text = message.get("content")

            if text:
                print("✅ Groq: WORKING")
                print("Response:", text.strip())
            else:
                print("⚠️ Groq: API worked but returned no text")
                print("Response:", result)

        else:
            print("❌ Groq: FAILED")
            print("Status:", response.status_code)
            print("Error:", response.text[:1000])

    except Exception as e:
        print("❌ Groq: ERROR")
        print(e)


# =========================================================
# OPENROUTER
# =========================================================

def test_openrouter():
    print("\n[3] Testing OpenRouter...")

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free"
    )

    if not api_key:
        print("❌ OpenRouter: API key not found")
        return

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AI Business Analytics Test",
    }

    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly: OpenRouter is working"
            }
        ],
        "max_tokens": 30,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        if response.ok:
            result = response.json()

            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})

            text = message.get("content")

            if text:
                print("✅ OpenRouter: WORKING")
                print("Response:", text.strip())
            else:
                print("⚠️ OpenRouter: API worked but returned no text")
                print("Model:", result.get("model"))
                print("Finish reason:", choice.get("finish_reason"))
                print("Full response:")
                print(result)

        else:
            print("❌ OpenRouter: FAILED")
            print("Status:", response.status_code)
            print("Error:", response.text[:1000])

    except Exception as e:
        print("❌ OpenRouter: ERROR")
        print(e)


# =========================================================
# RUN TESTS
# =========================================================

test_gemini()
test_groq()
test_openrouter()

print("\n" + "=" * 60)
print("TEST FINISHED")
print("=" * 60)