# --- Imports ---
import requests
import json
import os
import openai
import asyncio
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# --- Load environment variables from .env ---
load_dotenv()

# --- LLMConnector Class ---
class LLMConnector:
    """
    Handles connections and calls to Gemini or OpenAI LLM APIs.
    """

    def __init__(self, api_key: str = "", llm_provider: str = "openai"):
        self.llm_provider = llm_provider.lower()

        if self.llm_provider == "gemini":
            self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
            self.base_url = (
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
            )

        elif self.llm_provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
            openai.api_key = self.api_key
            self.client = openai.OpenAI(api_key=self.api_key)

        else:
            raise ValueError("Unsupported LLM provider. Choose 'gemini' or 'openai'.")

    async def call_llm_api(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        response_schema: dict = None,
        model: str = None,
    ) -> str | dict | None:
        """
        Asynchronously calls the configured LLM (OpenAI or Gemini).
        """

        # --- Ensure either prompt or messages is provided ---
        if not prompt and not messages:
            print("❌ Error: Either 'prompt' or 'messages' must be provided.")
            return None

        # --- Construct message list ---
        llm_messages = []
        if messages:
            llm_messages = messages
        elif prompt:
            llm_messages.append({"role": "user", "parts": [{"text": prompt}]})

        # --- Gemini Handling ---
        if self.llm_provider == "gemini":
            if not self.api_key:
                print("❌ Error: Gemini API key not found.")
                return None

            payload = {"contents": llm_messages}

            if response_schema:
                payload["generationConfig"] = {
                    "responseMimeType": "application/json",
                    "responseSchema": response_schema,
                }

            headers = {"Content-Type": "application/json"}
            api_url = f"{self.base_url}?key={self.api_key}"

            try:
                response = await asyncio.to_thread(
                    requests.post, api_url, headers=headers, data=json.dumps(payload)
                )
                response.raise_for_status()
                result = response.json()

                candidates = result.get("candidates", [])
                if candidates and candidates[0].get("content"):
                    parts = candidates[0]["content"].get("parts", [])
                    if parts:
                        text_response = parts[0]["text"]
                        if response_schema:
                            try:
                                return json.loads(text_response)
                            except json.JSONDecodeError:
                                print(f"⚠️ Malformed JSON from Gemini: {text_response}")
                                return text_response
                        return text_response

                print(f"⚠️ Unexpected Gemini response format: {result}")
                return None

            except requests.exceptions.RequestException as e:
                print(f"❌ Gemini API connection error: {e}")
                return None

            except Exception as e:
                print(f"❌ Unexpected error with Gemini: {e}")
                return None

        # --- OpenAI Handling ---
        elif self.llm_provider == "openai":
            if not model:
                model = "gpt-3.5-turbo"

            openai_messages = [
                {"role": msg["role"], "content": msg["parts"][0]["text"]}
                for msg in llm_messages
            ]

            try:
                completion = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=model,
                    messages=openai_messages,
                    tools=[{
                        "type": "function",
                        "function": {
                            "name": "extract_structured_response",
                            "parameters": response_schema
                        }
                    }] if response_schema else None,
                    tool_choice="auto" if response_schema else None,
                )

                if response_schema and completion.choices[0].message.tool_calls:
                    try:
                        arguments = completion.choices[0].message.tool_calls[0].function.arguments
                        return json.loads(arguments)
                    except Exception as e:
                        print(f"⚠️ Failed to parse tool_call arguments: {e}")
                        return completion.choices[0].message.tool_calls[0].function.arguments

                return completion.choices[0].message.content

            except openai.APIError as e:
                print(f"❌ OpenAI API error: {e}")
                return None

            except Exception as e:
                print(f"❌ Unexpected error with OpenAI: {e}")
                return None

        return None
