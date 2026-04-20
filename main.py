import os
import sys

# A 'NoneType isatty error' may appear when the app is bundled with PyInstaller
# Because in GUI mode the console is gone, so we just use a dummy stream
if sys.stdout is None:
    class DummyStream:
        def write(self, x): pass
        def flush(self): pass
        def isatty(self): return False
    sys.stdout = DummyStream()
    sys.stderr = DummyStream()
    
import re
import threading
import numpy as np
import tkinter as tk
from   tkinter import messagebox
import customtkinter as ctk

# UI Configuration
ctk.set_appearance_mode("Dark")  # Modes: "System Theme" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")

class KeyNoteExtractor(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Key-Note Extractor")
        self.geometry("1000x550")
        
        # Model state
        self.model = None
        self.is_processing = False
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL: Input ---
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.input_label = ctk.CTkLabel(self.left_frame, text="Text Field", font=ctk.CTkFont(size=16, weight="bold"))
        self.input_label.grid(row=0, column=0, pady=(10, 5))
        
        self.input_text = ctk.CTkTextbox(self.left_frame, font=ctk.CTkFont(size=14), undo=True, autoseparators=True, maxundo=50, border_width=1, wrap="word")
        self.input_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.input_text.insert("1.0", "Paste your text here...")
        self.input_text.bind("<FocusIn>", lambda e: self.handle_placeholder("in"))
        self.input_text.bind("<FocusOut>", lambda e: self.handle_placeholder("out"))
        self.after(128, lambda: self.input_text.focus_set())

        # --- RIGHT PANEL: Result ---
        self.right_frame = ctk.CTkFrame(self, corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.output_label = ctk.CTkLabel(self.right_frame, text="Key Notes", font=ctk.CTkFont(size=16, weight="bold"))
        self.output_label.grid(row=0, column=0, pady=(10, 5))

        self.output_text = ctk.CTkTextbox(self.right_frame, font=ctk.CTkFont(size=14), state="disabled", border_width=1, wrap="word")
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # --- BOTTOM PANEL: Controls ---
        self.control_frame = ctk.CTkFrame(self, height=100)
        self.control_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        
        # Slider for notes count
        self.notes_label = ctk.CTkLabel(self.control_frame, text="Max Notes:")
        self.notes_label.pack(side="left", padx=(20, 5))
        
        self.notes_entry = ctk.CTkEntry(self.control_frame, width=60)
        self.notes_entry.insert(0, "5") # Default value
        self.notes_entry.pack(side="left", padx=5)

        # Appearance Mode
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.control_frame, values=["Dark", "Light", "System Theme"],
                                                               command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.pack(side="right", padx=20)
        self.appearance_mode_optionemenu.set("Dark")

        # Action Button
        self.extract_button = ctk.CTkButton(self.control_frame, text="Extract Key Notes", command=self.start_extraction_thread, font=ctk.CTkFont(weight="bold"))
        self.extract_button.pack(side="right", padx=10)

        # Status Label
        self.status_label = ctk.CTkLabel(self.control_frame, text="Ready", text_color="gray")
        self.status_label.pack(side="right", padx=20)
        
        # Context Menu
        for btn in ["<Button-2>", "<Button-3>"]:
            self.input_text.bind(btn, self.show_context_menu)
            self.output_text.bind(btn, self.show_context_menu)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def handle_placeholder(self, mode):
        content = self.input_text.get("1.0", tk.END).strip()
        if mode == "in" and content == "Paste your text here...":
            self.input_text.delete("1.0", tk.END)
        elif mode == "out" and not content:
            self.input_text.insert("1.0", "Paste your text here...")

    def set_status(self, text, color="gray"):
        self.status_label.configure(text=text, text_color=color)

    def start_extraction_thread(self):
        if self.is_processing:
            return
        
        raw_text = self.input_text.get("1.0", "end-1c").strip()
        length = len(raw_text)
        if len(raw_text) < 100:
            messagebox.showwarning("Incomplete Data", f"Please paste a longer text to allow for meaningful analysis.\n\nMinimum characters: 100\nCurrent characters: {length}")
            return

        self.is_processing = True
        self.extract_button.configure(state="disabled")
        threading.Thread(target=self.process_text, args=(raw_text,), daemon=True).start()

    def process_text(self, text_content):
        try:
            # 1. Model Initialization
            if self.model is None:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                model_path = os.path.join(script_dir, 'all-minilm-l6-v2')
            
                # Warn if no model is found
                if not os.path.exists(model_path):
                    error_msg = (
                        f"Model not found at: {model_path}\n\n"
                        "Please ensure the 'all-minilm-l6-v2' folder is in the same directory as this app."
                    )
                    self.set_status("Model Missing", "#e74c3c")
                    messagebox.showerror("Critical Error", error_msg)
                    # Since this is in a thread, we can't just sys.exit(); we return to stop the process
                    return
                    
                # Load the model normally
                global KMeans, pairwise_distances_argmin_min
                self.set_status("Loading Model...", "#3498db")
                from sentence_transformers import SentenceTransformer
                from sklearn.cluster import KMeans
                from sklearn.metrics import pairwise_distances_argmin_min
                self.model = SentenceTransformer(model_path)

            self.set_status("Analyzing Context...", "#e67e22")
            
            # 2. Text Pre-processing 
            # Use regex to handle abbreviations and split sentences accurately
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text_content)
            # Filter structural noise and headings 
            clean_sentences = [s.strip() for s in sentences if len(s.strip()) > 30 and not s.strip().isupper()]
            
            if not clean_sentences:
                raise ValueError("No substantive sentences found in the provided text.")

            # 3. Embedding and Clustering 
            embeddings = self.model.encode(clean_sentences)
            # Parse arbitrary number with fallback
            try: 
                num_notes = int(self.notes_entry.get())
                if num_notes <= 0: raise ValueError
            except ValueError:
                num_notes = 5
                self.notes_entry.delete(0, tk.END)
                self.notes_entry.insert(0, "5")
                
            # Ensure clusters don't exceed available sentences
            num_notes = min(num_notes, len(clean_sentences))
            
            kmeans = KMeans(n_clusters=num_notes, n_init='auto', random_state=42)
            kmeans.fit(embeddings)

            # Find sentences closest to center of each topic cluster 
            closest_indices, _ = pairwise_distances_argmin_min(kmeans.cluster_centers_, embeddings)
            
            # 4. Display Results
            self.update_output(clean_sentences, sorted(closest_indices))
            self.set_status("Complete", "#2ecc71")

        except Exception as e:
            self.set_status("Error", "#e74c3c")
            messagebox.showerror("Processing Error", f"An error occurred during analysis:\n{str(e)}")
        
        finally:
            self.is_processing = False
            self.extract_button.configure(state="normal")

    def update_output(self, sentences, indices):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        text = ''
        for i in indices:
            note = re.sub(r'\n{1,}', '\n', sentences[i]).strip()
            text += f"• {note}\n\n"
        
        self.output_text.insert(tk.END,text)
        self.output_text.configure(state="disabled")

    def show_context_menu(self, event):
        # Create menu
        menu = tk.Menu(
            self, 
            tearoff=0, 
            bg="white",
            fg="black",
            activebackground="#D3D3D3",
            activeforeground="black", 
            bd=0,
            borderwidth=0,
            relief="flat"
        )
        widget = event.widget
        
        # Define options: (Label, Symbol, Command)
        options = [
            ("Undo", "    ️", "<<Undo>>"),
            ("Redo", "    ", "<<Redo>>"),
            None,
            ("Cut", "✂️", "<<Cut>>"),
            ("Copy", "📋", "<<Copy>>"),
            ("Paste", "⧉", "<<Paste>>"),
            ("Delete", "❌️", "delete_selection"), # Custom for Delete
            None, # Separator
            ("Select All", "    ", "select_all")    # Custom for Select All
        ]

        for opt in options:
            if opt is None:
                menu.add_separator()
            else:
                label, sym, cmd = opt
                # Handle standard virtual events vs custom methods
                if cmd.startswith("<<"):
                    menu.add_command(label=f"{sym} {label}", command=lambda c=cmd: widget.event_generate(c))
                elif cmd == "select_all":
                    menu.add_command(label=f"{sym} {label}", command=lambda: widget.tag_add("sel", "1.0", "end"))
                elif cmd == "delete_selection":
                    menu.add_command(label=f"{sym} {label}", command=lambda: widget.delete("sel.first", "sel.last") if widget.tag_ranges("sel") else None)

        menu.tk_popup(event.x_root, event.y_root)

if __name__ == "__main__":
    app = KeyNoteExtractor()
    app.mainloop()