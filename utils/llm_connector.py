import requests
import json
import os
import openai
import asyncio # Import asyncio for async operations
from typing import Optional, List, Dict, Any # Import necessary types
from dotenv import load_dotenv
load_dotenv()


class LLMConnector:
    """
    Handles connections and calls to the LLM API (Gemini or OpenAI).
    """
    def __init__(self, api_key: str = "", llm_provider: str = "gemini"):
        self.llm_provider = llm_provider.lower()
        if self.llm_provider == "gemini":
            self.api_key = api_key if api_key else os.getenv("GEMINI_API_KEY", "")
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        elif self.llm_provider == "openai":
            self.api_key = api_key if api_key else os.getenv("OPENAI_API_KEY", "")
            openai.api_key = self.api_key # This line is for older OpenAI library compatibility
            # --- FIX: Explicitly pass api_key to OpenAI client constructor ---
            self.client = openai.OpenAI(api_key=self.api_key) 
        else:
            raise ValueError("Unsupported LLM provider. Choose 'gemini' or 'openai'.")


    async def call_llm_api(self, prompt: Optional[str] = None, messages: Optional[List[Dict[str, Any]]] = None, response_schema: dict = None, model: str = None) -> str | dict | None:
        """
        Makes an asynchronous call to the configured LLM API.
        Can accept either a single 'prompt' string or a list of 'messages' for conversational context.
        """
        if not prompt and not messages:
            print("Error: Either 'prompt' or 'messages' must be provided.")
            return None

        # Prepare chat history for the LLM API call
        # If 'prompt' is provided, convert it to a single message.
        # If 'messages' is provided, use it directly.
        llm_messages = []
        if messages:
            llm_messages = messages
        elif prompt:
            llm_messages.append({ "role": "user", "parts": [{ "text": prompt }] })


        if self.llm_provider == "gemini":
            if not self.api_key:
                print("Error: Gemini API key not found.")
                return None

            payload = { "contents": llm_messages } # Use llm_messages here

            if response_schema:
                payload["generationConfig"] = {
                    "responseMimeType": "application/json",
                    "responseSchema": response_schema
                }

            headers = { 'Content-Type': 'application/json' }
            api_url = f"{self.base_url}?key={self.api_key}"

            try:
                response = await asyncio.to_thread(
                    requests.post,
                    api_url,
                    headers=headers,
                    data=json.dumps(payload)
                )
                response.raise_for_status()
                result = response.json()

                if result.get("candidates") and result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts"):
                    text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                    if response_schema:
                        try:
                            return json.loads(text_response)
                        except json.JSONDecodeError:
                            print(f"Warning: Expected JSON but received malformed JSON from Gemini: {text_response}")
                            return text_response
                    return text_response
                else:
                    print(f"Warning: Unexpected Gemini API response structure: {result}")
                    return None
            except requests.exceptions.RequestException as e:
                print(f"Error calling Gemini API: {e}")
                return None
            except Exception as e:
                print(f"An unexpected error occurred with Gemini: {e}")
                return None

        elif self.llm_provider == "openai":
            if not model:
                model = "gpt-3.5-turbo" # Default OpenAI model

            # OpenAI's chat completions API expects messages in a specific format
            openai_messages = [{"role": msg["role"], "content": msg["parts"][0]["text"]} for msg in llm_messages]

            try:
                if response_schema:
                    completion = await self.client.chat.completions.create(
                        model=model,
                        messages=openai_messages, # Use openai_messages here
                        response_format={"type": "json_object"}
                    )
                    text_response = completion.choices[0].message.content
                    return json.loads(text_response)
                else:
                    completion = await self.client.chat.completions.create(
                        model=model,
                        messages=openai_messages # Use openai_messages here
                    )
                    return completion.choices[0].message.content
            except openai.APIError as e:
                print(f"Error calling OpenAI API: {e}")
                return None
            except Exception as e:
                print(f"An unexpected error occurred with OpenAI: {e}")
                return None
        return None
