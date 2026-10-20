# v2.2
import json
import os
import platform
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

DEFAULT_TARGET_JSON = "anime_heroine.json"


class NestedJSONFillerApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Easy Character Template Editor")
    self.root.geometry("950x900")
    self.root.minsize(750, 700)

    self.raw_loaded_data = None
    self.target_blocks = []
    self.current_block_index = tk.IntVar(value=0)

    self.target_data = {}
    self.entries = {}
    self.entry_widgets = {}
    self.tab_mapping = {}
    self.tab_frames = {}
    self.raw_json_text = None

    self.search_matches = []
    self.search_index = 0
    self.find_dialog = None
    self.find_var = None
    self.replace_var = None

    self.create_menu()
    self.create_widgets()
    self.setup_shortcuts()
    self.load_data(is_initial_load=True)

  def create_menu(self):
    menubar = tk.Menu(self.root)

    # --- File Menu ---
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(
        label="Open Template JSON...",
        command=lambda: self.browse_file("target"),
        accelerator="Ctrl+O",
    )
    file_menu.add_separator()
    file_menu.add_command(
        label="Save (Update Current Block)",
        command=self.save_update_current,
        accelerator="Ctrl+S",
    )
    file_menu.add_command(
        label="Save As New File...", command=self.save_as_new
    )
    file_menu.add_command(
        label="Append to Existing File...", command=self.save_append
    )
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=self.root.quit)
    menubar.add_cascade(label="File", menu=file_menu)

    # --- Search Menu ---
    search_menu = tk.Menu(menubar, tearoff=0)
    search_menu.add_command(
        label="Find & Replace...",
        command=self.open_find_replace_dialog,
        accelerator="Ctrl+F",
    )
    menubar.add_cascade(label="Search", menu=search_menu)

    # --- Help Menu ---
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About", command=self.open_about_dialog)
    menubar.add_cascade(label="Help", menu=help_menu)

    self.root.config(menu=menubar)

  def setup_shortcuts(self):
    self.root.bind_all("<Control-f>", lambda e: self.open_find_replace_dialog())
    self.root.bind_all("<Control-s>", lambda e: self.save_update_current())
    self.root.bind_all("<Control-o>", lambda e: self.browse_file("target"))

  def open_about_dialog(self):
    about_win = tk.Toplevel(self.root)
    about_win.title("Easy Character Template Editor")
    about_win.geometry("420x240")
    about_win.resizable(False, False)
    about_win.transient(self.root)
    about_win.grab_set()

    # Padding frame
    content_frame = ttk.Frame(about_win, padding=15)
    content_frame.pack(fill="both", expand=True)

    ttk.Label(
        content_frame,
        text="Easy Character Template Editor",
        font=("Arial", 11, "bold"),
    ).pack(pady=(0, 5))

    desc_text = (
        "A desktop GUI tool designed to edit multi-block flat and nested "
        "JSON template files with real-time preview, search & replace, "
        "and flexible block-selection management."
    )
    lbl_desc = ttk.Label(content_frame, text=desc_text, wraplength=380, justify="center")
    lbl_desc.pack(pady=(0, 10))

    ttk.Label(content_frame, text="GitHub Repository:", font=("Arial", 9, "bold")).pack()

    link_lbl = ttk.Label(
        content_frame,
        text="https://github.com/ViTa-Plane/agi_toolbox",
        foreground="blue",
        cursor="hand2",
        font=("Arial", 9, "underline"),
    )
    link_lbl.pack(pady=(2, 15))
    link_lbl.bind(
        "<Button-1>",
        lambda e: webbrowser.open_new("https://github.com/ViTa-Plane/agi_toolbox"),
    )

    ttk.Button(content_frame, text="Close", command=about_win.destroy, width=10).pack()

  def create_widgets(self):
    # --- Status & Block Selector Frame ---
    info_frame = ttk.LabelFrame(
        self.root, text=" Loaded Template & Block Selection ", padding=8
    )
    info_frame.pack(fill="x", padx=10, pady=8)

    ttk.Label(info_frame, text="File Path:").grid(
        row=0, column=0, sticky="w", padx=5, pady=2
    )
    self.target_path_var = tk.StringVar(value=DEFAULT_TARGET_JSON)
    ttk.Label(
        info_frame, textvariable=self.target_path_var, foreground="blue"
    ).grid(row=0, column=1, sticky="w", padx=5, pady=2)

    # Dropdown for selecting block
    ttk.Label(info_frame, text="Select Block:").grid(
        row=1, column=0, sticky="w", padx=5, pady=2
    )
    
    selector_subframe = ttk.Frame(info_frame)
    selector_subframe.grid(row=1, column=1, sticky="w", padx=5, pady=2)

    self.block_combo = ttk.Combobox(
        selector_subframe,
        state="readonly",
        width=55,
    )
    self.block_combo.pack(side="left", padx=(0, 5))
    self.block_combo.bind("<<ComboboxSelected>>", self.on_block_selected)

    self.block_counter_lbl = ttk.Label(selector_subframe, text="(Index: 0)")
    self.block_counter_lbl.pack(side="left")

    # --- Main Vertical PanedWindow ---
    paned_window = ttk.PanedWindow(self.root, orient="vertical")
    paned_window.pack(fill="both", expand=True, padx=10, pady=5)

    # Top Pane: Notebook
    form_container = ttk.LabelFrame(
        paned_window, text=" Template Properties by Category ", padding=5
    )
    paned_window.add(form_container, weight=3)

    self.notebook = ttk.Notebook(form_container)
    self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

    # Bottom Pane: Raw JSON Preview Panel
    raw_container = ttk.LabelFrame(
        paned_window, text=" Live Raw JSON Preview ", padding=5
    )
    paned_window.add(raw_container, weight=2)

    raw_frame = ttk.Frame(raw_container, padding=5)
    raw_frame.pack(fill="both", expand=True)

    self.raw_json_text = tk.Text(raw_frame, wrap="none", font=("Consolas", 9))
    raw_scroll_y = ttk.Scrollbar(
        raw_frame, orient="vertical", command=self.raw_json_text.yview
    )
    raw_scroll_x = ttk.Scrollbar(
        raw_frame, orient="horizontal", command=self.raw_json_text.xview
    )
    self.raw_json_text.configure(
        yscrollcommand=raw_scroll_y.set, xscrollcommand=raw_scroll_x.set
    )

    self.raw_json_text.grid(row=0, column=0, sticky="nsew")
    raw_scroll_y.grid(row=0, column=1, sticky="ns")
    raw_scroll_x.grid(row=1, column=0, sticky="ew")

    raw_frame.rowconfigure(0, weight=1)
    raw_frame.columnconfigure(0, weight=1)

    current_os = platform.system()
    if current_os == "Darwin":
      self.raw_json_text.bind("<MouseWheel>", self._on_raw_mousewheel_mac)
    elif current_os == "Linux":
      self.raw_json_text.bind("<Button-4>", self._on_raw_mousewheel_linux_up)
      self.raw_json_text.bind("<Button-5>", self._on_raw_mousewheel_linux_down)
    else:
      self.raw_json_text.bind("<MouseWheel>", self._on_raw_mousewheel_windows)

  def _on_raw_mousewheel_windows(self, event):
    self.raw_json_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
    return "break"

  def _on_raw_mousewheel_mac(self, event):
    self.raw_json_text.yview_scroll(int(-1 * event.delta), "units")
    return "break"

  def _on_raw_mousewheel_linux_up(self, event):
    self.raw_json_text.yview_scroll(-1, "units")
    return "break"

  def _on_raw_mousewheel_linux_down(self, event):
    self.raw_json_text.yview_scroll(1, "units")
    return "break"

  def bind_canvas_mousewheel(self, canvas):
    current_os = platform.system()
    if current_os == "Darwin":
      canvas.bind("<MouseWheel>", lambda e: (canvas.yview_scroll(int(-1 * e.delta), "units"), "break"))
    elif current_os == "Linux":
      canvas.bind("<Button-4>", lambda e: (canvas.yview_scroll(-1, "units"), "break"))
      canvas.bind("<Button-5>", lambda e: (canvas.yview_scroll(1, "units"), "break"))
    else:
      canvas.bind("<MouseWheel>", lambda e: (canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"), "break"))

  def browse_file(self, file_type):
    filename = filedialog.askopenfilename(
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if filename:
      if file_type == "target":
        self.target_path_var.set(filename)
      self.load_data()

  def load_data(self, is_initial_load=False):
    target_path = self.target_path_var.get()

    # Silently handle missing default file on startup without raising errors
    if is_initial_load and not os.path.exists(target_path):
      self.target_path_var.set("No File Loaded (Open a JSON file)")
      self.target_blocks = [{}]
      self.populate_block_selector()
      return

    try:
      with open(target_path, "r", encoding="utf-8") as f:
        self.raw_loaded_data = json.load(f)

        if isinstance(self.raw_loaded_data, list):
          self.target_blocks = [item for item in self.raw_loaded_data if isinstance(item, dict)]
          if not self.target_blocks:
            self.target_blocks = [{}]
        elif isinstance(self.raw_loaded_data, dict):
          self.target_blocks = [self.raw_loaded_data]
        else:
          self.target_blocks = [{}]
    except Exception as e:
      if not is_initial_load:
        messagebox.showerror(
            "Error", f"Could not load target template JSON:\n{str(e)}"
        )
      self.target_blocks = [{}]

    self.populate_block_selector()

  def get_block_name(self, block):
    flat = self.flatten_dict(block)
    
    for k, v in flat.items():
      lower_k = k.lower()
      if lower_k == "name" or lower_k.endswith(".name") or lower_k == "title" or lower_k.endswith(".title"):
        if v not in [None, ""]:
          return str(v)

    for k, v in flat.items():
      lower_k = k.lower()
      if "name" in lower_k or "title" in lower_k:
        if v not in [None, ""]:
          return str(v)

    return None

  def populate_block_selector(self):
    combo_values = []
    for idx, block in enumerate(self.target_blocks):
      name_val = self.get_block_name(block)
      if name_val:
        combo_values.append(name_val)
      else:
        combo_values.append(f"Block [{idx}]")

    self.block_combo["values"] = combo_values
    if combo_values:
      self.block_combo.current(0)
      self.current_block_index.set(0)

    self.load_active_block()

  def on_block_selected(self, event):
    selected_idx = self.block_combo.current()
    if selected_idx != -1:
      self.current_block_index.set(selected_idx)
      self.load_active_block()

  def load_active_block(self):
    idx = self.current_block_index.get()

    if 0 <= idx < len(self.target_blocks):
      self.target_data = self.target_blocks[idx]
    else:
      self.target_data = {}

    total = len(self.target_blocks)
    self.block_counter_lbl.config(text=f"(Index: {idx} of {total - 1})")
    self.build_form()

  def flatten_dict(self, d, parent_key="", sep="."):
    items = []
    for k, v in d.items():
      new_key = f"{parent_key}{sep}{k}" if parent_key else k
      if isinstance(v, dict):
        items.extend(self.flatten_dict(v, new_key, sep=sep).items())
      else:
        items.append((new_key, v))
    return dict(items)

  def unflatten_dict(self, d, sep="."):
    result = {}
    for path, val in d.items():
      parts = path.split(sep)
      d_current = result
      for part in parts[:-1]:
        if part not in d_current:
          d_current[part] = {}
        d_current = d_current[part]
      try:
        if "." in str(val):
          val = float(val)
        else:
          val = int(val)
      except ValueError:
        pass
      d_current[parts[-1]] = val
    return result

  def build_form(self):
    for tab_id in self.notebook.tabs():
      self.notebook.forget(tab_id)

    self.entries.clear()
    self.entry_widgets.clear()
    self.tab_mapping.clear()
    self.tab_frames.clear()

    flat_target = self.flatten_dict(self.target_data)

    sections = {}
    for flat_key in flat_target.keys():
      if "." in flat_key:
        sec = flat_key.split(".")[0]
      else:
        sec = "GENERAL"
      sections.setdefault(sec, []).append(flat_key)

    for section, keys in sections.items():
      sec_title = "GENERAL" if section == "GENERAL" else section.upper()

      tab_frame = ttk.Frame(self.notebook)
      self.notebook.add(tab_frame, text=sec_title)

      canvas = tk.Canvas(tab_frame, highlightthickness=0)
      scrollbar = ttk.Scrollbar(
          tab_frame, orient="vertical", command=canvas.yview
      )
      scrollable_sub_frame = ttk.Frame(canvas, padding=10)

      scrollable_sub_frame.bind(
          "<Configure>",
          lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
      )
      canvas_window = canvas.create_window(
          (0, 0), window=scrollable_sub_frame, anchor="nw"
      )
      canvas.bind(
          "<Configure>",
          lambda e, c=canvas, cw=canvas_window: c.itemconfig(
              cw, width=e.width
          ),
      )
      canvas.configure(yscrollcommand=scrollbar.set)

      self.bind_canvas_mousewheel(canvas)
      self.bind_canvas_mousewheel(scrollable_sub_frame)

      canvas.pack(side="left", fill="both", expand=True)
      scrollbar.pack(side="right", fill="y")

      self.tab_frames[section] = tab_frame

      header_frame = ttk.Frame(scrollable_sub_frame)
      header_frame.pack(fill="x", padx=5, pady=(2, 10))
      ttk.Label(
          header_frame,
          text=f"Properties in [{sec_title}]",
          font=("Arial", 9, "bold"),
      ).pack(side="left")
      ttk.Button(
          header_frame,
          text="+ Add Field",
          width=10,
          command=lambda s=section: self.prompt_add_field(s),
      ).pack(side="right")

      for flat_key in keys:
        current_val = flat_target[flat_key]
        self.create_entry_row(scrollable_sub_frame, flat_key, current_val, section)

    self.update_raw_json_view()

  def create_entry_row(self, parent_frame, flat_key, current_val, section):
    row_frame = ttk.Frame(parent_frame)
    row_frame.pack(fill="x", expand=True, padx=5, pady=4)

    display_label = (
        flat_key.split(".")[-1] if "." in flat_key else flat_key
    )

    lbl = ttk.Label(row_frame, text=f"{display_label}:", width=25, anchor="w")
    lbl.pack(side="left", padx=(0, 5))

    entry_var = tk.StringVar()
    entry_var.trace_add("write", lambda *args: self.update_raw_json_view())

    if current_val not in [None, ""]:
      entry_var.set(str(current_val))
    else:
      entry_var.set("")

    entry = ttk.Entry(row_frame, textvariable=entry_var)
    entry.pack(side="left", fill="x", expand=True)

    current_os = platform.system()
    p = parent_frame
    while p and not isinstance(p, tk.Canvas):
      p = p.master
    if isinstance(p, tk.Canvas):
      if current_os == "Darwin":
        entry.bind("<MouseWheel>", lambda e, c=p: (c.yview_scroll(int(-1 * e.delta), "units"), "break"))
      elif current_os == "Linux":
        entry.bind("<Button-4>", lambda e, c=p: (c.yview_scroll(-1, "units"), "break"))
        entry.bind("<Button-5>", lambda e, c=p: (c.yview_scroll(1, "units"), "break"))
      else:
        entry.bind("<MouseWheel>", lambda e, c=p: (c.yview_scroll(int(-1 * (e.delta / 120)), "units"), "break"))

    self.entries[flat_key] = entry_var
    self.entry_widgets[flat_key] = entry
    self.tab_mapping[flat_key] = section

  def prompt_add_field(self, section):
    new_key_name = simpledialog.askstring(
        "Add Field", f"Enter new key name for [{section.upper()}]:"
    )
    if not new_key_name:
      return

    new_key_name = new_key_name.strip()
    if not new_key_name:
      return

    if section == "GENERAL":
      full_key = new_key_name
    else:
      full_key = f"{section}.{new_key_name}"

    if full_key in self.entries:
      messagebox.showerror("Error", "This field already exists!")
      return

    initial_val = ""

    target_tab_frame = self.tab_frames.get(section)
    if target_tab_frame:
      for child in target_tab_frame.winfo_children():
        if isinstance(child, tk.Canvas):
          for subchild in child.winfo_children():
            self.create_entry_row(subchild, full_key, initial_val, section)
            subchild.update_idletasks()
            break

  def get_current_unflattened_data(self):
    flat_updated = {}
    for key, var in self.entries.items():
      flat_updated[key] = var.get()
    return self.unflatten_dict(flat_updated)

  def update_raw_json_view(self):
    if self.raw_json_text:
      try:
        data = self.get_current_unflattened_data()
        formatted_json = json.dumps(data, indent=4)
        self.raw_json_text.config(state="normal")
        self.raw_json_text.delete("1.0", tk.END)
        self.raw_json_text.insert(tk.END, formatted_json)
        self.raw_json_text.config(state="disabled")
      except Exception:
        pass

  # --- Search & Replace Dialog & Logic ---
  def open_find_replace_dialog(self):
    if self.find_dialog and tk.Toplevel.winfo_exists(self.find_dialog):
      self.find_dialog.lift()
      self.find_dialog.focus()
      return

    self.find_dialog = tk.Toplevel(self.root)
    self.find_dialog.title("Find & Replace")
    self.find_dialog.geometry("400x180")
    self.find_dialog.resizable(False, False)
    
    self.find_dialog.transient(self.root)
    self.find_dialog.attributes("-topmost", True)

    ttk.Label(self.find_dialog, text="Find what:").grid(
        row=0, column=0, sticky="w", padx=10, pady=10
    )
    self.find_var = tk.StringVar()
    find_entry = ttk.Entry(
        self.find_dialog, textvariable=self.find_var, width=30
    )
    find_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    find_entry.focus()

    ttk.Label(self.find_dialog, text="Replace with:").grid(
        row=1, column=0, sticky="w", padx=10, pady=5
    )
    self.replace_var = tk.StringVar()
    replace_entry = ttk.Entry(
        self.find_dialog, textvariable=self.replace_var, width=30
    )
    replace_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

    btn_frame = ttk.Frame(self.find_dialog, padding=10)
    btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew")

    ttk.Button(
        btn_frame, text="Find Next", command=self.search_find_next
    ).pack(side="left", padx=3)
    ttk.Button(
        btn_frame, text="Replace", command=self.search_replace_current
    ).pack(side="left", padx=3)
    ttk.Button(
        btn_frame, text="Replace All", command=self.search_replace_all
    ).pack(side="left", padx=3)

  def search_find_next(self):
    query = self.find_var.get()
    if not query:
      return

    keys = list(self.entries.keys())
    if not keys:
      return

    matches = []
    for k, var in self.entries.items():
      if query.lower() in var.get().lower() or query.lower() in k.lower():
        matches.append(k)

    if not matches:
      messagebox.showinfo(
          "Find", f"Cannot find '{query}'", parent=self.find_dialog
      )
      return

    if not hasattr(self, "_last_find_query") or self._last_find_query != query:
      self._last_find_query = query
      self.search_index = 0

    if self.search_index >= len(matches):
      self.search_index = 0

    matched_key = matches[self.search_index]
    self.search_index += 1

    self.focus_and_highlight_field(matched_key, query)

  def focus_and_highlight_field(self, flat_key, query):
    section = self.tab_mapping.get(flat_key)
    if section:
      for idx, tab_id in enumerate(self.notebook.tabs()):
        tab_text = self.notebook.tab(tab_id, "text").lower()
        if tab_text == section.lower() or (
            section == "GENERAL" and tab_text == "general"
        ):
          self.notebook.select(idx)
          break

    widget = self.entry_widgets.get(flat_key)
    if widget:
      widget.focus()
      val = widget.get()
      pos = val.lower().find(query.lower())
      if pos != -1:
        widget.selection_range(pos, pos + len(query))

  def search_replace_current(self):
    query = self.find_var.get()
    replacement = self.replace_var.get()
    if not query:
      return

    try:
      focused = self.root.focus_get()
      for k, widget in self.entry_widgets.items():
        if widget == focused:
          current_val = self.entries[k].get()
          new_val = current_val.replace(query, replacement)
          self.entries[k].set(new_val)
          self.search_find_next()
          return
    except Exception:
      pass
    self.search_find_next()

  def search_replace_all(self):
    query = self.find_var.get()
    replacement = self.replace_var.get()
    if not query:
      return

    count = 0
    for k, var in self.entries.items():
      val = var.get()
      if query in val:
        new_val = val.replace(query, replacement)
        var.set(new_val)
        count += 1

    messagebox.showinfo(
        "Replace All",
        f"Replaced {count} occurrences.",
        parent=self.find_dialog,
    )

  # --- Saving Options ---
  def save_update_current(self):
    if not self.target_blocks:
      messagebox.showwarning("Warning", "No data to save.")
      return

    idx = self.current_block_index.get()
    updated_data = self.get_current_unflattened_data()
    self.target_blocks[idx] = updated_data

    target_path = self.target_path_var.get()
    try:
      if isinstance(self.raw_loaded_data, list):
        content_to_save = self.target_blocks
      else:
        content_to_save = self.target_blocks[0]

      with open(target_path, "w", encoding="utf-8") as f:
        json.dump(content_to_save, f, indent=4)
      messagebox.showinfo("Success", f"Successfully updated block index [{idx}] in:\n{target_path}")
    except Exception as e:
      messagebox.showerror("Error", f"Failed to update file:\n{str(e)}")

  def save_as_new(self):
    if not self.entries:
      messagebox.showwarning("Warning", "No data to save.")
      return

    updated_data = self.get_current_unflattened_data()

    save_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        initialfile="filled_output.json",
    )
    if not save_path:
      return
    try:
      with open(save_path, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, indent=4)
      messagebox.showinfo("Success", f"Saved successfully as new file to:\n{save_path}")
    except Exception as e:
      messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")

  def save_append(self):
    if not self.entries:
      messagebox.showwarning("Warning", "No data to save.")
      return

    updated_data = self.get_current_unflattened_data()

    save_path = filedialog.askopenfilename(
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
    )
    if not save_path:
      return
    try:
      existing_content = []
      if os.path.exists(save_path):
        with open(save_path, "r", encoding="utf-8") as f:
          try:
            data = json.load(f)
            if isinstance(data, list):
              existing_content = data
            else:
              existing_content = [data]
          except json.JSONDecodeError:
            existing_content = []

      existing_content.append(updated_data)

      with open(save_path, "w", encoding="utf-8") as f:
        json.dump(existing_content, f, indent=4)

      messagebox.showinfo(
          "Success", f"Successfully appended block to existing file:\n{save_path}"
      )
    except Exception as e:
      messagebox.showerror("Error", f"Failed to append to file:\n{str(e)}")


if __name__ == "__main__":
  root = tk.Tk()
  app = NestedJSONFillerApp(root)
  root.mainloop()
