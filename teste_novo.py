import tkinter as tk
from tkinter import ttk, messagebox
import edge_tts
import asyncio
import pygame
import tempfile
import os
import threading

VOICE = "pt-BR-AntonioNeural"

class TextToSpeechApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎙️ Texto para Voz")
        self.root.geometry("700x520")
        self.root.configure(bg="#1a1a2e")
        self.root.attributes("-fullscreen", True)

        self.temp_file = os.path.join(tempfile.gettempdir(), "tts_output.mp3")
        self.is_playing = False

        pygame.mixer.init()

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        title = tk.Label(
            self.root,
            text="🎙️ Texto para Voz",
            font=("Segoe UI", 22, "bold"),
            fg="#e94560",
            bg="#1a1a2e"
        )
        title.pack(pady=(20, 5))

        subtitle = tk.Label(
            self.root,
            text="Voz Masculina Neural · Microsoft Edge TTS",
            font=("Segoe UI", 10),
            fg="#7a7a9e",
            bg="#1a1a2e"
        )
        subtitle.pack(pady=(0, 15))

        text_frame = tk.Frame(self.root, bg="#16213e", bd=0, highlightthickness=2, highlightbackground="#0f3460")
        text_frame.pack(padx=30, pady=(0, 10), fill="both", expand=True)

        self.text_input = tk.Text(
            text_frame,
            font=("Segoe UI", 13),
            bg="#16213e",
            fg="#eaeaea",
            insertbackground="#e94560",
            relief="flat",
            wrap="word",
            padx=15,
            pady=15,
            selectbackground="#0f3460",
            selectforeground="#ffffff",
            bd=0
        )
        self.text_input.pack(fill="both", expand=True)
        self.text_input.insert("1.0", "Digite seu texto aqui...")
        self.text_input.bind("<FocusIn>", self._clear_placeholder)

        controls_frame = tk.Frame(self.root, bg="#1a1a2e")
        controls_frame.pack(pady=(5, 10))

        speed_label = tk.Label(controls_frame, text="Velocidade:", font=("Segoe UI", 10), fg="#7a7a9e", bg="#1a1a2e")
        speed_label.pack(side="left", padx=(0, 5))

        self.speed_var = tk.StringVar(value="Normal")
        speed_options = ["Muito Lenta", "Lenta", "Normal", "Rápida", "Muito Rápida"]
        self.speed_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.speed_var,
            values=speed_options,
            state="readonly",
            width=14,
            font=("Segoe UI", 10)
        )
        self.speed_combo.pack(side="left", padx=(0, 20))

        volume_label = tk.Label(controls_frame, text="Volume:", font=("Segoe UI", 10), fg="#7a7a9e", bg="#1a1a2e")
        volume_label.pack(side="left", padx=(0, 5))

        self.volume_var = tk.IntVar(value=100)
        self.volume_scale = tk.Scale(
            controls_frame,
            from_=10, to=100,
            orient="horizontal",
            variable=self.volume_var,
            length=120,
            bg="#1a1a2e",
            fg="#e94560",
            troughcolor="#0f3460",
            highlightthickness=0,
            sliderrelief="flat",
            font=("Segoe UI", 8)
        )
        self.volume_scale.pack(side="left")

        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=(5, 20))

        self.play_btn = tk.Button(
            btn_frame,
            text="▶  RODAR",
            font=("Segoe UI", 14, "bold"),
            fg="#ffffff",
            bg="#e94560",
            activebackground="#c73e54",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=35,
            pady=8,
            command=self._on_play
        )
        self.play_btn.pack(side="left", padx=8)

        self.stop_btn = tk.Button(
            btn_frame,
            text="⏹  PARAR",
            font=("Segoe UI", 14, "bold"),
            fg="#ffffff",
            bg="#0f3460",
            activebackground="#0a2647",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=35,
            pady=8,
            command=self._on_stop
        )
        self.stop_btn.pack(side="left", padx=8)

        self.status_label = tk.Label(
            self.root,
            text="Pronto",
            font=("Segoe UI", 10),
            fg="#4ecca3",
            bg="#1a1a2e"
        )
        self.status_label.pack(pady=(0, 10))

    def _clear_placeholder(self, event):
        if self.text_input.get("1.0", "end-1c") == "Digite seu texto aqui...":
            self.text_input.delete("1.0", "end")

    def _get_rate(self):
        speed_map = {
            "Muito Lenta": "-40%",
            "Lenta": "-20%",
            "Normal": "+0%",
            "Rápida": "+25%",
            "Muito Rápida": "+50%"
        }
        return speed_map.get(self.speed_var.get(), "+0%")

    def _on_play(self):
        text = self.text_input.get("1.0", "end-1c").strip()
        if not text or text == "Digite seu texto aqui...":
            messagebox.showwarning("Aviso", "Digite um texto para converter em voz!")
            return

        self.play_btn.config(state="disabled", bg="#7a3a4a")
        self.status_label.config(text="⏳ Gerando áudio...", fg="#f0c040")
        self.root.update()

        thread = threading.Thread(target=self._generate_and_play, args=(text,), daemon=True)
        thread.start()

    def _generate_and_play(self, text):
        try:
            rate = self._get_rate()
            volume_val = self.volume_var.get()
            volume_str = f"+{volume_val - 100}%" if volume_val <= 100 else f"+0%"

            async def generate():
                communicate = edge_tts.Communicate(text, VOICE, rate=rate, volume=volume_str)
                await communicate.save(self.temp_file)

            asyncio.run(generate())

            self.root.after(0, lambda: self.status_label.config(text="🔊 Reproduzindo...", fg="#4ecca3"))

            pygame.mixer.music.load(self.temp_file)
            pygame.mixer.music.set_volume(volume_val / 100)
            pygame.mixer.music.play()
            self.is_playing = True

            while pygame.mixer.music.get_busy() and self.is_playing:
                pygame.time.Clock().tick(10)

            self.root.after(0, self._reset_ui)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao gerar áudio:\n{e}"))
            self.root.after(0, self._reset_ui)

    def _on_stop(self):
        self.is_playing = False
        pygame.mixer.music.stop()
        self._reset_ui()

    def _reset_ui(self):
        self.play_btn.config(state="normal", bg="#e94560")
        self.status_label.config(text="✅ Pronto", fg="#4ecca3")

    def on_closing(self):
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        if os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = TextToSpeechApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
