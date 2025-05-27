import requests
import json
import os
import openai 

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
            openai.api_key = self.api_key
            self.client = openai.OpenAI() # Initialize OpenAI client
        else:
            raise ValueError("Unsupported LLM provider. Choose 'gemini' or 'openai'.")


    async def call_llm_api(self, prompt: str, response_schema: dict = None, model: str = None) -> str | dict | None:
        """
        Makes an asynchronous call to the configured LLM API.
        """
        if self.llm_provider == "gemini":
            # ... existing Gemini API call logic ...
            # (You'd keep the current code for Gemini here)
            pass
        elif self.llm_provider == "openai":
            if not model:
                model = "gpt-3.5-turbo" # Default OpenAI model

            messages = [{"role": "user", "content": prompt}]
            try:
                # For structured output, you might need to guide the LLM
                # to produce JSON or parse its natural language response.
                # OpenAI's function calling or JSON mode can be used here.
                if response_schema:
                    # This part would be more complex for direct schema enforcement
                    # with OpenAI's standard chat completions without function calling.
                    # You might need to instruct the model to output JSON and then parse it.
                    completion = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_format={"type": "json_object"} # For OpenAI's JSON mode
                    )
                    text_response = completion.choices[0].message.content
                    return json.loads(text_response)
                else:
                    completion = self.client.chat.completions.create(
                        model=model,
                        messages=messages
                    )
                    return completion.choices[0].message.content
            except openai.APIError as e:
                print(f"Error calling OpenAI API: {e}")
                return None
            except Exception as e:
                print(f"An unexpected error occurred with OpenAI: {e}")
                return None
        return None