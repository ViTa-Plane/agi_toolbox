# v4.2.1 (Multithreaded)

"""
ComfyUI Workflow Extractor & JPEG Converter (Multithreaded)
==========================================================

DEPENDENCY INSTALLATION:
This script requires the 'pillow' library to process images. 
Open your terminal or command prompt and run one of the following commands:

    Standard Python:      pip install pillow
    Anaconda / Miniconda:  conda install -c conda-forge pillow
    Python 3 (Linux/Mac):  pip3 install pillow

You can also create a virtual environment first if preferred:
    python -m venv venv
    source venv/bin/activate  # On Windows use: venv\\Scripts\\activate
    pip install pillow
"""

import os
import json
import argparse
import sys
import time
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

def extract_comfyui_workflow(png_path, target_dir, skip_existing=False, quiet=False):
    """
    Extracts the ComfyUI workflow JSON from a single PNG file 
    and saves it into the designated target directory.
    """
    if not os.path.exists(png_path):
        if not quiet: print(f"[-] Error: The file '{png_path}' does not exist.")
        return "failed"

    base_name = os.path.splitext(os.path.basename(png_path))[0]
    output_json_path = os.path.join(target_dir, f"{base_name}_workflow.json")

    if skip_existing and os.path.exists(output_json_path):
        if not quiet: print(f"[Skipped] JSON already exists: '{output_json_path}'")
        return "skipped"

    try:
        with Image.open(png_path) as img:
            metadata = img.info
            
            if not metadata or 'workflow' not in metadata:
                if not quiet: print(f"[-] No ComfyUI workflow metadata found in '{png_path}'.")
                return "failed"
            
            workflow_json = json.loads(metadata['workflow'])
            
    except Exception as e:
        if not quiet: print(f"[-] Error reading '{png_path}': {e}")
        return "failed"

    os.makedirs(target_dir, exist_ok=True)

    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(workflow_json, f, indent=4, ensure_ascii=False)
        print(f"[+] Extracted JSON: '{png_path}' -> '{output_json_path}'")
        return "success"
    except Exception as e:
        print(f"[-] Failed to write JSON file for '{png_path}': {e}")
        return "failed"


def convert_to_jpeg(png_path, target_dir, quality=90, skip_existing=False, quiet=False):
    """
    Converts a PNG file to JPEG format and saves it into the target directory.
    """
    if not os.path.exists(png_path):
        return "failed"

    base_name = os.path.splitext(os.path.basename(png_path))[0]
    jpeg_path = os.path.join(target_dir, f"{base_name}.jpg")

    if skip_existing and os.path.exists(jpeg_path):
        if not quiet: print(f"[Skipped] JPEG already exists: '{jpeg_path}'")
        return "skipped"

    try:
        os.makedirs(target_dir, exist_ok=True)

        with Image.open(png_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = img.convert('RGB')
            else:
                rgb_img = img
            
            rgb_img.save(jpeg_path, 'JPEG', quality=quality)
            print(f"[+] Converted JPEG: '{png_path}' -> '{jpeg_path}' (Quality: {quality})")
            return "success"
    except Exception as e:
        print(f"[-] Failed to convert '{png_path}' to JPEG: {e}")
        return "failed"


def process_single_file_task(task_type, file_path, target_output_dir, quality, skip_existing):
    """
    Worker task function executed by threads (or sequentially). Combines workflow 
    extraction and/or JPEG conversion for a single target file.
    """
    wf_status = "none"
    jpg_status = "none"

    if task_type in ('extract_only', 'full_process'):
        quiet_val = True if task_type == 'full_process' else False
        wf_status = extract_comfyui_workflow(file_path, target_output_dir, skip_existing=skip_existing, quiet=quiet_val)

    if task_type == 'full_process':
        jpg_status = convert_to_jpeg(file_path, target_output_dir, quality=quality, skip_existing=skip_existing, quiet=True)

    return wf_status, jpg_status


def get_all_png_files_recursive(root_dir):
    """
    Recursively scans the root directory and all subdirectories for PNG files.
    Returns a list of tuples: (file_path, parent_directory)
    """
    png_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        dir_parts = os.path.normpath(dirpath).split(os.sep)
        if "workflows" in dir_parts:
            continue
            
        for filename in filenames:
            if filename.lower().endswith('.png'):
                full_path = os.path.join(dirpath, filename)
                png_files.append((full_path, dirpath))
    return png_files


def get_quality_input():
    """Helper prompt to safely grab JPEG quality setting."""
    quality_input = input("Enter JPEG quality (1-100) [Default: 90]: ").strip()
    if quality_input == "":
        return 90
    try:
        quality = int(quality_input)
        if 1 <= quality <= 100:
            return quality
        print("Quality must be between 1 and 100. Using default (90).")
    except ValueError:
        print("Invalid input. Using default (90).")
    return 90


def get_skip_input():
    """Helper prompt to check if the user wants to skip existing output files."""
    skip_choice = input("Skip processing if output file already exists? (y/n) [Default: y]: ").strip().lower()
    return skip_choice != 'n'


def run_menu(force_single_thread=False):
    """Displays the configuration setup followed by execution options."""
    print("======================================================")
    print(" ComfyUI Tool - Configuration Setup")
    print("======================================================")
    
    # 1. Source Input Path Selection
    print(" [1/2] SOURCE PATH")
    print(" Leave empty to scan the CURRENT folder, or paste a custom folder/file path.")
    user_path = input(" Enter source path: ").strip().strip('"').strip("'")
    target_root = "." if user_path == "" else user_path

    if not os.path.exists(target_root):
        print(f"\n[-] Error: The source path '{target_root}' does not exist.")
        return

    # 2. Destination Output Folder Selection
    print("\n [2/2] OUTPUT PATH")
    print(" Leave empty to save inside the script's '.\\workflows\\' folder,")
    print(" OR enter/drag a specific custom folder path.")
    custom_output_path = input(" Enter custom output folder path: ").strip().strip('"').strip("'")
    
    custom_dest = os.path.abspath(os.path.join(".", "workflows")) if custom_output_path == "" else os.path.abspath(custom_output_path)

    # Resolve target items based on source path type
    if os.path.isfile(target_root):
        if not target_root.lower().endswith('.png'):
            print("[-] Error: Selected file is not a PNG file.")
            return
        png_data = [(target_root, os.path.dirname(target_root) or ".")]
    else:
        png_data = get_all_png_files_recursive(target_root)

    if not png_data:
        print(f"\nNo PNG files found at the target destination: '{target_root}'")
        return

    print("\n======================================================")
    print(f" ComfyUI Tool Options - Targets Loaded: {len(png_data)} file(s)")
    print(f" Destination Folder Set To: '{custom_dest}'")
    if force_single_thread:
        print(" Execution Mode: FORCE SINGLE-THREADED")
    print("======================================================")
    print(" 1. Extract: Save workflows (.json) inside the destination folder")
    print(" 2. Full:  Save Workflows and sample JPEGs inside the destination folder")
    print(" 3. Full + Mirror Structure: Extract & convert while recreating source subfolder structures inside destination")
    print(" 4. Exit")
    print("======================================================")
    
    choice = input("Select an option (1-4): ").strip()
    print("")

    if choice not in ('1', '2', '3'):
        if choice == '4':
            print("Exiting.")
        else:
            print("Invalid option selected.")
        return

    task_type = 'extract_only' if choice == '1' else 'full_process'
    quality = 90 if choice == '1' else get_quality_input()
    skip_existing = get_skip_input()

    workflow_count = 0
    jpeg_count = 0
    skipped_workflow_count = 0
    skipped_jpeg_count = 0

    root_dir_abs = os.path.abspath(target_root if os.path.isdir(target_root) else os.path.dirname(target_root) or ".")

    # START TIMING BLOCK
    start_time = time.time()

    # --- MODE A: FORCE SINGLE THREADED ---
    if force_single_thread:
        execution_mode_str = "Single-Threaded"
        print(f"\n[!] Initializing sequential loop (Single-Threaded). Processing files...\n")
        for file_path, parent_dir in png_data:
            if choice in ('1', '2'):
                target_output_dir = custom_dest
            else:
                parent_dir_abs = os.path.abspath(parent_dir)
                relative_subpath = os.path.relpath(parent_dir_abs, root_dir_abs)
                target_output_dir = custom_dest if relative_subpath == "." else os.path.join(custom_dest, relative_subpath)

            try:
                wf_res, jpg_res = process_single_file_task(task_type, file_path, target_output_dir, quality, skip_existing)
                if wf_res == "success": workflow_count += 1
                elif wf_res == "skipped": skipped_workflow_count += 1
                if jpg_res == "success": jpeg_count += 1
                elif jpg_res == "skipped": skipped_jpeg_count += 1
            except Exception as exc:
                print(f"[-] Processing failed for '{file_path}': {exc}")

    # --- MODE B: MULTITHREADED POOL ---
    else:
        execution_mode_str = "Multithreaded"
        print(f"\n[!] Initializing multithreaded worker pool. Processing files...\n")
        with ThreadPoolExecutor() as executor:
            futures = {}
            for file_path, parent_dir in png_data:
                if choice in ('1', '2'):
                    target_output_dir = custom_dest
                else:
                    parent_dir_abs = os.path.abspath(parent_dir)
                    relative_subpath = os.path.relpath(parent_dir_abs, root_dir_abs)
                    target_output_dir = custom_dest if relative_subpath == "." else os.path.join(custom_dest, relative_subpath)

                future = executor.submit(
                    process_single_file_task, 
                    task_type, file_path, target_output_dir, quality, skip_existing
                )
                futures[future] = file_path

            for future in as_completed(futures):
                try:
                    wf_res, jpg_res = future.result()
                    if wf_res == "success": workflow_count += 1
                    elif wf_res == "skipped": skipped_workflow_count += 1
                    if jpg_res == "success": jpeg_count += 1
                    elif jpg_res == "skipped": skipped_jpeg_count += 1
                except Exception as exc:
                    failed_file = futures[future]
                    print(f"[-] Thread generated an unhandled exception for '{failed_file}': {exc}")

    # END TIMING BLOCK
    elapsed_time = time.time() - start_time

    # Generate telemetry summary with explicit execution mode tracking
    print(f"\n=========================================")
    print(f" PROCESS SUMMARY")
    print(f"=========================================")
    print(f" Execution Mode:       {execution_mode_str}")
    print(f" Total Execution Time: {elapsed_time:.2f} seconds")
    if choice == '1':
        print(f" Workflows Extracted:  {workflow_count} | Already existed/Skipped: {skipped_workflow_count}")
    else:
        print(f" Workflows Extracted:  {workflow_count} (Skipped: {skipped_workflow_count})")
        print(f" JPEGs Converted:      {jpeg_count} (Skipped: {skipped_jpeg_count})")
    print(f"=========================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursively extract ComfyUI workflows and/or convert images to JPEG.")
    parser.add_argument("png_file", nargs="?", help="Optional: Path to a specific PNG image file.", default=None)
    parser.add_argument("-o", "--output", help="Optional: Specific folder to save output (single file mode only).", default=None)
    parser.add_argument("-j", "--jpeg", action="store_true", help="Optional: Force JPEG conversion (single file mode only).")
    parser.add_argument("-q", "--quality", type=int, default=90, help="Optional: JPEG compression quality (default: 90).")
    parser.add_argument("-s", "--skip", action="store_true", help="Optional: Skip existing files (single file mode only).")
    parser.add_argument("-st", "--single-thread", action="store_true", help="Disable multithreading and process files sequentially.")
    
    args = parser.parse_args()
    
    try:
        if args.png_file is None:
            run_menu(force_single_thread=args.single_thread)
        else:
            # Single file explicit command bypasses worker logic entirely
            start_time = time.time()
            parent_directory = os.path.dirname(args.png_file) or "."
            target_dir = args.output if args.output else os.path.abspath(os.path.join(".", "workflows"))
            
            extract_comfyui_workflow(args.png_file, target_dir, skip_existing=args.skip)
            if args.jpeg:
                convert_to_jpeg(args.png_file, target_dir, quality=args.quality, skip_existing=args.skip)
            
            print(f"\n[Done] Finished single file process in {time.time() - start_time:.2f} seconds (Single-Threaded).")
                
    finally:
        print("\n-----------------------------------------")
        input("Execution finished. Press Enter to close...")