from config import App
import os
from dotenv import load_dotenv
import json
import query_model as qm
import argparse
import numpy as np
from scipy.spatial.distance import cdist
import copy
from tqdm import tqdm


def parse_command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str,
                        help='path to file containing buggy files and metadata')
    parser.add_argument('--output', type=str,
                        help='output file to write generated edit results to')
    parser.add_argument('--max_num_patches', type=int,
                        help='number of patches to generate')
    parser.add_argument('--model', type=str,
                        help='codex engine to use', default='code-davinci-edit-001')
    parser.add_argument('--prompt', type=str,
                        help='options basic, issue_summary or issue_description')
    parser.add_argument('--sampling_temp', type=float,
                        help='sampling temperature for gpt')
    parser.add_argument('--num_examples', type=int,
                        help='How many examples to process, default is all')
    parser.add_argument('--use_k_shot', action='store_true',
                        help='whether to use k-shot in the prompt')
    parser.add_argument(
        '--shot_selection_method',
        help='How to select k-shots. Note that if "fixed" is given, k_shot have to be 1',
        choices=['fixed', 'random', 'closest_source', 'closest_issue']
    )
    parser.add_argument('--k_shot', type=int,
                        help='Number of shots', default=0)
    parser.add_argument(
        '--use_cache',
        help='Use the cache with selected k shot_examples',
        action='store_true', default=True
    )

    return parser.parse_args()


def select_shots(
    buggy_file,
    shot_selection_method,
    k_shot
):
    cache_modified = False
    bugids = sorted(list(buggy_file.keys()))
    bugid_to_idx = {bid: idx for idx, bid in enumerate(bugids)}
    idx_to_bugids = {bugid_to_idx[bid]: bid for bid in bugid_to_idx}
    num_bugs = len(idx_to_bugids.keys())
    if shot_selection_method == 'fixed':
        issue_lengths = [
            len(str(buggy_file[idx_to_bugids[idx]]['summary']) +
                " " + str(buggy_file[idx_to_bugids[idx]]['Description']))
            for idx in tqdm(idx_to_bugids.keys())
        ]
        sorted_indices = np.argsort(issue_lengths)
        for idx in idx_to_bugids.keys():
            taken_idx = sorted_indices[0]
            if taken_idx == idx:
                taken_idx = sorted_indices[1]
            bugid = idx_to_bugids[idx]
            taken_bugid = idx_to_bugids[taken_idx]
            buggy_file[bugid]['k_shot'] = [copy.copy(buggy_file[taken_bugid])]
    elif shot_selection_method == 'random':
        for bid in bugids:
            copied_bids = copy.copy(bugids)
            copied_bids.remove(bid)
            taken_bugids = np.random.choice(copied_bids, k_shot)
            buggy_file[bid]['k_shot'] = [
                copy.copy(buggy_file[tbid]) for tbid in taken_bugids]
    else:
        print(
            f'Getting embeddings for selecting k_shot based on {shot_selection_method}')
        if shot_selection_method == 'closest_source':
            for idx in tqdm(idx_to_bugids.keys()):
                if 'src_wo_comments_embed' not in buggy_file[idx_to_bugids[idx]]:
                    buggy_file[idx_to_bugids[idx]]['src_wo_comments_embed'] = \
                        qm.get_embedding(
                            buggy_file[idx_to_bugids[idx]]['src_wo_comments'])
                    cache_modified = True
            source_embeddings = np.array(
                [buggy_file[idx_to_bugids[idx]]['src_wo_comments_embed']
                    for idx in idx_to_bugids.keys()]
            )
        else:
            for idx in tqdm(idx_to_bugids.keys()):
                if 'issue_embed' not in buggy_file[idx_to_bugids[idx]]:
                    buggy_file[idx_to_bugids[idx]]['issue_embed'] = qm.get_embedding(
                        str(buggy_file[idx_to_bugids[idx]]['summary'])
                    )
                    cache_modified = True
            source_embeddings = np.array([
                buggy_file[idx_to_bugids[idx]]['issue_embed'] for idx in idx_to_bugids.keys()
            ])
        distant_matrix = cdist(source_embeddings, source_embeddings)
        for idx in range(num_bugs):
            bugid = idx_to_bugids[idx]
            distances = distant_matrix[idx, :]
            sorted_example_indices = np.argsort(distances)
            taken = 0
            for sidx in sorted_example_indices:
                if sidx == idx:
                    continue
                if 'k_shot' not in buggy_file[bugid]:
                    buggy_file[bugid]['k_shot'] = []
                buggy_file[bugid]['k_shot'].append(
                    copy.copy(buggy_file[idx_to_bugids[sidx]]))
                taken += 1
                if taken == k_shot:
                    break
    return buggy_file, cache_modified


def build_prompt(
    prompt_type, issue_summary, issue_description, buggy_file,
    k_shots=None
):
    """Build prompt for gpt"""
    if prompt_type == 'basic':
        prompt = "Fix the bug with minimal changes. "
    elif prompt_type == 'issue_summary':
        prompt = "Fix the bug with minimal changes. The issue is: " + issue_summary
    elif prompt_type == 'issue_description':
        prompt = "Fix the bug with minimal changes. " + \
            "The issue is: " + issue_summary + issue_description
    elif prompt_type == 'discussion':
        prompt = "Fix the bug with minimal changes. " + "The issue is: " + \
            issue_summary + issue_description + discussion
    elif prompt_type == 'chatgpt':
         prompt = "The following code is buggy. " + \
            "The issue is: " + issue_summary + issue_description + "please provide a fixed version with minimal changes."+ \
             "<code>" + buggy_file + "</code> Surround the code changes in your response with <code> </code>"

    else:
        prompt = "Fix the bug with minimal changes. "
    if k_shots is not None:
        prompt += "\nExample changes "
        for shot in k_shots:
            prompt += f"\nBuggy\n{shot['src_wo_comments']}\n"
            prompt += f"Fixed\n{shot['fixed_src_wo_comments']}\n"
    return prompt


def generate_patches(metadata, output, num_examples, cache_file=None):
    """Generate patches for a buggy file"""
    patches = {}
    rate_limit_per_minute = 20
    # query gpt for each json object in the file
    if args.use_k_shot:
        metadata, cache_modified = select_shots(
            metadata,
            args.shot_selection_method,
            args.k_shot
        )
        if cache_file is not None and cache_modified:
            print(f'Saving cache to {cache_file}')
            with open(cache_file, 'w') as fp:
                try:
                    json.dump(metadata, fp, indent=2)
                    fp.close()
                except:
                    fp.close()
                    os.remove(cache_file)

    if num_examples is not None:
        metadata = {
            k: metadata[k] for k in list(metadata.keys())[:num_examples]
        }

    over_length_bugids = []
    no_patch_generated_bugids = []
    for bid_key in tqdm(metadata):
        key = bid_key.split('_')[0] + '_' + bid_key.split('_')[1]
        
        metadata[bid_key]['summary'] = metadata[bid_key]['summary'] or ''
        metadata[bid_key]['Description'] = metadata[bid_key]['Description'] or ''
        patches[bid_key] = {'patches': []}
        file = metadata[bid_key]['src_wo_comments']
        
        print("Generating patches for bug " + str(key))
        try:
            assert (
                not args.use_k_shot or 
                'k_shot' in metadata[bid_key].keys()
            ), "K-shot should've been selected before coming here, if it is used!"
      
            prompt = build_prompt(
                args.prompt,
                metadata[bid_key]['summary'],
                metadata[bid_key]['Description'],
                file,
                k_shots=metadata[bid_key]['k_shot'] if args.use_k_shot else None
            )
            patches[bid_key]['prompt'] = prompt
            
            response_len = 0
            while response_len < App.config("MAX_NUM_CODEX_CODE_SUGGESTIONS"):
                n = min(
                    App.config("MAX_NUM_CODEX_CODE_SUGGESTIONS") - response_len,
                    rate_limit_per_minute
                )
                
                response, cur_resp_len = query_model(prompt, file, n, App.config("CODEX_ENGINE"))
                response_len += cur_resp_len
                if response is not None:
                    print("....saving " + str(response_len) +
                          " patches for " + str(key))
                    if App.config("CODEX_ENGINE") == "gpt-3.5-turbo":
                        append_responses_to_patches_gpt3_5(patches, bid_key, response)
                    else:
                        append_responses_to_patches(patches, bid_key, response)
      
            patches[bid_key]['response_length'] = response_len
            patches[bid_key]['unique_patches'] = len(
                patches[bid_key]['patches']
            )
            if patches[bid_key]['unique_patches'] == 0:
                no_patch_generated_bugids.append(key)
            try:
                json.dump(patches, open(output, 'w'), indent=2)
            except:
                print('Error when writing to file')
        except ValueError as v:
            if "Over Length" in str(v):
                over_length_bugids.append(key)
        except Exception as e:
            print('Error when querying codex. Exception: ' + str(e))
    if len(over_length_bugids) > 0 or len(no_patch_generated_bugids) > 0:
        print('=' * 100)
        print("No patch was generated for the following bugids")
        print("Due to Over length Prompt")
        print('-' * 100)
        print('\n'.join(over_length_bugids))
        print('-' * 100)
        print("Due to Other reasons")
        print('-' * 100)
        print('\n'.join(no_patch_generated_bugids))
        print('=' * 100)


def query_model(prompt, file, n, model):
        response, cur_resp_len = qm.get_codex_response_with_retries(prompt, file, n, model )
        return response, cur_resp_len

def append_responses_to_patches(patches, bugid_key, response):
    for choice in response['choices']:
        if 'text' in choice:
            patches[bugid_key]['patches'].append(
                {'patch': choice['text'],
                 'index': choice['index']
                })
def append_responses_to_patches_gpt3_5(patches, bugid_key, response):
    for choice in response['choices']:
        if 'message' in choice:
            patches[bugid_key]['patches'].append(
                {'patch': choice['message']['content'],
                 'index': choice['index']
                })

if __name__ == '__main__':
    args = parse_command_line_args()
    print("Command line args with defaults ==>\n\t" +
          '\n\t'.join([f"--{k}={v}" for k, v in vars(args).items()]))
    App.set("CODEX_ENGINE", args.model)
    App.set("MAX_NUM_CODEX_CODE_SUGGESTIONS", args.max_num_patches)
    App.set("TEMP", args.sampling_temp)
    input_file = args.input
    output_file = args.output
    num_examples = args.num_examples
    qm.setup()

    # open json file and read file text
    cache_file = input_file + "-cached.json"
    if args.use_k_shot and args.use_cache and os.path.exists(cache_file):
        print(f'Reading data from {cache_file}')
        buggy_file = json.load(open(cache_file))
    else:
        print(f'Reading data from {input_file}')
        buggy_file = json.load(open(input_file))

    generate_patches(
        buggy_file, output_file, num_examples, cache_file
    )