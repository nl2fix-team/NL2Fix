import json
import jsonlines
import os
import shutil
import subprocess
import time
import sys
import tokenization


def apply_patch(tmp_dir,path, start_loc, end_loc, patch, level):
    if(level == "line"):
        backup_file = apply_patch_line(tmp_dir,path, start_loc, end_loc, patch)        
    else:
       backup_file =  apply_patch_file(tmp_dir, path, patch)
    
    return backup_file


#replace patch in the file at a line level
def insert_fix(file_path, start_loc, end_loc, patch, project_dir):
    file_path = os.path.join(project_dir, file_path)
    #create backup with original file contents
    shutil.copyfile(file_path, file_path + '.bak')

    with open(file_path, 'r') as file:
        data = file.readlines()

    patched = False
    #replace the lines in the file with the patch
    with open(file_path, 'w') as file:
        for idx, line in enumerate(data):
            if start_loc - 1 <= idx <= end_loc -1:
                if not patched:
                    file.write(patch)
                    patched = True
            else:
                file.write(line)

    return file_path + '.bak'

def apply_patch_file(project_dir, file_path, patch):
    patch = patch.strip()
    file_path = project_dir + file_path
    #create backup with original file contents
    shutil.copyfile(file_path, file_path + '.bak')
    #replace the lines in the file with the patch
    with open(file_path, 'w') as file:
        file.write(patch)
    
    return file_path + '.bak'

def apply_patch_line(tmp_dir, path, start_loc, end_loc, patch):
     files = []
     #create backup with original file contents
     shutil.copyfile(path, path + '.bak')
     patch = patch.strip()
     patched_file = insert_fix(path, int(start_loc), int(end_loc), patch, tmp_dir)
     return path + '.bak'

