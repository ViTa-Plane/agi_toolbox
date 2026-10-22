# v 2.3.4
import json
import os
import platform
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

DEFAULT_TARGET_JSON = "anime_heroine.json"
SETTINGS_FILE = "settings.json"
MAX_RECENT_FILES = 5

EXAMPLE_TEMPLATE_DATA = [
    {
        "name": "Anime Heroine / Sakura",
        "category": "character",
        "character": "sakura",
        "thumbnail": "sakura_thumb.png",
        "comment": "Main protagonist style trained on NijiXL base model. Use high CFG.",
        "seed": 8675309,
        "prompt": "{prompt}, 1girl, solo, cute smile, detailed eyes, masterpiece, {age}, {clothes}, {mod}, {lora}",
        "negative_prompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
        "suppress": "nsfw, gore",
        "params": {
            "steps": 25,
            "cfg": 7.0,
            "sampler": "euler_ancestral"
        },
        "version": {
            "default": "{prompt}, 1girl, solo, cute smile, detailed eyes, masterpiece, {age}, {clothes}, {mod}, {lora}",
            "Battle Mode": "{prompt}, 1girl, solo, fierce expression, dynamic pose, glowing aura, {age}, {clothes}, {mod}, {lora}"
        },
        "age": {
            "teen (16yo)": "young, teenage girl, slender build",
            "adult (22yo)": "mature female, elegant posture"
        },
        "clothes": {
            "school uniform": "school uniform, sailor collar, pleated skirt, loafers",
            "casual hoodie": "oversized pastel hoodie, black leggings, sneakers",
            "battle armor": "light fantasy armor, pauldrons, gauntlets, thigh-high boots"
        },
        "mod": {
            "cherry blossoms": "falling cherry blossoms, wind blowing, pink petals",
            "cyberpunk alley": "neon lights, cyberpunk street, wet asphalt reflections",
            "magic circle": "glowing magical runes, floating sparks, arcane energy"
        },
        "lora": {
            "default": "<lora:sakura_model_v1_epoch{epoch}:0.8>, <lora:clothing_pack_v2:0.5>",
            "Battle Mode": "<lora:sakura_model_v1_epoch{epoch}:1.0>, <lora:epic_battle_fx:0.6>"
        }
    }
]


class ExitPromptDialog(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Unsaved Changes")

        dialog_width = 360
        dialog_height = 140
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        parent.update_idletasks()
        p_x = parent.winfo_rootx()
        p_y = parent.winfo_rooty()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        x = p_x + (p_w - dialog_width) // 2
        y = p_y + (p_h - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        self.result = "cancel"

        ttk.Label(
            self,
            text="You have unsaved changes.\nWhat would you like to do?",
            justify="center",
            font=("Arial", 10),
        ).pack(pady=(15, 15))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(0, 15))

        ttk.Button(
            btn_frame, text="Save", command=self.on_save, width=10
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="Continue", command=self.on_exit, width=10
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="Abort", command=self.on_cancel, width=10
        ).pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def on_save(self):
        self.result = "save"
        self.destroy()

    def on_exit(self):
        self.result = "exit"
        self.destroy()

    def on_cancel(self):
        self.result = "cancel"
        self.destroy()


class NestedJSONFillerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Template JSON Value Filler")
        self.root.geometry("950x900")
        self.root.minsize(750, 700)

        # Set custom window icon if icon128.png exists
        self.set_window_icon()

        self.raw_loaded_data = None
        self.target_blocks = []
        self.current_block_index = tk.IntVar(value=0)
        self.is_edited = False

        self.target_data = {}
        self.entries = {}
        self.entry_widgets = {}
        self.tab_mapping = {}
        self.tab_frames = {}
        self.raw_json_text = None

        self.recent_files = []
        self.load_settings()

        self.search_matches = []
        self.search_index = 0
        self.find_dialog = None
        self.find_var = None
        self.replace_var = None

        self.create_context_menu()
        self.create_menu()
        self.create_widgets()
        self.setup_shortcuts()
        self.load_data(is_initial_load=True)

        self.root.protocol("WM_DELETE_WINDOW", self.check_exit)

    def set_window_icon(self):
        icon_path = "icon128.png"
        if os.path.exists(icon_path):
            try:
                self.app_icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self.app_icon)
            except Exception:
                pass

    def create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Undo", command=self.undo_action)
        self.context_menu.add_command(label="Redo", command=self.redo_action)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Cut", command=self.context_cut)
        self.context_menu.add_command(label="Copy", command=self.context_copy)
        self.context_menu.add_command(label="Paste", command=self.context_paste)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", command=self.context_delete)

    def show_context_menu(self, event):
        widget = event.widget
        try:
            widget.focus()
            self.active_context_widget = widget
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def undo_action(self, event=None):
        focused = self.root.focus_get()
        if isinstance(focused, ttk.Entry) and hasattr(focused, "undo_stack"):
            if len(focused.undo_stack) > 1:
                current = focused.undo_stack.pop()
                focused.redo_stack.append(current)
                prev = focused.undo_stack[-1]
                focused._ignoring_change = True
                for k, w in self.entry_widgets.items():
                    if w == focused:
                        self.entries[k].set(prev)
                        break
                focused._ignoring_change = False
                self.is_edited = True
        return "break"

    def redo_action(self, event=None):
        focused = self.root.focus_get()
        if isinstance(focused, ttk.Entry) and hasattr(focused, "redo_stack"):
            if focused.redo_stack:
                nxt = focused.redo_stack.pop()
                focused.undo_stack.append(nxt)
                focused._ignoring_change = True
                for k, w in self.entry_widgets.items():
                    if w == focused:
                        self.entries[k].set(nxt)
                        break
                focused._ignoring_change = False
                self.is_edited = True
        return "break"

    def context_cut(self):
        widget = getattr(self, "active_context_widget", None)
        if not widget:
            widget = self.root.focus_get()

        if widget and isinstance(widget, ttk.Entry):
            try:
                selected_text = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)

                sel_start = widget.index("sel.first")
                sel_end = widget.index("sel.last")
                widget.delete(sel_start, sel_end)
                widget.event_generate("<<Modified>>")

                self.is_edited = True
                if hasattr(widget, "undo_stack") and not widget._ignoring_change:
                    val = widget.get()
                    if widget.undo_stack[-1] != val:
                        widget.undo_stack.append(val)
                        widget.redo_stack.clear()
            except tk.TclError:
                pass

    def menu_cut_action(self, event=None):
        focused = self.root.focus_get()
        if isinstance(focused, ttk.Entry):
            try:
                selected_text = focused.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)

                sel_start = focused.index("sel.first")
                sel_end = focused.index("sel.last")
                focused.delete(sel_start, sel_end)
                focused.event_generate("<<Modified>>")

                self.is_edited = True
                if hasattr(focused, "undo_stack") and not focused._ignoring_change:
                    val = focused.get()
                    if focused.undo_stack[-1] != val:
                        focused.undo_stack.append(val)
                        focused.redo_stack.clear()
            except tk.TclError:
                pass
        return "break"

    def context_copy(self):
        widget = getattr(self, "active_context_widget", None)
        if widget and isinstance(widget, ttk.Entry):
            try:
                selected_text = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
            except tk.TclError:
                pass

    def context_paste(self):
        widget = getattr(self, "active_context_widget", None)
        if widget and isinstance(widget, ttk.Entry):
            try:
                clipboard_text = self.root.clipboard_get()
                try:
                    sel_start = widget.index("sel.first")
                    sel_end = widget.index("sel.last")
                    widget.delete(sel_start, sel_end)
                except tk.TclError:
                    pass
                cursor_pos = widget.index(tk.INSERT)
                widget.insert(cursor_pos, clipboard_text)
                widget.event_generate("<<Modified>>")
                self.is_edited = True
                if hasattr(widget, "undo_stack") and not widget._ignoring_change:
                    val = widget.get()
                    if widget.undo_stack[-1] != val:
                        widget.undo_stack.append(val)
                        widget.redo_stack.clear()
            except tk.TclError:
                pass

    def context_delete(self):
        widget = getattr(self, "active_context_widget", None)
        if widget and isinstance(widget, ttk.Entry):
            try:
                sel_start = widget.index("sel.first")
                sel_end = widget.index("sel.last")
                widget.delete(sel_start, sel_end)
                widget.event_generate("<<Modified>>")
            except tk.TclError:
                widget.delete(0, tk.END)
                widget.event_generate("<<Modified>>")

            self.is_edited = True
            if hasattr(widget, "undo_stack") and not widget._ignoring_change:
                val = widget.get()
                if widget.undo_stack[-1] != val:
                    widget.undo_stack.append(val)
                    widget.redo_stack.clear()

    def check_exit(self):
        if self.is_edited:
            dialog = ExitPromptDialog(self.root)
            if dialog.result == "save":
                self.save_update_current()
                self.root.destroy()
            elif dialog.result == "exit":
                self.root.destroy()
            else:
                return  # Cancel
        else:
            self.root.destroy()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.recent_files = data.get("recent_files", [])
            except Exception:
                self.recent_files = []

    def save_settings(self):
        try:
            data = {"recent_files": self.recent_files}
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def add_recent_file(self, filepath):
        filepath = os.path.abspath(filepath)
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        if len(self.recent_files) > MAX_RECENT_FILES:
            self.recent_files = self.recent_files[:MAX_RECENT_FILES]
        self.save_settings()
        self.create_menu()

    def create_menu(self):
        menubar = tk.Menu(self.root)

        # --- File Menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="New (Create Example Template)...",
            command=self.create_new_example_template,
        )
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

        # --- Recent Files Block ---
        file_menu.add_separator()
        file_menu.add_command(label="Recent Files:", state="disabled")

        if self.recent_files:
            for fpath in self.recent_files:
                filename = os.path.basename(fpath)
                dirname = os.path.dirname(fpath)
                if len(dirname) > 30:
                    dirname = "..." + dirname[-27:]

                display_label = f"   {filename}  ({dirname})"
                file_menu.add_command(
                    label=display_label,
                    command=lambda p=fpath: self.open_specific_file(p),
                )
        else:
            file_menu.add_command(label="   (No Recent Files)", state="disabled")

        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.check_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        # --- Edit Menu ---
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(
            label="Add Category...", command=self.prompt_add_category
        )
        edit_menu.add_command(
            label="Edit Category Name...", command=self.prompt_edit_category_name
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Add Field...", command=self.prompt_add_field_from_menu
        )
        edit_menu.add_command(
            label="Edit Field Name...", command=self.prompt_edit_field_name
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Cut",
            command=self.menu_cut_action,
            accelerator="Ctrl+X",
        )
        edit_menu.add_command(
            label="Undo",
            command=self.undo_action,
            accelerator="Ctrl+Z",
        )
        edit_menu.add_command(
            label="Redo",
            command=self.redo_action,
            accelerator="Ctrl+Y",
        )
        menubar.add_cascade(label="Edit", menu=edit_menu)

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
        self.root.bind_all("<Control-z>", lambda e: self.undo_action())
        self.root.bind_all("<Control-y>", lambda e: self.redo_action())
        self.root.bind_all("<Control-x>", lambda e: self.menu_cut_action())

    def prompt_add_category(self):
        cat_name = simpledialog.askstring(
            "Add Category", "Enter new category name:", parent=self.root
        )
        if not cat_name:
            return
        cat_name = cat_name.strip().lower()
        if not cat_name:
            return

        field_name = simpledialog.askstring(
            "Add Field",
            f"Enter initial field name for [{cat_name.upper()}]:",
            parent=self.root,
        )
        if not field_name:
            return
        field_name = field_name.strip()
        if not field_name:
            return

        full_key = f"{cat_name}.{field_name}"
        if full_key in self.entries:
            messagebox.showerror("Error", "This field already exists!", parent=self.root)
            return

        idx = self.current_block_index.get()
        if 0 <= idx < len(self.target_blocks):
            self.target_blocks[idx] = self.get_current_unflattened_data()
            if cat_name not in self.target_blocks[idx]:
                self.target_blocks[idx][cat_name] = {}
            self.target_blocks[idx][cat_name][field_name] = ""
            self.load_active_block(preserve_tab=cat_name)
            self.is_edited = True

    def prompt_edit_category_name(self, event=None):
        try:
            clicked_tab = self.notebook.tk.call(
                self.notebook._w, "identify", "tab", event.x, event.y
            )
            if clicked_tab != "":
                self.notebook.select(clicked_tab)
        except Exception:
            pass

        try:
            current_tab_id = self.notebook.select()
            current_tab_text = self.notebook.tab(current_tab_id, "text")
            old_cat = "" if current_tab_text == "GENERAL" else current_tab_text.lower()
        except Exception:
            old_cat = ""

        if old_cat == "" or old_cat == "general":
            messagebox.showerror(
                "Error",
                "Cannot rename the default GENERAL top-level category.",
                parent=self.root,
            )
            return

        new_cat = simpledialog.askstring(
            "Edit Category Name",
            f"Enter new name for category [{old_cat.upper()}]:",
            parent=self.root,
        )
        if not new_cat:
            return
        new_cat = new_cat.strip().lower()

        if old_cat == new_cat:
            return

        idx = self.current_block_index.get()
        if 0 <= idx < len(self.target_blocks):
            data = self.get_current_unflattened_data()
            if old_cat in data and isinstance(data[old_cat], dict):
                data[new_cat] = data.pop(old_cat)
                self.target_blocks[idx] = data
                self.load_active_block(preserve_tab=new_cat)
                self.is_edited = True
            else:
                messagebox.showerror(
                    "Error", f"Category '{old_cat}' not found.", parent=self.root
                )

    def prompt_add_field_from_menu(self):
        try:
            current_tab_id = self.notebook.select()
            current_tab_text = self.notebook.tab(current_tab_id, "text")
            section = "GENERAL" if current_tab_text == "GENERAL" else current_tab_text.lower()
        except Exception:
            section = "general"
        self.prompt_add_field(section)

    def prompt_edit_field_name_for_key(self, flat_key):
        if "." in flat_key:
            section, old_field = flat_key.split(".", 1)
        else:
            section = "general"
            old_field = flat_key

        new_field = simpledialog.askstring(
            "Edit Field Name",
            f"Enter new name for field '{old_field}' (in [{section.upper()}]):",
            parent=self.root,
        )
        if not new_field:
            return
        new_field = new_field.strip()

        if old_field == new_field:
            return

        idx = self.current_block_index.get()
        if 0 <= idx < len(self.target_blocks):
            data = self.get_current_unflattened_data()
            if section == "general" or section == "GENERAL":
                if old_field in data:
                    val = data.pop(old_field)
                    data[new_field] = val
                    self.target_blocks[idx] = data
                    self.load_active_block(preserve_tab=section)
                    self.is_edited = True
                else:
                    messagebox.showerror(
                        "Error",
                        f"Field '{old_field}' not found in GENERAL.",
                        parent=self.root,
                    )
            else:
                if section in data and isinstance(data[section], dict):
                    if old_field in data[section]:
                        val = data[section].pop(old_field)
                        data[section][new_field] = val
                        self.target_blocks[idx] = data
                        self.load_active_block(preserve_tab=section)
                        self.is_edited = True
                    else:
                        messagebox.showerror(
                            "Error",
                            f"Field '{old_field}' not found in category [{section.upper()}].",
                            parent=self.root,
                        )
                else:
                    messagebox.showerror(
                        "Error", f"Category [{section.upper()}] not found.", parent=self.root
                    )

    def prompt_edit_field_name(self):
        focused = self.root.focus_get()
        target_key = None

        for k, w in self.entry_widgets.items():
            if w == focused:
                target_key = k
                break

        if not target_key:
            messagebox.showerror(
                "Error",
                "Please click or focus on the specific field entry you want to rename.",
                parent=self.root,
            )
            return

        self.prompt_edit_field_name_for_key(target_key)

    def create_new_example_template(self):
        if self.is_edited:
            dialog = ExitPromptDialog(self.root)
            if dialog.result == "save":
                self.save_update_current()
            elif dialog.result == "cancel":
                return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="anime_heroine.json",
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(EXAMPLE_TEMPLATE_DATA, f, indent=4)

            self.target_path_var.set(save_path)
            self.add_recent_file(save_path)
            self.load_data()
            messagebox.showinfo("Success", f"Created and loaded new template at:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create new template file:\n{str(e)}")

    def open_specific_file(self, filepath):
        if self.is_edited:
            dialog = ExitPromptDialog(self.root)
            if dialog.result == "save":
                self.save_update_current()
            elif dialog.result == "cancel":
                return

        if os.path.exists(filepath):
            self.target_path_var.set(filepath)
            self.add_recent_file(filepath)
            self.load_data()
        else:
            messagebox.showerror("Error", f"File not found:\n{filepath}")
            if filepath in self.recent_files:
                self.recent_files.remove(filepath)
                self.save_settings()
                self.create_menu()

    def open_about_dialog(self):
        about_win = tk.Toplevel(self.root)
        about_win.title("About Template JSON Filler")

        dialog_width = 420
        dialog_height = 240
        about_win.resizable(False, False)
        about_win.transient(self.root)
        about_win.grab_set()

        self.root.update_idletasks()
        p_x = self.root.winfo_rootx()
        p_y = self.root.winfo_rooty()
        p_w = self.root.winfo_width()
        p_h = self.root.winfo_height()

        x = p_x + (p_w - dialog_width) // 2
        y = p_y + (p_h - dialog_height) // 2
        about_win.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        content_frame = ttk.Frame(about_win, padding=15)
        content_frame.pack(fill="both", expand=True)

        ttk.Label(
            content_frame,
            text="Template JSON Value Filler",
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
        self.notebook.bind("<Double-1>", self.prompt_edit_category_name)

        # Bottom Pane: Live Raw JSON Preview Panel
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

    def browse_file(self, file_type):
        if self.is_edited:
            dialog = ExitPromptDialog(self.root)
            if dialog.result == "save":
                self.save_update_current()
            elif dialog.result == "cancel":
                return

        filename = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if filename:
            if file_type == "target":
                self.target_path_var.set(filename)
                self.add_recent_file(filename)
            self.load_data()

    def load_data(self, is_initial_load=False):
        target_path = self.target_path_var.get()

        # Automatically create DEFAULT_TARGET_JSON if missing on initial load (without adding to recent files)
        if is_initial_load and not os.path.exists(target_path):
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(EXAMPLE_TEMPLATE_DATA, f, indent=4)
            except Exception:
                pass

        if not os.path.exists(target_path):
            self.target_path_var.set("No File Loaded (Open a JSON file)")
            self.target_blocks = [{}]
            self.populate_block_selector()
            self.is_edited = False
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

            if not is_initial_load:
                self.add_recent_file(target_path)
        except Exception as e:
            if not is_initial_load:
                messagebox.showerror(
                    "Error", f"Could not load target template JSON:\n{str(e)}"
                )
            self.target_blocks = [{}]

        self.populate_block_selector()
        self.is_edited = False

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
        if self.is_edited:
            dialog = ExitPromptDialog(self.root)
            if dialog.result == "save":
                self.save_update_current()
            elif dialog.result == "cancel":
                idx = self.current_block_index.get()
                self.block_combo.current(idx)
                return

        selected_idx = self.block_combo.current()
        if selected_idx != -1:
            self.current_block_index.set(selected_idx)
            self.load_active_block()

    def load_active_block(self, preserve_tab=None):
        idx = self.current_block_index.get()

        if 0 <= idx < len(self.target_blocks):
            self.target_data = self.target_blocks[idx]
        else:
            self.target_data = {}

        total = len(self.target_blocks)
        self.block_counter_lbl.config(text=f"(Index: {idx} of {total - 1})")
        self.build_form(preserve_tab=preserve_tab)
        self.is_edited = False

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

    def build_form(self, preserve_tab=None):
        current_selected_tab_text = None
        if not preserve_tab and self.notebook.tabs():
            try:
                curr_tab_id = self.notebook.select()
                if curr_tab_id:
                    current_selected_tab_text = self.notebook.tab(curr_tab_id, "text").lower()
            except Exception:
                pass

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

        target_tab_index = 0
        for idx, (section, keys) in enumerate(sections.items()):
            sec_title = "GENERAL" if section == "GENERAL" else section.upper()

            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=sec_title)

            if preserve_tab and section.lower() == preserve_tab.lower():
                target_tab_index = idx
            elif current_selected_tab_text and sec_title.lower() == current_selected_tab_text:
                target_tab_index = idx

            canvas = tk.Canvas(tab_frame, highlightthickness=0)
            scrollbar = ttk.Scrollbar(
                tab_frame, orient="vertical", command=canvas.yview
            )

            scrollable_sub_frame = ttk.Frame(canvas, padding=15)

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

            def make_empty_double_click_handler(sec_name, sub_fr, cvs):
                def handler(e):
                    if e.widget in (cvs, sub_fr):
                        self.prompt_add_field(sec_name)

                return handler

            double_click_handler = make_empty_double_click_handler(section, scrollable_sub_frame, canvas)
            canvas.bind("<Double-1>", double_click_handler)
            scrollable_sub_frame.bind("<Double-1>", double_click_handler)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            self.tab_frames[section] = tab_frame

            header_frame = ttk.Frame(scrollable_sub_frame)
            header_frame.pack(fill="x", padx=5, pady=(2, 12))
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

        if self.notebook.tabs():
            self.notebook.select(target_tab_index)

        self.update_raw_json_view()

    def create_entry_row(self, parent_frame, flat_key, current_val, section):
        row_frame = ttk.Frame(parent_frame)
        row_frame.pack(fill="x", expand=True, padx=5, pady=6)

        display_label = (
            flat_key.split(".")[-1] if "." in flat_key else flat_key
        )

        lbl = ttk.Label(row_frame, text=f"{display_label}:", width=25, anchor="w")
        lbl.pack(side="left", padx=(0, 10))
        lbl.bind("<Double-1>", lambda e, k=flat_key: self.prompt_edit_field_name_for_key(k))

        entry_var = tk.StringVar()

        def on_var_change(*args):
            self.is_edited = True
            self.update_raw_json_view()

        entry_var.trace_add("write", on_var_change)

        if current_val not in [None, ""]:
            entry_var.set(str(current_val))
        else:
            entry_var.set("")

        entry = ttk.Entry(row_frame, textvariable=entry_var)
        entry.pack(side="left", fill="x", expand=True)

        initial_text = entry_var.get()
        entry.undo_stack = [initial_text]
        entry.redo_stack = []
        entry._ignoring_change = False

        def on_key_release(event):
            if entry._ignoring_change:
                return
            val = entry_var.get()
            if entry.undo_stack and entry.undo_stack[-1] != val:
                entry.undo_stack.append(val)
                entry.redo_stack.clear()

        entry.bind("<KeyRelease>", on_key_release)

        current_os = platform.system()
        if current_os == "Darwin":
            entry.bind("<Button-2>", self.show_context_menu)
        else:
            entry.bind("<Button-3>", self.show_context_menu)

        self.entries[flat_key] = entry_var
        self.entry_widgets[flat_key] = entry
        self.tab_mapping[flat_key] = section

    def prompt_add_field(self, section):
        new_key_name = simpledialog.askstring(
            "Add Field",
            f"Enter new key name for [{section.upper()}]:",
            parent=self.root,
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
            messagebox.showerror("Error", "This field already exists!", parent=self.root)
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

        self.is_edited = True

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

        if count > 0:
            self.is_edited = True

        messagebox.showinfo(
            "Replace All",
            f"Replaced {count} occurrences.",
            parent=self.find_dialog,
        )

    # --- Saving Options ---
    def save_update_current(self):
        if not self.target_blocks:
            messagebox.showwarning("Warning", "No data to save.", parent=self.root)
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

            self.is_edited = False
            messagebox.showinfo(
                "Success",
                f"Successfully updated block index [{idx}] in:\n{target_path}",
                parent=self.root,
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to update file:\n{str(e)}", parent=self.root
            )

    def save_as_new(self):
        if not self.entries:
            messagebox.showwarning("Warning", "No data to save.", parent=self.root)
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
            self.add_recent_file(save_path)
            self.is_edited = False
            messagebox.showinfo(
                "Success",
                f"Saved successfully as new file to:\n{save_path}",
                parent=self.root,
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to save file:\n{str(e)}", parent=self.root
            )

    def save_append(self):
        if not self.entries:
            messagebox.showwarning("Warning", "No data to save.", parent=self.root)
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

            self.add_recent_file(save_path)
            self.is_edited = False
            messagebox.showinfo(
                "Success",
                f"Successfully appended block to existing file:\n{save_path}",
                parent=self.root,
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to append to file:\n{str(e)}", parent=self.root
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = NestedJSONFillerApp(root)
    root.mainloop()