A companion tool for my 'Easy Styles Selector (minimal)' ComfyUI node ([agi_custom_nodes](https://github.com/ViTa-Plane/agi_custom_nodes)) that automates workflow/styles .json files generation

It generates thumbnails and workflow.json file from ComfyUI PNG images.

how to use:
  - copy the .py script to an ComfyUI PNG image directory and run it. Follow the menu instructions. Usually the default options are enough
  - copy\move the generated 'thumbnails' folder and 'workflow.json' (you can rename it to example_workflows.json, my_workflows_1.json etc.) to 'ComfyUI\ComfyUI\custom_nodes\agi_custom_nodes\nodes\easy_styles' folder
  for use in 'Easy Styles Selector' node

You can edit "category": "workflows" in the generated .json file if you want to change the category to something else. This is the name of the category your workflows are listed in the 'Easy Styles Selector (minimal)' node
Open ComfyUI add an 'Easy Styles Selector (minimal)' node. the newly added workflows are now inside the 'select category' widget, select 'workflows' (or your custom name )

This script requires the 'pillow' library to process images. 
Open your terminal or command prompt and run one of the following commands:

    Standard Python:      pip install pillow
    Anaconda / Miniconda:  conda install -c conda-forge pillow
    Python 3 (Linux/Mac):  pip3 install pillow
