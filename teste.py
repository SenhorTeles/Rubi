import speech_recognition as sr

# Inicializa o reconhecedor
r = sr.Recognizer()

# Usa o microfone
with sr.Microphone() as source:
    print("🎤 Fale algo... (Ctrl+C para sair)")
    
    # Ajusta o ruído ambiente
    r.adjust_for_ambient_noise(source)

    while True:
        try:
            print("🔴 Ouvindo...")
            audio = r.listen(source)

            print("🧠 Processando...")
            texto = r.recognize_google(audio, language="pt-BR")

            print("Você disse:", texto)
            print("-" * 30)

        except sr.UnknownValueError:
            print("Não entendi...")
        except sr.RequestError as e:
            print(f"Erro no serviço: {e}")
        except KeyboardInterrupt:
            print("\nEncerrado.")
            break