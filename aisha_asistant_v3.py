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

def choose_assistant_name(recognizer, source):
    print("Ассистенттің атын таңдаңыз (мысалы, 'Айша', 'Болат', 'Қыран'): ")
    while True:
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            name = recognizer.recognize_google(audio, language='kk').lower()
            name = tokenize(name)[0] if tokenize(name) else None
            if name and is_kazakh_word(name):
                print(f"Ассистенттің аты: {name}")
                return name
            else:
                print("Қазақша атау айтыңыз.")
        except (sr.UnknownValueError, sr.RequestError, sr.WaitTimeoutError):
            print("Атауды қайта айтыңыз.")
            continue

def listen_for_trigger(recognizer, source, trigger_word):
    print(f"«{trigger_word}» деп айтыңыз...")
    while True:
        try:
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=5)
            text = recognizer.recognize_google(audio, language='kk').lower()
            if trigger_word in text:
                print(f"Салем, пилот! Команда күтемін.")
                return True
        except (s

                r.UnknownValueError, sr.RequestError, sr.WaitTimeoutError):
            continue

def process_command(recognizer, source):
    try:
        audio = recognizer.listen(source, timeout=15, phrase_time_limit=10)
        text = recognizer.recognize_google(audio, language='kk')
        words = tokenize(text)
        kazakh_words = [w for w in words if is_kazakh_word(w)]

        if any(word in ['қос', 'ос', 'берік', 'зеңбірек'] for word in kazakh_words):
            print("Қосамын, жүйелерді іске қосамын!")
        elif any(word in ['өшір', 'тоқтат', 'аяқта'] for word in kazakh_words):
            print("Ассистент өшіріледі. Сау болыңыз, пилот!")
            return False
        else:
            print("Команда анықталмады. Нақтырақ айтыңыз.")

    except sr.UnknownValueError:
        print("Сөзіңіз танылмады.")
    except sr.RequestError as e:
        print(f"Қызмет қатесі: {e}")
    except sr.WaitTimeoutError:
        print("Сөйлемеген сияқтысыз...")

    return True

def recognize_and_analyze():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        trigger_word = choose_assistant_name(recognizer, source)
        while True:
            if listen_for_trigger(recognizer, source, trigger_word):
                if not process_command(recognizer, source):
                    break
                time.sleep(0.5)

if __name__ == "__main__":
    recognize_and_analyze()
