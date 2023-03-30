import os
import sys
import time
import openai

class App:
  

  __conf = {
    "TEMP": 0.8,
    "MAX_TOKENS": 300,
    "TOP_P": 0.95,
    "CODEX_ENGINE": 'code-davinci-edit-001', # 'code-davinci-002
    "NUM_CODEX_RETRIES": 100,
    "MAX_NUM_CODEX_CODE_SUGGESTIONS" : 10,
    "TESTS" : 'trigger',
    "PATCH_GRANULARITY" : 'line',
    "OUTPUT_DIR" : ""

  }
  __setters = ["TEMP", "MAX_TOKENS", "TOP_P", "CODEX_ENGINE", "NUM_CODEX_RETRIES", "MAX_NUM_CODEX_CODE_SUGGESTIONS", "TESTS", "PATCH_GRANULARITY", "TMP_DIR", "OUTPUT_DIR"]

  @staticmethod
  def config(name):
    return App.__conf[name]

  @staticmethod
  def set(name, value):
    if name in App.__setters:
      App.__conf[name] = value
    else:
      raise NameError("Name not accepted in set() method")


