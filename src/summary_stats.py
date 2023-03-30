

import time
from datetime import datetime
import openai
import config
import os 
from dotenv import load_dotenv
import json
import query_model as qm
import argparse
import jsonlines
import pandas
import numpy as np

def parse_command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--i', type=str,  help='path to directory containing validated patch files')
    parser.add_argument('--prune_compilation', action='store_true',  help='Flag to prune compilation failures')
    return parser.parse_args() 

def get_pass_at_k(n, c, k):
    if n - c < k : return 1.0
    return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))

def pass_at_k(input_dir, k, prune_compilation):
    p_k_list = []

    for file in os.listdir(input_dir):
        if file.endswith('.jsonl'):
            file_path = os.path.join(input_dir, file)
            try:
                correct = 0
                total = 0
                jsonObj = pandas.read_json(path_or_buf=file_path, lines=True)
                
                for i in jsonObj:
                    if len (jsonObj[i][0]['patches']) > 0:
                        prune_comp_failures = []
                        for p in jsonObj[i][0]['patches']:
                            if "uncompilable" not in p['correctness'] :
                                prune_comp_failures.append(p)
                            if [p][0]['correctness'] == 'plausible':
                               # if "failing_relevant" in [p][0]:
                                    if [p][0]['failing_relevant'] == 0:
                                        correct += 1
                   
                if prune_compilation:
                    total = len(prune_comp_failures)
                else:
                    total = len(jsonObj[i][0]['patches'])
                p_k = get_pass_at_k(total, correct, min(k, total))
                p_k_list.append(p_k)
            except:
                print("Error in file: " + file)
    
    p_k_avg = sum(p_k_list)/283 #number of bugs in D4J-nl2fix
    
    return p_k_avg

if __name__ == '__main__':
    args = parse_command_line_args()
    input_dir =  args.i
    prune_compilation = args.prune_compilation
    p1 = pass_at_k(input_dir, 1, prune_compilation)
    print ("Pass@1: " + (str(p1*100)) + "%" )
    p2 = pass_at_k(input_dir, 5, prune_compilation)
    print ("Pass@5: " + str(p2*100) + "%" )
    p3 = pass_at_k(input_dir, 20, prune_compilation)
    print ("Pass@20: " + str(p3*100) + "%")
    p4 = pass_at_k(input_dir, 100, prune_compilation)
    print ("Pass@100: " + str(p4*100) + "%")
    

