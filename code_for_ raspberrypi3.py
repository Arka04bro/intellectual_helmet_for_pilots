from gpiozero import OutputDevice
import vosk
import sounddevice as sd
import json
import time
import cv2
import numpy as np
import random
import math
import requests
from datetime import datetime

# Инициализация реле
relay = OutputDevice(17, active_high=False)  # GPIO17, активно низким уровнем

# Инициализация модели Vosk для казахского языка
model_path = '/home/pi/Downloads/vosk-model-small-kz-0.15'
model = vosk.Model(model_path)

# Настройка аудиопотока (16kHz, моно, 16-бит)
samplerate = 16000
device = sd.default.device  # Использовать микрофон по умолчанию

# Захват видео с веб-камеры
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Ошибка: Не удалось открыть веб-камеру")
    exit()

# Координаты Актобе
AKTOBE_LAT = 50.2833
AKTOBE_LON = 57.1667

# Функция для получения погоды
def get_weather():
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": AKTOBE_LAT,
        "longitude": AKTOBE_LON,
        "current_weather": True
    }
    try:
        response = requests.get(base_url, params=params, timeout=3)
        data = response.json()
        return data.get("current_weather", {})
    except Exception as e:
        print(f"Ошибка получения погоды: {e}")
        return {}

# Функция для рисования расширенного радара
def draw_radar(img, center, radius, angle, time_now):
    # Круги радара
    for r in [radius, radius // 2, radius // 3]:
        cv2.circle(img, center, r, (0, 255, 0), 1)
    # Сканирующая линия с затуханием
    scan_x = int(center[0] + radius * np.cos(np.radians(angle)))
    scan_y = int(center[1] + radius * np.sin(np.radians(angle)))
    cv2.line(img, center, (scan_x, scan_y), (0, int(255 * (1 - (time_now % 1))), 0), 1)
    # Метки объектов с ID
    for i in range(3):
        obj_angle = (angle + i * 120) % 360
        dist = random.uniform(radius // 3, radius)
        x = int(center[0] + dist * np.cos(np.radians(obj_angle)))
        y = int(center[1] + dist * np.sin(np.radians(obj_angle)))
        alpha = 255 * (1 - (time_now + i * 0.2) % 1)  # Анимация мигания
        cv2.circle(img, (x, y), 4, (0, int(alpha), 0), -1)
        cv2.putText(img, f"ID{i+1}", (x + 5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, int(alpha), 0), 1)

# Функция для рисования шкалы крена/тангажа
def draw_pitch_roll(img, pitch, roll):
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    # Поворот для крена
    rot_matrix = cv2.getRotationMatrix2D(center, roll, 1.0)
    rotated = cv2.warpAffine(img, rot_matrix, (w, h))
    # Линии горизонта
    for i in range(-3, 4):
        y = center[1] + int(i * 15 - pitch * 5)
        if i == 0:
            cv2.line(rotated, (center[0] - 40, y), (center[0] - 15, y), (0, 255, 0), 1)
            cv2.line(rotated, (center[0] + 15, y), (center[0] + 40, y), (0, 255, 0), 1)
        else:
            cv2.line(rotated, (center[0] - 25, y), (center[0] + 25, y), (0, 255, 0), 1)
            cv2.putText(rotated, str(-i * 5), (center[0] + 30, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
    return rotated

# Функция для рисования компаса
def draw_compass(img, heading):
    h, w = img.shape[:2]
    center = (w - 50, 50)
    radius = 30
    cv2.circle(img, center, radius, (0, 255, 0), 1)
    # Метки сторон света
    for angle, label in [(0, 'N'), (90, 'E'), (180, 'S'), (270, 'W')]:
        x = int(center[0] + (radius + 10) * np.cos(np.radians(angle)))
        y = int(center[1] + (radius + 10) * np.sin(np.radians(angle)))
        cv2.putText(img, label, (x - 5, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
    # Стрелка курса
    arrow_x = int(center[0] + radius * 0.8 * np.cos(np.radians(heading)))
    arrow_y = int(center[1] + radius * 0.8 * np.sin(np.radians(heading)))
    cv2.line(img, center, (arrow_x, arrow_y), (0, 255, 0), 1)

# Функция для рисования шкал высоты и скорости
def draw_alt_speed(img, altitude, speed):
    h, w = img.shape[:2]
    # Шкала высоты (слева)
    alt_y = int(h * (1 - altitude / 20000))  # Нормализация 0-20000 м
    cv2.rectangle(img, (20, h - 100), (40, h - 300), (0, 255, 0), 1)
    cv2.rectangle(img, (20, h - alt_y - 10), (40, h - alt_y + 10), (0, 255, 0), -1)
    cv2.putText(img, f"{int(altitude)}", (45, h - alt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    # Шкала скорости (справа)
    spd_y = int(h * (1 - speed / 1200))  # Нормализация 0-1200 км/ч
    cv2.rectangle(img, (w - 40, h - 100), (w - 20, h - 300), (0, 255, 0), 1)
    cv2.rectangle(img, (w - 40, h - spd_y - 10), (w - 20, h - spd_y + 10), (0, 255, 0), -1)
    cv2.putText(img, f"{int(speed)}", (w - 60, h - spd_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

# Функция для рисования индикатора вертикальной скорости (VSI)
def draw_vsi(img, vsi):
    h, w = img.shape[:2]
    center = (w - 50, h - 50)
    radius = 20
    cv2.circle(img, center, radius, (0, 255, 0), 1)
    angle = np.clip(vsi * 9, -90, 90)  # VSI от -10 до 10 м/с
    arrow_x = int(center[0] + radius * 0.8 * np.cos(np.radians(angle + 90)))
    arrow_y = int(center[1] + radius * 0.8 * np.sin(np.radians(angle + 90)))
    color = (0, 255, 0) if abs(vsi) < 5 else (0, 0, 255)  # Красный при экстремальных значениях
    cv2.line(img, center, (arrow_x, arrow_y), color, 1)
    cv2.putText(img, f"{vsi:.1f}", (center[0] + 25, center[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

# Функция для рисования сетки прицела
def draw_reticle(img, time_now):
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    # Основной крест
    cv2.line(img, (center[0] - 15, center[1]), (center[0] + 15, center[1]), (0, 255, 0), 1)
    cv2.line(img, (center[0], center[1] - 15), (center[0], center[1] + 15), (0, 255, 0), 1)
    # Динамическая сетка
    for i in range(1, 3):
        offset = int(10 * (1 + 0.2 * np.sin(time_now * 2 + i)))
        cv2.rectangle(img, (center[0] - offset, center[1] - offset), 
                     (center[0] + offset, center[1] + offset), (0, 255, 0), 1)

# Функция для рисования динамических меток
def draw_targets(img, time_now):
    h, w = img.shape[:2]
    for i in range(2):
        x = int(w * (0.3 + 0.4 * ((time_now + i) % 2)))
        y = int(h * (0.3 + 0.2 * np.sin(time_now + i)))
        alpha = 255 * (1 - (time_now + i * 0.5) % 1)  # Мигание
        cv2.rectangle(img, (x - 10, y - 10), (x + 10, y + 10), (0, int(alpha), 0), 1)
        cv2.putText(img, f"T{i+1}", (x + 15, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, int(alpha), 0), 1)

# Функция для рисования индикаторов состояния
def draw_status(img, fuel, temp, pressure):
    h, w = img.shape[:2]
    # Топливо
    fuel_color = (0, 255, 0) if fuel > 30 else (0, 0, 255)
    cv2.putText(img, f"FUEL: {fuel}%", (10, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.4, fuel_color, 1)
    # Температура
    temp_color = (0, 255, 0) if temp < 80 else (0, 0, 255)
    cv2.putText(img, f"TEMP: {temp}C", (10, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, temp_color, 1)
    # Давление
    press_color = (0, 255, 0) if 0.9 < pressure < 1.1 else (0, 0, 255)
    cv2.putText(img, f"PRESS: {pressure:.2f}", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, press_color, 1)

# Функция для рисования основного HUD
def draw_hud(img, height, speed, heading):
    font_scale = 0.5
    cv2.putText(img, f"ALT: {height} m", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), 1)
    cv2.putText(img, f"SPD: {speed} km/h", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), 1)
    cv2.putText(img, f"HDG: {heading} deg", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), 1)

# Функция для отображения погоды
def draw_weather(img, weather):
    if not weather:
        return
        
    # Погодный блок в правом верхнем углу
    temp = weather.get('temperature', 'N/A')
    windspeed = weather.get('windspeed', 'N/A')
    winddirection = weather.get('winddirection', 'N/A')
    
    cv2.putText(img, f"Aktobe weather:", (img.shape[1] - 250, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    cv2.putText(img, f"Temp: {temp}°C", (img.shape[1] - 250, 50), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    cv2.putText(img, f"Wind: {windspeed} м/с", (img.shape[1] - 250, 70), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    cv2.putText(img, f"Direction: {winddirection}°", (img.shape[1] - 250, 90), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    cv2.putText(img, f"Time: {datetime.now().strftime('%H:%M:%S')}", 
               (img.shape[1] - 250, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

# Основной цикл
radar_angle = 0
start_time = time.time()
last_weather_update = 0
weather_data = {}

# Создаем полноэкранное окно
cv2.namedWindow('Pilot HUD View', cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty('Pilot HUD View', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# Запуск аудиопотока в отдельном потоке
with sd.RawInputStream(samplerate=samplerate, blocksize=8000, device=device, 
                      dtype='int16', channels=1, callback=None) as stream:
    
    rec = vosk.KaldiRecognizer(model, samplerate)
    rec.SetWords(True)  # Включить вывод на уровне слов

    print("Говорите (нажмите Ctrl+C для выхода)...")
    while True:
        try:
            # Обновляем погоду каждые 60 секунд
            current_time = time.time()
            if current_time - last_weather_update > 60:
                weather_data = get_weather()
                last_weather_update = current_time
                print("Погода обновлена")

            # Обработка аудио
            data, overflowed = stream.read(4000)  # Чтение аудиоданных
            
            # Преобразование буфера в байты
            if isinstance(data, (bytes, bytearray)):
                data_bytes = bytes(data)
            else:
                # Для старых версий sounddevice, возвращающих объекты буфера
                data_bytes = bytes(memoryview(data))
            
            if len(data_bytes) > 0:
                if rec.AcceptWaveform(data_bytes):
                    result = json.loads(rec.Result())
                    if result.get("text"):
                        print(f"Распознано: {result['text']}")
                        if result['text'] == 'қос' or result['text'] == 'ад' or result['text'] == 'ат' :
                            relay.on()  # Включить реле
                            print("Реле ВКЛ")
                        elif result['text'] == 'тоқта' or result['text'] == 'тоқтар':	
                            relay.off()  # Выключить реле
                            print("Реле ВЫКЛ")
                else:
                    result_partial = json.loads(rec.PartialResult())
            
            # Обработка видео
            ret, frame = cap.read()
            if not ret:
                print("Ошибка: Не удалось получить кадр")
                break

            # Работаем с полным кадром
            h, w = frame.shape[:2]
            
            # Текущее время для анимаций
            time_now = time.time() - start_time

            # Шкала крена/тангажа
            fake_pitch = 10 * np.sin(time_now * 0.5)
            fake_roll = 15 * np.sin(time_now * 0.3)
            frame = draw_pitch_roll(frame, fake_pitch, fake_roll)

            # Радар
            radar_center = (int(w * 0.85), int(h * 0.85))
            radar_angle = (radar_angle + 5) % 360
            draw_radar(frame, radar_center, 50, radar_angle, time_now)

            # Компас
            fake_heading = (360 + 90 * np.sin(time_now * 0.2)) % 360
            draw_compass(frame, fake_heading)

            # Шкалы высоты и скорости
            fake_altitude = 5000 + 2000 * np.sin(time_now * 0.1)
            fake_speed = 600 + 200 * np.sin(time_now * 0.15)
            draw_alt_speed(frame, fake_altitude, fake_speed)

            # VSI
            fake_vsi = 5 * np.sin(time_now * 0.4)
            draw_vsi(frame, fake_vsi)

            # Сетка прицела
            draw_reticle(frame, time_now)

            # Динамические метки
            draw_targets(frame, time_now)

            # Индикаторы состояния
            fake_fuel = 50 + 30 * np.sin(time_now * 0.05)
            fake_temp = 60 + 15 * np.sin(time_now * 0.07)
            fake_pressure = 1.0 + 0.1 * np.sin(time_now * 0.06)
            draw_status(frame, int(fake_fuel), int(fake_temp), fake_pressure)

            # Основной HUD
            draw_hud(frame, int(fake_altitude), int(fake_speed), int(fake_heading))
            
            # Отображение погоды
            draw_weather(frame, weather_data)

            # Отображение результата в полноэкранном режиме
            cv2.imshow('Pilot HUD View', frame)

            # Выход по 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        except KeyboardInterrupt:
            print("\nЗавершение работы.")
            relay.off()  # Убедиться, что реле выключено при выходе
            break

# Освобождение ресурсов
cap.release()
cv2.destroyAllWindows()
