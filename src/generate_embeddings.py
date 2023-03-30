import openai
import numpy as np
import os
from config import App
import os
from dotenv import load_dotenv
import json
import argparse
import numpy as np
import copy
from tqdm import tqdm
import time
from tenacity import retry, wait_random_exponential, stop_after_attempt


def parse_command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str,
                        help='json file containing patches')
    parser.add_argument('--output', type=str,
                        help='output file to save embeddings')
    return parser.parse_args()

def setup():
    """Setup OpenAI API"""
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def get_embedding(text: str, model="text-embedding-ada-002"):
    return openai.Embedding.create(input=[text], model=model)["data"][0]["embedding"]

if __name__ == '__main__':
    args = parse_command_line_args()
    print("Command line args with defaults ==>\n\t" +
          '\n\t'.join([f"--{k}={v}" for k, v in vars(args).items()]))

    input_file = args.input
    setup()

    with open(input_file, 'r') as f:
        patches = json.load(f)

    for bug in tqdm(patches):
        try:
            for patch in tqdm(patches[bug]['patches']):
                text = patch['patch']
                if text is None:
                    text = "empty"
                    print("empty patch for " + bug)
                embedding = get_embedding(text, model="text-embedding-ada-002")
                patch['embedding'] = embedding
            
            with open(args.output, 'w') as f:
                json.dump(patches, f)
        
        except Exception as e:
            print(e)
         
