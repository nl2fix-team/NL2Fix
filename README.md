## Supplementary Material for "NL2Fix: Evaluating LLMs for Resolving Bugs From Natural Language Intent" 

This repository contains supplementary materials for our ICSE2024 submission. We include the NL2Fix dataset, along with scripts used to generate and evaluate generated patches against trigger tests and regression tests. 

### Inluded Materials
- `datasets/defects4j/nl2fix_dataset.json` contains the NL2Fix dataset. The dataset is a json file with issue metadata, including: issue title, issue description, the original buggy method, and the ground truth fix.
- [embeddings.zip](https://zenodo.org/record/7787107#.ZCX5Gy-B19g) on zenodo contains the embeddings used for RQ4. The embeddings are generated using the `generate_embeddings.py` script. The embeddings are used to calculate the cosine similarity between the original buggy method and the generated patch.
- [generated-patches.zip](https://zenodo.org/record/7787107#.ZCX5ni-B19h) on zenodo includes the generated patches for the 283 issues in the dataset. The patches are generated using the `generate_patches.py` script. These patches are used for RQ 1-4



### Patch Generation Scripts
#### Step 1: export OpenAI key

Add your OpenAI api key to a .env file
```
 export OPENAI_API_KEY = 'YOUR-KEY'
```

#### Step 2: Generate Patch Candidates
Using the dataset json file: nl2fix_dataset.json :

```
python3 generate_patches.py --input ../datasets/defects4j/nl2fix_dataset.json --output ../output/candidate-patches.json --max_num_patches 100 --prompt issue_description  --sampling_temp 0.8 --model edit
```

Some of the options include `--prompt` to set the prompting strategy, `--model` for the model type (edit, completion, gpt-3.5),  `--sampling_temp`,`--num_examples` to select how many data points to process, `--use_k_shot`, `--shot_selection_method`, `--k_shot` number of shots. Arguments are documented in the generate_patches.py file.

### Patch Evaluation Scripts
#### Step 1: Clone project and setup Docker container

```
git clone https://github.com/nl2fix-team/NL2Fix
```

Download Docker: https://www.docker.com

To build an image, in the NL2Fix/ directory run:
 
```
cd ./NL2Fix
docker build ./ --tag nl2fix
```

To create a container from the image:

```
sudo docker run -it --name nl2fix_container nl2fix
```

A few helpful docker commands:
- To run the container

```
docker exec -it nl2fix_container /bin/bash
```

- To copy data into and out of the container
```
docker cp nl2fix_container:/nl2fix/nl2fix/Path/To/Source ./Destination
```

#### Step 2: Validate Patch Candidates

```
python3 validate.py --patch_file ../datasets/defects4j/patches.json  --level line --tests all 
```

options for --level includes `line` for method or line level patches or `file` for whole file patches. You can choose to run `all` --tests or `trigger` --tests only. --num_examples to select how many datapoints to process. 


#### 2.1 Calculate summary level statistics
summary_stats.py is a script to calculate summary level pass@k statistics for the validation output.

```
python3 summary_stats.py --i ./validation-output-folder 
```

options for --i include the path to the validation output directory and --prune_compilation to generate pass@k with for patches that compile.

