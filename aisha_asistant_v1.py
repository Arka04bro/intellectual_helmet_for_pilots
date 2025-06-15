import cv2
import numpy as np
from ultralytics import YOLO

# 1. Загрузка модели
model = YOLO(r"C:\Users\Arkats\Downloads\military_aircraft.pt")  # или ваш сохраненный путь

# 2. Инициализация OpenCV
cap = cv2.VideoCapture(0)  # Веб-камера. Для видео укажите путь к файлу

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # 3. Детекция
    results = model.predict(frame, imgsz=640, conf=0.5)  # conf - порог уверенности
    
    # 4. Визуализация результатов
    for result in results:
        boxes = result.boxes.xyxy.cpu().numpy()  # Координаты bbox
        classes = result.boxes.cls.cpu().numpy()  # Классы
        confs = result.boxes.conf.cpu().numpy()  # Уверенность
        
        for box, cls, conf in zip(boxes, classes, confs):
            x1, y1, x2, y2 = map(int, box)
            label = f"{model.names[int(cls)]} {conf:.2f}"
            
            # Рисуем прямоугольник и текст
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # 5. Показ результата
    cv2.imshow('Military Aircraft Detection', frame)
    
    # Выход по 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
