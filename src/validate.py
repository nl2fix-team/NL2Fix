import argparse
import os
import sys
import path
import validate_defects4j as validate
from config import App
import time

def parse_command_line_args():
    parser = argparse.ArgumentParser()
    # options that do not affect the metrics
    parser.add_argument('--patch_file', type=str, required=True, help='path to file containing generated patches')
    parser.add_argument('--level', type=str, default='line',  help='patch level')
    parser.add_argument('--tests', type=str, default='trigger',  help='Which tests to execute, trigger or all (trigger + relevant)')
    parser.add_argument('--num_examples', type=int,  help='How many examples to process, default is all')

    return parser.parse_args()         

if __name__ == '__main__':
    args = parse_command_line_args()
    print("Command line args with defaults ==>\n\t" + '\n\t'.join([f"--{k}={v}" for k, v in vars(args).items()]))

    App.set("PATCH_GRANULARITY" , args.level)
    App.set("TESTS", args.tests)
    input_patch_file =  args.patch_file
    num_examples = args.num_examples
 
    validate.validate_defects4j(input_patch_file, num_examples)