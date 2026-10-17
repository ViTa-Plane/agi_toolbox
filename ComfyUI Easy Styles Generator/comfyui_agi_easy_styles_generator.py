# v1.0
# ==============================================================================
# DEPENDENCY INSTALLATION REQUIREMENT:
# This script requires the 'Pillow' library for advanced image processing.
# Run the following command in your terminal before execution:
#
#     pip install Pillow
# ==============================================================================

import os
import json
import re
from pathlib import Path
from PIL import Image, ImageOps

DEFAULT_SETTINGS = {
    "silent_mode": "off",
    "mode": "smart",
    "thumbnail_size": [200, 200],
    "thumbnail_file_format": "PNG",
    "thumbnails_cropping": "on",  # Options: "on" (crop to square) or "off" (keep aspect ratio)
    "thumbnail_directory_name": "thumbnails",
    "output_json_file_name": "workflows.json",
    "default_category": "workflows"
}

def load_settings():
    """Loads configuration settings from settings.json or initializes defaults if missing."""
    settings_path = Path("settings.json")
    if not settings_path.exists():
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        return DEFAULT_SETTINGS
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            return {**DEFAULT_SETTINGS, **loaded}
    except Exception as e:
        print(f"Warning: Failed to parse settings.json ({e}). Using defaults.")
        return DEFAULT_SETTINGS

def clean_prompt_text(text):
    """Normalizes prompt formatting and removes common model file extensions and comma-clutter."""
    if not text: return ""
    # Strip paths inside pre-existing inline lora strings first
    text = re.sub(r'<lora:[^>]*[\\/]([^>:]+):', r'<lora:\1:', text, flags=re.IGNORECASE)
    text = re.sub(r'\.(safetensors|ckpt|pt|bin|yaml)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\n\t]+', ' ', text)
    text = re.sub(r',+', ',', text)
    text = re.sub(r'\s*,\s*BREAK\s*,\s*', ' BREAK ', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*,\s*BREAK\b', ' BREAK ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bBREAK\s*,\s*', ' BREAK ', text, flags=re.IGNORECASE)
    text = text.replace(',', ', ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' ,')

def smart_combine(text_list, lora_list=None):
    """Combines tags with BREAKs and prepends active global LoRAs while preserving inline positions."""
    processed_blocks = []
    seen_globally = set()
    final_loras = []
    
    if lora_list:
        for lora in lora_list:
            lora_lower = lora.lower()
            if lora_lower not in seen_globally:
                seen_globally.add(lora_lower)
                final_loras.append(lora)
                name_tokens = re.findall(r'[a-zA-Z0-9]+', lora_lower)
                for token in name_tokens:
                    if len(token) > 2: seen_globally.add(token)

    if text_list:
        for block in text_list:
            if "<lora:" in block:
                block_clean = re.sub(r'<lora:[^>]+>', '', block, flags=re.IGNORECASE)
                for tag in re.split(r',|BREAK', block_clean, flags=re.IGNORECASE):
                    tag_strip = tag.strip().lower()
                    if tag_strip: seen_globally.add(tag_strip)
                processed_blocks.append(block.strip())
                continue

            segments = re.split(r',|BREAK', block, flags=re.IGNORECASE)
            unique_block_tags = []
            for tag in segments:
                tag = tag.strip()
                if not tag: continue
                tag_lower = tag.lower()
                if tag_lower not in seen_globally:
                    seen_globally.add(tag_lower)
                    unique_block_tags.append(tag)
                    for sub_token in re.findall(r'[a-zA-Z0-9]+', tag_lower):
                        if len(sub_token) > 3: seen_globally.add(sub_token)
            if unique_block_tags:
                processed_blocks.append(", ".join(unique_block_tags))
                
    main_prompt = " BREAK ".join(processed_blocks)
    return f'{" ".join(final_loras)} {main_prompt}'.strip() if final_loras else main_prompt

def standard_combine(text_list, lora_list=None):
    """Combines text lists via commas for Clean/Rich modes without breaking alignment."""
    seen_loras = set()
    prefix_loras = []
    
    for block in text_list:
        for match in re.findall(r'<lora:[^>]+>', block, flags=re.IGNORECASE):
            seen_loras.add(match.lower())
            
    if lora_list:
        for lora in lora_list:
            if lora.lower() not in seen_loras:
                prefix_loras.append(lora)
                seen_loras.add(lora.lower())
                
    main_prompt = ", ".join(text_list)
    return f'{" ".join(prefix_loras)}, {main_prompt}'.strip() if prefix_loras else main_prompt

def is_likely_prompt(text):
    if not isinstance(text, str): return False
    text = text.strip()
    if len(text) < 2 or re.fullmatch(r'.*\.(safetensors|ckpt|pt|yaml|bin|json)', text.lower()) or re.fullmatch(r'[\d,.\s]+', text):
        return False
    return True

def extract_loras_deeply(data, node_type, node_title, default_widget="unknown"):
    loras = []
    if isinstance(data, dict):
        if "lora" in data and "on" in data:
            lora_path = str(data.get("lora", ""))
            strength = data.get("strength", 1.0)
            if lora_path:
                # Use Path to accurately peel off folder subdirectories and extensions
                lora_name = Path(lora_path).stem
                loras.append({
                    "node_type": node_type, "node_title": node_title,
                    "widget_name": default_widget, "enabled": data.get("on") is True,
                    "text": f"<lora:{lora_name}:{strength}>"
                })
        else:
            for key, value in data.items():
                loras.extend(extract_loras_deeply(value, node_type, node_title, key if not key.isdigit() else default_widget))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            loras.extend(extract_loras_deeply(item, node_type, node_title, f"{default_widget}_{idx}"))
    return loras

def is_negative_content(text, node_title):
    text_lower = text.lower()
    node_title_lower = str(node_title).lower()
    if "negative" in node_title_lower: return True
    neg_keywords = ["worst quality", "low quality", "bad anatomy", "embedding:", "bad hands"]
    return any(kw in text_lower for kw in neg_keywords)

def process_comfy_images():
    cfg = load_settings()
    silent = str(cfg.get("silent_mode")).strip().lower() == "on"
    
    mode_choice = str(cfg.get("mode")).strip().lower()
    if not silent:
        print("--- ComfyUI Deep Metadata Extractor ---")
        print("1. [S]mart Mode (BREAKs + Token Cleaning)")
        print("2. [C]lean Mode (Comma list)")
        print("3. [R]ich Mode (Full objects)")
        user_input = input(f"Select mode [Current config: {mode_choice}]: ").strip().lower()
        if user_input in ('1', 's', '2', 'c', '3', 'r'):
            mode_choice = user_input

    is_smart = mode_choice not in ('2', 'c', '3', 'r')
    is_rich = mode_choice in ('3', 'r')
    show_detected = is_rich or mode_choice in ('2', 'c')
    mode_label = "SMART" if is_smart else ("RICH" if is_rich else "CLEAN")

    base_dir = Path.cwd()
    thumb_dir = base_dir / cfg.get("thumbnail_directory_name", "thumbnails")
    thumb_dir.mkdir(exist_ok=True)
    
    all_workflows = []
    node_blacklist = {"SaveImage", "LoadImage", "LoadAndResizeImage", "ImageResize", "DPRandomGenerator", "PrimitiveStringMultiline", "KSampler", "SDXL Empty Latent Image"}

    print(f"\nProcessing assets using configuration profile [{mode_label}]...")

    for img_path in list(base_dir.glob("*.png")):
        if img_path.name.startswith("tn_") or thumb_dir.name in img_path.parts: continue
        try:
            with Image.open(img_path) as img:
                prompt_metadata = img.info.get('prompt')
                workflow_metadata = img.info.get('workflow')
                if not prompt_metadata and not workflow_metadata: continue

                # Configured Thumbnail Parameters
                t_size = tuple(cfg.get("thumbnail_size", [200, 200]))
                t_format = cfg.get("thumbnail_file_format", "PNG")
                t_ext = t_format.lower() if t_format.lower() != "jpeg" else "jpg"
                thumb_path = thumb_dir / f"tn_{img_path.stem}.{t_ext}"
                
                # Check simplified on/off cropping rules
                crop_setting = str(cfg.get("thumbnails_cropping")).strip().lower()
                if crop_setting == "on":
                    ImageOps.fit(img, t_size, Image.Resampling.LANCZOS).save(thumb_path, t_format)
                else:
                    img_copy = img.copy()
                    img_copy.thumbnail(t_size, Image.Resampling.LANCZOS)
                    img_copy.save(thumb_path, t_format)

                entry = {
                    "name": img_path.stem, 
                    "category": cfg.get("default_category", "workflows"), 
                    "comment": "", "seed": "", "prompt": "", "negative_prompt": "", 
                    "thumbnail": thumb_path.name, "params": {"model_name": ""}
                }
                if show_detected: entry["detected_prompts"] = {"positive": [], "negative": []}
                if is_rich: entry["detected_loras"] = []

                raw_prompts = []
                found_lora_objects = []

                # SCAN WORKFLOW
                if workflow_metadata:
                    for node in json.loads(workflow_metadata).get('nodes', []):
                        n_type, n_title = node.get('type', ''), node.get('title', node.get('type', ''))
                        if n_type in node_blacklist: continue
                        widgets = node.get('widgets_values', [])
                        if isinstance(widgets, list):
                            for idx, w in enumerate(widgets):
                                found_lora_objects.extend(extract_loras_deeply(w, n_type, n_title, f"widget_{idx}"))
                                if isinstance(w, str) and is_likely_prompt(w): raw_prompts.append((clean_prompt_text(w), n_type, n_title))

                # SCAN PROMPT
                if prompt_metadata:
                    p_data = json.loads(prompt_metadata)
                    for node in p_data.values():
                        inputs = node.get('inputs', {})
                        c_type = node.get('class_type', '')
                        title = node.get('_meta', {}).get('title', c_type)
                        if c_type in ["KSampler", "KSamplerAdvanced"]:
                            entry["seed"] = str(inputs.get('seed') or inputs.get('noise_seed', ''))
                            for k, v in inputs.items():
                                if not isinstance(v, (list, dict)): entry["params"][k] = v
                        elif c_type == "CheckpointLoaderSimple":
                            entry["params"]["model_name"] = Path(str(inputs.get('ckpt_name', ''))).stem
                        for key, val in inputs.items():
                            found_lora_objects.extend(extract_loras_deeply(val, c_type, title, key))
                        if c_type not in node_blacklist:
                            for val in inputs.values():
                                if isinstance(val, str) and is_likely_prompt(val): raw_prompts.append((clean_prompt_text(val), c_type, title))

                # DEDUPLICATE GLOBAL LORAS
                seen_lora_texts = set()
                deduped_lora_objects = []
                for obj in found_lora_objects:
                    sig = obj["text"].lower()
                    if sig not in seen_lora_texts:
                        seen_lora_texts.add(sig); deduped_lora_objects.append(obj)
                active_loras_strings = [obj["text"] for obj in deduped_lora_objects if obj["enabled"]]
                if is_rich: entry["detected_loras"] = deduped_lora_objects

                # UNIFIED DEDUPLICATION LOGIC WITH LORA PRIORITY
                unique_prompt_map = {"positive": {}, "negative": {}}
                for txt, n_type, n_title in raw_prompts:
                    bucket = "negative" if is_negative_content(txt, n_title) else "positive"
                    clean_key = re.sub(r'<lora:[^>]+>\s*', '', txt, flags=re.IGNORECASE).strip().lower()
                    if not clean_key: continue
                    
                    if clean_key not in unique_prompt_map[bucket]:
                        unique_prompt_map[bucket][clean_key] = (txt, n_type, n_title)
                    else:
                        existing_txt = unique_prompt_map[bucket][clean_key][0]
                        if "<lora:" in txt and "<lora:" not in existing_txt:
                            unique_prompt_map[bucket][clean_key] = (txt, n_type, n_title)

                # BUILD FINAL LISTS
                final_texts = {"positive": [], "negative": []}
                for bucket in ["positive", "negative"]:
                    for txt, n_type, n_title in unique_prompt_map[bucket].values():
                        final_texts[bucket].append(txt)
                        if show_detected:
                            entry["detected_prompts"][bucket].append({"node_type": n_type, "node_title": n_title, "text": txt} if is_rich else txt)

                # APPLY MODE-SPECIFIC FORMATTING
                if is_smart:
                    entry["prompt"] = smart_combine(final_texts["positive"], active_loras_strings)
                    entry["negative_prompt"] = smart_combine(final_texts["negative"])
                else:
                    entry["prompt"] = standard_combine(final_texts["positive"], active_loras_strings)
                    entry["negative_prompt"] = standard_combine(final_texts["negative"])

                if "size" not in entry["params"]: entry["params"]["size"] = f"{img.size[0]}x{img.size[1]}"
                all_workflows.append(entry)
                print(f"Processed: {img_path.name}")

        except Exception as e: print(f"Error {img_path.name}: {e}")

    output_file = cfg.get("output_json_file_name", "workflows.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_workflows, f, indent=4)
    
    print(f"\nSuccess: Exported {len(all_workflows)} items into '{output_file}'.")

if __name__ == "__main__":
    process_comfy_images()
    if str(load_settings().get("silent_mode")).strip().lower() != "on":
        input("\nFinished. Press Enter to exit...")