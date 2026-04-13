from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import edge_tts
import asyncio
import tempfile
import os
import base64
import threading
import pygame
import cv2
import queue
import time

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE = "pt-BR-AntonioNeural"
OWNER_PHOTO = os.path.join(BASE_DIR, "Foto de 2026-04-12 23-06-54.728319.jpeg")

pygame.mixer.init()

TEMP_FILE = os.path.join(tempfile.gettempdir(), "rubi_response.mp3")
CAPTURE_FILE = os.path.join(tempfile.gettempdir(), "rubi_capture.jpg")
AUDIO_FILE = os.path.join(tempfile.gettempdir(), "rubi_audio.wav")
NOTIFY_FILE = os.path.join(tempfile.gettempdir(), "rubi_notify.mp3")

event_queue = queue.Queue()
is_playing = False
is_listening = False
is_speaking = False
voice_thread = None
is_playing = False

API_KEY = "AIzaSyDBoCerLD476h-aKggjPsOB6aX2C8TJ2tc"

GEMINI_PROMPT = """Você é a Rubi, minha assistente direta e gente boa. Responda só o que foi perguntado, sem apresentações, sem enrolação e sem textos longos. Use humor leve e trocadilhos quando fizer sentido, mas sem forçar. Fale como uma pessoa normal, simples e útil. IMPORTANTE: Nunca use emojis, emoticons, ou qualquer tipo de figurinha nas suas respostas. Use apenas texto puro."""


async def generate_speech(text, rate="+50%", volume="+0%"):
    communicate = edge_tts.Communicate(text, VOICE, rate=rate, volume=volume)
    await communicate.save(TEMP_FILE)


def generate_speech_thread(text, rate, volume):
    global is_playing, is_speaking
    try:
        event_queue.put('{"type": "speaking", "status": true}')
        event_queue.put('{"type": "mode", "mode": "speaking"}')
        is_speaking = True
        
        asyncio.run(generate_speech(text, rate, volume))
        
        if os.path.exists(TEMP_FILE):
            pygame.mixer.music.load(TEMP_FILE)
            pygame.mixer.music.play()
            is_playing = True
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            is_playing = False
            is_speaking = False
            event_queue.put('{"type": "speaking", "status": false}')
            event_queue.put('{"type": "mode", "mode": "idle"}')
            
            if text.strip().endswith('?') or text.strip().endswith('?'):
                event_queue.put('{"type": "auto_listen", "status": true}')
            
            try:
                os.remove(TEMP_FILE)
            except:
                pass
    except Exception as e:
        print(f"Erro ao gerar audio: {e}")
        is_playing = False
        is_speaking = False
        event_queue.put('{"type": "speaking", "status": false}')
        event_queue.put('{"type": "mode", "mode": "idle"}')


def play_notify_sound():
    try:
        import subprocess
        subprocess.run(['play', '-q', '-n', ' synth 0.15 sin 880'], shell=True, capture_output=True)
    except Exception as e:
        pass


def record_and_recognize():
    pass  # Inutilizado, a logica foi movida para voice_loop localmente para não fechar o mic

def voice_loop():
    global is_listening, is_speaking
    print("[VOICE] Sistema de voz iniciado - diga 'Rubi' para ativar")
    
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        
        print("[VOICE] Conectando ao microfone local...")
        with sr.Microphone() as source:
            print("[VOICE] Ajustando ruidos de ambiente...")
            r.adjust_for_ambient_noise(source, duration=1)
            print("[VOICE] Pronto para ouvir comandos!")
            
            while True:
                try:
                    if is_listening or is_speaking:
                        time.sleep(0.1)
                        continue
                    
                    event_queue.put('{"type": "mode", "mode": "idle"}')
                    
                    try:
                        audio = r.listen(source, timeout=1)
                        text = r.recognize_google(audio, language='pt-BR').lower()
                        print(f"[VOICE DEBUG] Ouviu: '{text}'")
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception as e:
                        continue
                    
                    if not text:
                        continue
                    
                    if 'rubi' in text:
                        event_queue.put('{"type": "wake_word", "detected": true}')
                        event_queue.put('{"type": "mode", "mode": "listening"}')
                        play_notify_sound()
                        
                        command = text.replace('rubi', '').strip()
                        
                        if not command:
                            try:
                                audio2 = r.listen(source, timeout=5)
                                command = r.recognize_google(audio2, language='pt-BR').lower()
                                print(f"[VOICE DEBUG] Ouviu comando: '{command}'")
                            except:
                                command = ""
                        
                        if command:
                            event_queue.put('{"type": "mode", "mode": "processing"}')
                            event_queue.put(f'{{"type": "voice_command", "text": "{command}"}}')
                    
                    event_queue.put('{"type": "mode", "mode": "idle"}')
                    
                except Exception as e:
                    print(f"Erro no loop de voz: {e}")
                    event_queue.put('{"type": "mode", "mode": "idle"}')
                    time.sleep(1)
                    
    except Exception as e:
        print(f"[VOICE] Falha critica no mic: {e}")


@app.route("/api/listen", methods=["POST"])
def start_listening():
    global is_listening
    is_listening = True
    return jsonify({"status": "listening"})


@app.route("/api/stop_listening", methods=["POST"])
def stop_listening():
    global is_listening
    is_listening = False
    return jsonify({"status": "stopped"})


@app.route("/api/voice_status", methods=["GET"])
def voice_status():
    return jsonify({
        "listening": is_listening,
        "speaking": is_speaking,
        "playing": is_playing
    })


@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "index.html"))


@app.route("/api/chat", methods=["POST"])
def chat():
    global is_playing
    
    data = request.json
    message = data.get("message", "")
    speed = data.get("speed", "+0%")
    volume = data.get("volume", "+0%")
    
    if not message:
        return jsonify({"error": "Mensagem vazia"}), 400
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel("gemini-3-flash-preview")
        
        full_prompt = f"{GEMINI_PROMPT}\n\nUsuario: {message}\nRubi:"
        response = model.generate_content(full_prompt)
        reply = response.text.strip()
        
        if reply.startswith("*"):
            reply = reply.split("*")[-1] if "*" in reply[1:] else reply[1:]
        
        thread = threading.Thread(target=generate_speech_thread, args=(reply, speed, volume))
        thread.start()
        
        return jsonify({
            "reply": reply,
            "status": "playing"
        })
        
    except ImportError:
        return jsonify({"error": "Google Generative AI não instalado. Execute: pip install google-generativeai"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def status():
    global is_playing
    return jsonify({"playing": is_playing})


def capture_webcam():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.5)
        cap.set(cv2.CAP_PROP_CONTRAST, 0.5)
        
        for _ in range(10):
            cap.read()
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            cv2.imwrite(CAPTURE_FILE, frame)
            cv2.imwrite(os.path.join(BASE_DIR, "debug_capture.jpg"), frame)
            with open(CAPTURE_FILE, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None
    except Exception as e:
        print(f"Erro ao capturar webcam: {e}")
        return None


def verify_face():
    try:
        if not os.path.exists(OWNER_PHOTO):
            return None, None
        
        if not os.path.exists(CAPTURE_FILE):
            return None, None
        
        with open(CAPTURE_FILE, "rb") as f:
            capture_data = base64.b64encode(f.read()).decode()
        
        try:
            from google import genai
            client = genai.Client(api_key=API_KEY)
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {"text": """Compare these two face photos.
Image 1: registered owner
Image 2: current photo

Ignore clothes, hair, background. Only face matters.

Give me a percentage match (0-100%) of how similar the faces are."""},
                    [ OWNER_PHOTO, CAPTURE_FILE ]
                ]
            )
            
            result = response.text.strip().upper()
            print(f"[VERIFICACAO] Resposta da IA: {result}")
            
            import re
            numbers = re.findall(r'\d+', result)
            if numbers:
                match_percent = max([int(n) for n in numbers if int(n) <= 100])
                print(f"[VERIFICACAO] Percentual: {match_percent}%")
                verified = match_percent >= 85
            else:
                verified = "YES" in result or "SAME" in result or "MATCH" in result
            
        except ImportError:
            from google.generativeai import GenerativeModel
            import google.generativeai as genai
            genai.configure(api_key=API_KEY)
            model = GenerativeModel("gemini-2.0-flash")
            
            response = model.generate_content([
                {"text": """Compare these two face photos.
Image 1: registered owner
Image 2: current photo

Ignore clothes, hair, background. Only face matters.

Give me a percentage match (0-100%) of how similar the faces are."""},
                {"inline_data": {"mime_type": "image/jpeg", "data": open(OWNER_PHOTO, "rb").read()}},
                {"inline_data": {"mime_type": "image/jpeg", "data": open(CAPTURE_FILE, "rb").read()}}
            ])
            
            result = response.text.strip().upper()
            print(f"[VERIFICACAO] Resposta da IA: {result}")
            
            import re
            numbers = re.findall(r'\d+', result)
            if numbers:
                match_percent = max([int(n) for n in numbers if int(n) <= 100])
                print(f"[VERIFICACAO] Percentual: {match_percent}%")
                verified = match_percent >= 85
            else:
                verified = "YES" in result or "SAME" in result or "MATCH" in result
        
        try:
            os.remove(CAPTURE_FILE)
        except:
            pass
        
        return verified, capture_data
        
    except Exception as e:
        print(f"Erro na verificação: {e}")
        try:
            os.remove(CAPTURE_FILE)
        except:
            pass
        return None, None


@app.route("/api/verify", methods=["POST"])
def verify():
    capture_result = capture_webcam()
    
    if capture_result is None:
        return jsonify({"verified": True, "error": "webcam", "captured_image": None})
    
    verified, capture_data = verify_face()
    
    if verified is None:
        return jsonify({"verified": True, "error": "verify", "captured_image": capture_data})
    
    return jsonify({"verified": verified, "captured_image": capture_data})


@app.route("/api/chat_with_verify", methods=["POST"])
def chat_with_verify():
    global is_playing
    
    data = request.json
    message = data.get("message", "")
    first_message = data.get("first", False)
    
    if not message:
        return jsonify({"error": "Mensagem vazia"}), 400
    
    captured_image = None
    verified = True
    
    if first_message:
        captured_image = capture_webcam()
        
        if captured_image is not None:
            verified, img_data = verify_face()
            captured_image = img_data
            
            if verified is False:
                return jsonify({
                    "reply": None,
                    "status": "idle",
                    "verified": False,
                    "captured_image": captured_image,
                    "access_denied": True
                })
    
    try:
        try:
            from google import genai
            client = genai.Client(api_key=API_KEY)
            
            full_prompt = f"{GEMINI_PROMPT}\n\nUsuario: {message}\nRubi:"
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt
            )
            reply = response.text.strip()
            
        except ImportError:
            import google.generativeai as genai
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            full_prompt = f"{GEMINI_PROMPT}\n\nUsuario: {message}\nRubi:"
            response = model.generate_content(full_prompt)
            reply = response.text.strip()
        
        if reply.startswith("*"):
            reply = reply.split("*")[-1] if "*" in reply[1:] else reply[1:]
        
        thread = threading.Thread(target=generate_speech_thread, args=(reply, "+0%", "+0%"))
        thread.start()
        
        return jsonify({
            "reply": reply,
            "status": "playing",
            "verified": verified,
            "captured_image": captured_image,
            "access_denied": False
        })
        
    except ImportError:
        return jsonify({"error": "Google Generative AI não instalado. Execute: pip install google-generativeai"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/events")
def events():
    def generate():
        while True:
            try:
                event = event_queue.get(timeout=30)
                yield f"data: {event}\n\n"
            except:
                yield f"data: heartbeat\n\n"
    
    response = app.response_class(
        response=generate(),
        status=200,
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@app.route("/api/stop", methods=["POST"])
def stop():
    global is_playing
    is_playing = False
    pygame.mixer.music.stop()
    try:
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)
    except:
        pass
    return jsonify({"status": "stopped"})


if __name__ == "__main__":
    print("=" * 50)
    print("  RUBI ZYNAPSE - Sistema de IA")
    print("=" * 50)
    print()
    print("  Iniciando Interface Nativa (Chrome App Mode)...")
    print()
    print("=" * 50)
    print()
    
    print("[VOICE] Iniciando loop de voz em segundo plano...")
    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()
    
    def open_browser():
        import time
        import subprocess
        time.sleep(1.5)
        try:
            subprocess.Popen(['google-chrome', '--app=http://127.0.0.1:5000', '--window-size=1200,800'])
        except Exception as e:
            print(f"Não foi possivel abrir o chrome: {e}")
            
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
