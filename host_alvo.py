import sys
import subprocess
import os

# --- HACK PARA LINUX EXIGENTE COM X11 ---
if sys.platform.startswith('linux'):
    # O Ubuntu/Linux costuma travar o mouse para bibliotecas terceiras
    # Rodamos o comando para liberar a exibição (X server) automaticamente se acessível
    try:
        subprocess.run(['xhost', '+'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
    elif 'WAYLAND_DISPLAY' in os.environ:
        print("====== AVISO CRÍTICO ======")
        print("Seu Linux está usando Wayland. O controle remoto de mouse pelo Pyautogui pode ser bloqueado.")
        print("Recomenda-se iniciar a sessão escolhendo 'Ubuntu no Xorg' na tela de login.")
        print("===========================")

# Função para auto-instalar bibliotecas silenciosamente
def auto_install(packages):
    import importlib
    for pkg, import_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"Instalando independente: {pkg}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])
            except subprocess.CalledProcessError:
                # O Ubuntu/Linux novo bloqueia o pip por padrão (PEP 668). Essa flag foça a instalação global.
                print(f"Ambiente protegido detectado no Linux! Forçando instalação de {pkg}...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '--break-system-packages'])

print("Checando bibliotecas...")
auto_install([
    ('supabase', 'supabase'),
    ('pyautogui', 'pyautogui'),
    ('mss', 'mss'),
    ('Pillow', 'PIL')
])

import time
import base64
from io import BytesIO
import mss
from PIL import Image
import pyautogui
from supabase import create_client, Client

# === CREDENCIAIS DA API ===
SUPABASE_URL = "https://wdwiwfepukjoihxpqkvz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indkd2l3ZmVwdWtqb2loeHBxa3Z6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTc2NzkxOCwiZXhwIjoyMDkxMzQzOTE4fQ.v8B6q0Ji03hmIt_Zun3I7tT3iZYLCyGBLC8naq5QyYw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Desativar fail-safe do pyautogui para ele não crashar se o mouse for muito pro canto
pyautogui.FAILSAFE = False
# Pequena pausa entre comandos do teclado pra evitar erros
pyautogui.PAUSE = 0.05

def capture_screen_and_send():
    """Tira foto da tela, comprime e envia base64 no supabase"""
    with mss.mss() as sct:
        # Pega do primeiro monitor padrão
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        
        # Converter para Image do Pillow e remover o ALPHA (BGRA -> RGB) para diminuir tamanho
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        # Reduzir tamanho/resolução para focar em VELOCIDADE de rede (Supabase aguenta melhor)
        # 1024x576 é uma resolução boa HD otimizada (proporção 16:9)
        img.thumbnail((1024, 576)) 
        
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=45) # Compressão JPEG alta (menor peso, imagem mais fosca)
        img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        try:
            # Atualiza apenas o ID 1, para não criar várias imagens e sobrecarregar o banco
            supabase.table('screen_stream').update({'image_b64': img_b64}).eq('id', 1).execute()
        except Exception as e:
            print(f"Erro ao enviar frame da tela: {e}")

def process_commands():
    """Lê os comandos na fila do Supabase, executa-os e deleta"""
    try:
        # Puxa comandos pendentes ordenados pelo ID (ordem de chegada)
        res = supabase.table('remote_commands').select('*').order('id', desc=False).execute()
        commands = res.data
        if not commands: 
            return
            
        screen_width, screen_height = pyautogui.size()
        ids_to_delete = []
        
        for cmd in commands:
            ids_to_delete.append(cmd['id'])
            action = cmd.get('action')
            
            try:
                if action == 'click':
                    # Posições normativas que vêm do cliente (0.0 a 1.0)
                    # Multiplica pelo tamanho real da tela aqui do lado de quem vai executar o clique
                    x = int(cmd.get('x', 0) * screen_width)
                    y = int(cmd.get('y', 0) * screen_height)
                    button = cmd.get('button', 'left')
                    
                    pyautogui.click(x=x, y=y, button=button)
                    print(f"-> Clicou em X:{x}, Y:{y} [Botão: {button}]")
                    
                elif action == 'scroll':
                    amount = int(cmd.get('y', 0)) # Usamos o Y para enviar o valor de scroll
                    pyautogui.scroll(amount)
                    
                elif action == 'type':
                    key = cmd.get('key_name')
                    if not key:
                        continue
                    
                    # Se for tecla especial cadastrada no pyautogui (ex: enter, space, backspace, esc)
                    if key in pyautogui.KEYBOARD_KEYS:
                        pyautogui.press(key)
                    else:
                        pyautogui.write(key)
                    print(f"-> Teclou: {key}")
                    
            except Exception as cmd_e:
                print(f"Falha ao executar comando '{action}': {cmd_e}")
                
        # Apaga todos os comandos que a gente acabou de executar pra não executar de novo
        if ids_to_delete:
             supabase.table('remote_commands').delete().in_('id', ids_to_delete).execute()
             
    except Exception as e:
        print(f"Erro processando comandos: {e}")

def main():
    print("=======================================")
    print("HOST ALVO INICIADO (Sofrendo controle)")
    print("Transmitindo tela pelo Supabase... Aperte CTRL+C para parar.")
    print("=======================================")
    
    while True:
        capture_screen_and_send()
        process_commands()
        
        # Pausa leve de ~0.15s (cerca de 6 frames por segundo).
        # Se deixar muito rápido (sem sleep), sua cota mensal de requisições API do SUPABASE vai sumir!
        time.sleep(0.15) 

if __name__ == '__main__':
    main()
