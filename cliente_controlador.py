import sys
import subprocess
import threading
import base64
from io import BytesIO
import tkinter as tk

def auto_install(packages):
    import importlib
    for pkg, import_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"Instalando dependência: {pkg}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])
            except subprocess.CalledProcessError:
                print(f"Ambiente protegido detectado! Forçando instalação de {pkg}...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '--break-system-packages'])

print("Checando bibliotecas...")
# ===== ALTERAÇÃO =====
# Removido o pygame! O seu Python (3.14) é recente demais e o Pygame tenta compilar por baixo dos panos na máquina e dá erro.
# Substituímos pelo 'tkinter' que já vem 100% nativo em todo Python do Windows/Linux e faz a mesma coisa! Em contrapartida
auto_install([
    ('supabase', 'supabase'),
    ('Pillow', 'PIL')
])

from PIL import Image, ImageTk
from supabase import create_client, Client

SUPABASE_URL = "https://wdwiwfepukjoihxpqkvz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indkd2l3ZmVwdWtqb2loeHBxa3Z6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTc2NzkxOCwiZXhwIjoyMDkxMzQzOTE4fQ.v8B6q0Ji03hmIt_Zun3I7tT3iZYLCyGBLC8naq5QyYw"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class RemoteDesktopClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Meu ZYDESK - Controlador (Você)")
        self.width = 1024
        self.height = 576
        self.root.geometry(f"{self.width}x{self.height}")
        
        # Pinta o fundo de escuro
        self.label = tk.Label(root, bg="#141414")
        self.label.pack(fill="both", expand=True)
        
        # Monitorando o Mouse e Teclados pelo Tkinter
        self.root.bind("<Button-1>", lambda e: self.on_click(e, 'left'))
        self.root.bind("<Button-2>", lambda e: self.on_click(e, 'middle'))
        self.root.bind("<Button-3>", lambda e: self.on_click(e, 'right'))
        self.root.bind("<MouseWheel>", self.on_scroll_windows) # Windows Scroll
        self.root.bind("<Button-4>", self.on_scroll_linux_up) # Linux Scroll pra cima
        self.root.bind("<Button-5>", self.on_scroll_linux_down) # Linux scroll pra baixo
        self.root.bind("<Key>", self.on_key)
        
        # Inicia função de loop paralelo sem travar interface
        self.root.after(100, self.fetch_screen)
        
    def fetch_screen(self):
        def _fetch():
            try:
                res = supabase.table('screen_stream').select('image_b64').eq('id', 1).execute()
                if res.data and res.data[0].get('image_b64'):
                    b64_data = res.data[0]['image_b64']
                    if b64_data:
                        img_data = base64.b64decode(b64_data)
                        img = Image.open(BytesIO(img_data)).convert('RGB')
                        
                        # Ajustar o tamanho dinamicamente para o que você estiver vendo ao esticar janela
                        current_w = self.root.winfo_width()
                        current_h = self.root.winfo_height()
                        
                        # Evita bugar se minimizar e a janela bater em 1x1 pixels
                        if current_w > 10 and current_h > 10:
                            # Filtro Lanczos puxa resoluções mais nítidas
                            img = img.resize((current_w, current_h), Image.LANCZOS)
                            
                        # Converte pra objeto exclusivo de tela nativa no Tkinter
                        tk_img = ImageTk.PhotoImage(image=img)
                        # Devolve imagem calculada na mainthread!
                        self.root.after(0, self.update_image, tk_img)
            except Exception as e:
                pass
            
            # Repete a busca 5 vezes por segundo para economizar supabase
            self.root.after(200, self.fetch_screen)
            
        threading.Thread(target=_fetch, daemon=True).start()
        
    def update_image(self, tk_img):
        self.label.config(image=tk_img)
        self.label.image = tk_img # Ancorar a memoria senão a imagem pisca preta
        
    def send_command(self, action, x=None, y=None, button=None, key_name=None):
        def _send():
            try:
                cmd = {'action': action}
                if x is not None: cmd['x'] = x
                if y is not None: cmd['y'] = y
                if button: cmd['button'] = button
                if key_name: cmd['key_name'] = key_name
                supabase.table('remote_commands').insert(cmd).execute()
            except Exception as e:
                pass
        # Thread para disparar ao banco mais rápido
        threading.Thread(target=_send, daemon=True).start()

    def on_click(self, event, button):
        current_w = self.root.winfo_width()
        current_h = self.root.winfo_height()
        norm_x = event.x / current_w
        norm_y = event.y / current_h
        self.send_command('click', x=norm_x, y=norm_y, button=button)

    def on_scroll_windows(self, event):
        self.send_command('scroll', y=event.delta)

    def on_scroll_linux_up(self, event):
        self.send_command('scroll', y=300)

    def on_scroll_linux_down(self, event):
        self.send_command('scroll', y=-300)

    def on_key(self, event):
        # Traduz teclas do TKinter pro Pyautogui padrao dele -> 'Return' pra 'enter'
        key = event.keysym.lower()
        if key == 'return': key = 'enter'
        if key == 'escape': key = 'esc'
        if key.startswith('shift'): key = 'shift'
        if key.startswith('control'): key = 'ctrl'
        if key.startswith('alt'): key = 'alt'
        # Em caso especial como espaço, converta-se para 'space'
        if key == 'space': key = 'space'
        
        self.send_command('type', key_name=key)

if __name__ == "__main__":
    print("=======================================")
    print("CLIENTE CONTROLADOR INICIADO! (Via nativo)")
    print("Feche a janela popup para sair e parar o script.")
    print("=======================================")
    root = tk.Tk()
    app = RemoteDesktopClient(root)
    root.mainloop()
