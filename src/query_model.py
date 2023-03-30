import time
import openai
from config import App
import os
from dotenv import load_dotenv
import tiktoken


def setup():
    """Setup OpenAI API"""
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")


def get_codex_response_with_retries(prompt, buggy_file, n, model_type='edit'):
    """Query codex with retries"""
    rate_limit_per_minute = 3 if model_type == 'completion' else 20
    delay = 60.0 # / rate_limit_per_minute
    for _ in range(App.config("NUM_CODEX_RETRIES")):
        try:
            if model_type == 'edit':
                response = get_or_create_codex_response(prompt, buggy_file, n)
            elif model_type == 'completion':
                response = get_or_create_codex_completion(prompt, buggy_file, n)
            elif model_type == 'gpt3.5':
                response = get_or_create_gpt3_5_response(prompt, n)
            else:
                raise ValueError("Model type not supported")
            response_len = min(
                len(response['choices']),
                App.config("MAX_NUM_CODEX_CODE_SUGGESTIONS")
            )
            return response, response_len
        except openai.error.RateLimitError as e:
            print(
                f"RateLimitError Exception in get_codex_response_with_retries {e}"
            )
            time.sleep(delay)
        except openai.error.OpenAIError as e:
            print(
                f"OpenAIError Exception in get_codex_response_with_retries {e}"
            )
            # if e includes reduce the input size, then return with none
            if "Please reduce " in str(e):
                raise ValueError("Over Length")
            time.sleep(delay)
        except Exception as e:
            print(f"Exception in get_codex_response_with_retries {e}")
            # if e includes reduce the input size, then return with none
            if "Please reduce " in str(e):
                raise ValueError("Over Length")
            time.sleep(delay)
    return None, None


def get_or_create_codex_response(prompt, buggy_file, n):
    # https://beta.openai.com/docs/api-reference/edits
    # {model, input, instruction, n, temperature, top_p}
    response = openai.Edit.create(
        input=buggy_file,
        instruction=prompt,
        temperature=App.config("TEMP"),
        model="code-davinci-edit-001",
        n=n,
    )
    return response


def get_or_create_codex_completion(prompt, buggy_file, n):
    # https://beta.openai.com/docs/api-reference/completion
    # {model, input, instruction, n, temperature, top_p}
    response = openai.Completion.create(
        prompt=prompt,
        temperature=App.config("TEMP"),
        model='code-davinci-002',
        n=n,
        max_tokens=750,
        stop="//END_OF_CODE"
    )
    return response

def get_or_create_gpt3_5_response(prompt, n):
    # https://beta.openai.com/docs/api-reference/edits
    # {model, input, instruction, n, temperature, top_p}
  
    response = openai.ChatCompletion.create( messages=[{"role": "user", 
                                               "content": prompt }],
                                  model="gpt-3.5-turbo",
                                  n=n,
                                  temperature=App.config("TEMP"),
                                  )
    return response