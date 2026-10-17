A helper tool that extracts the workflow from a standard ComfyUI PNG image file , saves it as .json and convert the image to .jpeg. Useful to compact (archive)  large AI generated image galleries without loosing the workflows.
The script has a build-in menu, uses automated multithreaded batch processing , mirrors the folder structure and keeps the filenames. The script do not alter the original files.

To re-use the saved workflows just drag and drop the .json file in ComfyUI interface.

This script requires the 'pillow' library to process images. 
Open your terminal or command prompt and run one of the following commands:

    Standard Python:      pip install pillow
    Anaconda / Miniconda:  conda install -c conda-forge pillow
    Python 3 (Linux/Mac):  pip3 install pillow
