import speech_recognition as sr
import re
import unicodedata
import time

kazakh_alphabet = set('аәбвгғдеёжзийкқлмнңоөпрстуұүфхһцчшыіэюя')

def is_kazakh_word(word):
    return any(c in kazakh_alphabet for c in word.lower())

def tokenize(text):
    text = unicodedata.normalize('NFKC', text.lower())
    return re.findall(r'[а-яәғқңөұүһ]+', text)

def listen_for_trigger(recognizer, source, trigger_word='айша'):
    print("«Айша» деп айтыңыз...")
    while True:
        try:
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=5)
            text = recognizer.recognize_google(audio, language='kk').lower()
            if trigger_word in text:
                print("Не?")
                return True
        except (sr.UnknownValueError, sr.RequestError, sr.WaitTimeoutError):
            continue  # просто продолжаем слушать

def process_command(recognizer, source):
    try:
        audio = recognizer.listen(source, timeout=15, phrase_time_limit=10)
        text = recognizer.recognize_google(audio, language='kk')
        words = tokenize(text)
        kazakh_words = [w for w in words if is_kazakh_word(w)]

        if any(word in ['қос', 'ос', 'берік', 'зеңбірек'] for word in kazakh_words):
            print("Қосамын ")
        else:
            print("Команда анықталмады.")

    except sr.UnknownValueError:
        print("Сөзіңіз танылмады.")
    except sr.RequestError as e:
        print(f"Қызмет қатесі: {e}")
    except sr.WaitTimeoutError:
        print("Сөйлемеген сияқтысыз...")

def recognize_and_analyze():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        while True:
            if listen_for_trigger(recognizer, source):
                process_command(recognizer, source)
                time.sleep(0.5)

if __name__ == "__main__":
    recognize_and_analyze()
    
