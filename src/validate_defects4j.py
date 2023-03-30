import json
import jsonlines
import os
import shutil
import subprocess
import time
import sys
from pebble import ProcessPool
from multiprocessing import Value
from concurrent.futures import TimeoutError
import traceback
import datetime
import tokenization
import patch_utils as utils
import tqdm
from config import App

def clean_tmp_folder(tmp_dir):
    if os.path.isdir(tmp_dir):
        for files in os.listdir(tmp_dir):
            file_p = os.path.join(tmp_dir, files)
            try:
                if os.path.isfile(file_p):
                    os.unlink(file_p)
                elif os.path.isdir(file_p):
                    shutil.rmtree(file_p)
            except Exception as e:
                print(e)
    else:
        os.makedirs(tmp_dir)

#checkout the defects4j project to be tested 
# project name, bug id, and where to checkout the project
def checkout_defects4j_project(project, bug_id, tmp_dir):
    print("Checking out ", project, " ", bug_id, " to ", tmp_dir)
    FNULL = open(os.devnull, 'w')
    #command from defects4j installation
    command = "defects4j checkout " + " -p " + project + " -v " + bug_id + " -w " + tmp_dir
    p = subprocess.Popen([command], shell=True, stdout=FNULL, stderr=FNULL)
    p.wait()

#catch compilation errors for defects4j projects, mostly for Mockito
def compile_fix(project_dir):
    os.chdir(project_dir)
    print("Compiling ", project_dir)
    p = subprocess.Popen(["defects4j", "compile"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if "FAIL" in str(err) or "FAIL" in str(out):
        return False
    return True

#execute the defects4j with a set timeout
def command_with_timeout(cmd, timeout=300):
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
    t_beginning = time.time()
    while True:
        if p.poll() is not None:
            break
        seconds_passed = time.time() - t_beginning
        if timeout and seconds_passed > timeout:
            p.terminate()
            return 'TIMEOUT', 'TIMEOUT'
        time.sleep(1)
    out, err = p.communicate()
    return out, err

#runs all defects4j tests on instance
# -r Only execute relevant developer-written tests
def defects4j_test_suite(project_dir, timeout=300):
    os.chdir(project_dir)
    out, err = command_with_timeout(["defects4j", "test", "-r"], timeout)
    if "Compilation failed" in str(out):
        print("FAIL to Compile tests for ", project_dir)
    return out, err

# export number of trigger tests for buggy instance
def defects4j_trigger(project_dir, timeout=300):
    os.chdir(project_dir)
    out, err = command_with_timeout(["defects4j", "export", "-p", "tests.trigger"], timeout)
    return out, err

#export number of relevant tests for buggy instance
def defects4j_relevant(project_dir, timeout=300):
    os.chdir(project_dir)
    out, err = command_with_timeout(["defects4j", "export", "-p", "tests.relevant"], timeout)
    return out, err

#run only one tests
def defects4j_test_one(project_dir, test_case, timeout=300):
    os.chdir(project_dir)
    out, err = command_with_timeout(["defects4j", "test", "-t", test_case], timeout)
    return out, err

def get_bug_stats(tmp_dir):
    # check standard test time
    start_time = time.time()
    init_out, init_err = defects4j_test_suite(tmp_dir)
    standard_exec_time = int(time.time() - start_time)

    # check the number of failed test cases from output
    failed_test_cases = str(init_out).split(' - ')[1:]
    for i, failed_test_case in enumerate(failed_test_cases):
        failed_test_cases[i] = failed_test_case.strip()
    init_fail_num = len(failed_test_cases)
    print("number of failing test cases:", init_fail_num)
    print("standard test execution time", str(standard_exec_time) + 's')

    # List of test methods that trigger (expose) the bug
    # trigger tests should be equal to the number of failing tests
    trigger, err = defects4j_trigger(tmp_dir)
    trigger_tests = trigger.strip().split('\n')
    for i, trigger_test in enumerate(trigger_tests):
        trigger_tests[i] = trigger_test.strip()
    print('trigger number:', len(trigger_tests))

    # List of relevant tests classes 
    # a test class is relevant if, when executed, the JVM loads at least one of the modified classes
    relevant_tests, err = defects4j_relevant(tmp_dir)
    relevant_tests = relevant_tests.strip().split('\n')
    for i, test in enumerate(relevant_tests):
        relevant_tests[i] = test.strip()
    print('relevant number:', len(relevant_tests))

    return standard_exec_time, trigger_tests, relevant_tests, failed_test_cases



def validate_defects4j(patch_file, num_examples):
     
    candidate_patches = json.load(open(patch_file, 'r'))
    
    if num_examples is not None:
        candidate_patches = {k: candidate_patches[k] for k in list(candidate_patches.keys())[:num_examples]}

    with ProcessPool() as pool:
        future = pool.map(validate_patches_per_bug, candidate_patches.items())
        iterator = future.result()
        while True:
                try:
                    result = next(iterator)  
                except StopIteration:
                    break
                except (cf.TimeoutError, ProcessExpired):
                    continue
                except Exception as e:
                    print(f"Final catastrophic exception {str(e)}")
                    print(error.traceback)
                    continue
    pool.close()
    pool.join()
    
def extract_d4j_result( err, out, current_bug, tokenized_patch, start_time,  init_fail_num, failed_test_cases):

    patch_err = ""
    if 'TIMEOUT' in str(err) or 'TIMEOUT' in str(out):
        print( current_bug, 'Patch Timeout',
                str(int(time.time() - start_time)) + 's')
        correctness = 'timeout'
    elif 'FAIL' in str(err) or 'FAIL' in str(out):
        print(current_bug, 'Uncompilable patch', 
                str(int(time.time() - start_time)) + 's')
        correctness = 'uncompilable'

    elif "Failing tests: 0" in str(out):
        print(current_bug, 'Plausible patch', 
                str(int(time.time() - start_time)) + 's')
        correctness = 'plausible'
       
    elif len(str(out).split(' - ')[1:]) > 0:
        print( current_bug, 'Wrong patch', 
                str(int(time.time() - start_time)) + 's')
        correctness = 'wrong'
    else:
        print( current_bug, 'Wrong patch', 
                str(int(time.time() - start_time)) + 's')
        correctness = 'wrong'
    return correctness, patch_err


def validate_patches_per_bug(candidate_patch):

    key = candidate_patch[0]
    proj, bug_id, path, start_loc, end_loc = key.split('_')
    
    current_dir = os.path.dirname(os.path.realpath(__file__))
    tmp_dir = os.path.join(current_dir, 'tmp', proj + '_' + bug_id)
    output_dir = os.path.join(current_dir, 'validation-output')

    if not os.path.exists(tmp_dir):
        command_with_timeout(['mkdir', tmp_dir])
    
 
    validated_result = {}
    current_bug = proj + '_' + bug_id
 
    # checkout project
    clean_tmp_folder(tmp_dir)
    checkout_defects4j_project(proj, bug_id + 'b', tmp_dir)
    
    if proj == "Mockito" or proj == "mockito":
        print("Mockito needs separate compilation")
        compile_fix(tmp_dir)

    #get relevant stats for current bug
    standard_exec_time, trigger_tests, relevant_tests, failed_test_cases = get_bug_stats(tmp_dir)
    init_fail_num = len(failed_test_cases)
    validated_result[key] = {'patches': []}
    bug_start_time = time.time()
    validated_patch_list = []

    for tokenized_patch in candidate_patch[1]['patches']:
        if (tokenized_patch['patch'] not in validated_patch_list):
            # timeout after 1 hour per bug at most
            if time.time() - bug_start_time > 1 * 3600:
                break

            index = ""
            if 'index' in tokenized_patch:
                index = tokenized_patch['index']
            
            tokenized_patch = tokenized_patch['patch']
            validated_patch_list.append(tokenized_patch)
            
            with open(path, 'r') as file:
                clean_file = file.readlines()

            backup_file = utils.apply_patch(tmp_dir, path, start_loc, end_loc, tokenized_patch, App.config("PATCH_GRANULARITY"))
            test_errors = []
            failing_tests = []
            passing_tests = []
            correctness = None
            start_time = time.time()
            passing_relevant = 0
            passing_trigger = 0
            patch_compiles = True
            all_trigger_pass = True
            rel_fail_num = 0
            if init_fail_num == 0:
                correctness = 'init-error'
            else:
                if (App.config("TESTS") == 'trigger') or (App.config("TESTS") == 'all'):
                    for trigger in trigger_tests:
                        #if patch does not compile, do not run every test
                        if patch_compiles and all_trigger_pass:
                            out, err = defects4j_test_one(tmp_dir, trigger)
                            correctness, patch_err = extract_d4j_result( err, out, current_bug, tokenized_patch, start_time, init_fail_num, failed_test_cases)
                            if correctness == 'plausible':
                                passing_trigger += 1
                                passing_tests.append(trigger)
                            elif correctness == 'wrong': 
                                failing_tests.append(trigger)
                                test_errors.append(err)
                                all_trigger_pass = False
                            elif correctness == 'uncompilable':
                                failing_tests.append(trigger)
                                test_errors.append(err)
                                patch_compiles = False
                                all_trigger_pass = False
                
                  
                if (App.config("TESTS") == 'relevant' or App.config("TESTS") == 'all'):
                    if patch_compiles:
                        out, err = defects4j_test_suite(tmp_dir)
                        failed_test_cases = str(out).split(' - ')[1:]
                        for i, failed_test_case in enumerate(failed_test_cases):
                            failed_test_cases[i] = failed_test_case.strip()
                        rel_fail_num = len(failed_test_cases)
                        if rel_fail_num > 0:
                            failing_tests.append(failed_test_cases) 
                            test_errors.append(err)        
            
                shutil.copyfile(backup_file, backup_file.replace('.bak', ''))
                with open(backup_file.replace('.bak', ''), 'r') as file:
                    assert clean_file == file.readlines()
             

            validated_result[key]['patches'].append({
                'patch': tokenized_patch, 
                'index': index,
                'correctness': correctness, 
                'errors': test_errors, 
                'total_trigger': len(trigger_tests), 
                'passing_trigger': passing_trigger,
                'total_relevant': len(relevant_tests),
                'failing_relevant': rel_fail_num,
                'passing_tests': passing_tests,
                'failing_tests': failing_tests,
            })
            
    write_results_to_file(validated_result, output_dir, current_bug)
    return validated_result      
    

def write_results_to_file(validated_result, output_dir, current_bug):
    filename = str(current_bug) + '-validated.jsonl'
    log_file = os.path.join(output_dir, filename)
  
    if not os.path.exists(output_dir):
        command_with_timeout(['mkdir', output_dir])

    try:   
        print('Writing to file ', log_file)   
        with jsonlines.open(log_file, mode='w') as writer:
            writer.write(validated_result)

    except Exception as e:
        print('Error when writing to file ', e)  