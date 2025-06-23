/*
 * This software may be distributed and modified under the terms of the GNU
 * General Public License version 2 (GPL2) as published by the Free Software
 * Foundation and appearing in the file GPL2.TXT included in the packaging of
 * this file. Please note that GPL2 Section 2[b] requires that all works based
 * on this software must also be made publicly available under the terms of
 * the GPL2 ("Copyleft").
 * Contact information
 * -------------------
 * Kristian Lauszus, TKJ Electronics
 * Web      :  http://www.tkjelectronics.com
 * e-mail   :  kristianl@tkjelectronics.com
 */

#include <Stepper.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU6050.h>
#include "Kalman.h" // Source: https://github.com/TKJElectronics/KalmanFilter

#define RESTRICT_PITCH // Comment out to restrict roll to ±90deg instead

Kalman kalmanX;
Kalman kalmanY;

/* IMU Data */
double accX, accY, accZ;
double gyroX, gyroY, gyroZ;
int16_t tempRaw;

double gyroXangle, gyroYangle;
double compAngleX, compAngleY;
double kalAngleX, kalAngleY;
double yaw; // Угол рысканья для поворота направо/налево
double smoothedYaw; // Сглаженный yaw

uint32_t timer;
uint8_t i2cData[14];

Stepper stepper2(100, 8, 9, 10, 11); // Двигатель 2: пины 8, 9, 10, 11 для реверсивного управления
Stepper stepper1(100, 4, 5, 6, 7);   // Двигатель 1: пины 4, 5, 6, 7

#define ENA_PIN 3  // ШИМ для двигателя 1
#define ENB_PIN 2  // Пин 2: цифровой (вкл/выкл), т.к. не ШИМ

#define POT_PIN A0 // Один потенциометр для ENA и ENB

int previousx = 0;
int previousy = 0;

MPU6050 mpu;

void setup() {
  stepper2.setSpeed(200);
  stepper1.setSpeed(200);

  pinMode(ENA_PIN, OUTPUT);
  pinMode(ENB_PIN, OUTPUT);
  analogWrite(ENA_PIN, 255); // Максимальная мощность
  digitalWrite(ENB_PIN, HIGH); // Пин 2: вкл

  pinMode(POT_PIN, INPUT);

  Serial.begin(115200);
  Wire.begin();
  TWBR = ((F_CPU / 400000L) - 16) / 2;

  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.print(F("Ошибка чтения сенсора"));
    while (1);
  }

  i2cData[0] = 7;
  i2cData[1] = 0x00;
  i2cData[2] = 0x00;
  i2cData[3] = 0x00;
  I2Cdev::writeBytes(0x68, 0x19, 4, i2cData);
  I2Cdev::writeByte(0x68, 0x6B, 0x01);

  delay(100);

  I2Cdev::readBytes(0x68, 0x3B, 6, i2cData);
  accX = (i2cData[0] << 8) | i2cData[1];
  accY = (i2cData[2] << 8) | i2cData[3];
  accZ = (i2cData[4] << 8) | i2cData[5];

#ifdef RESTRICT_PITCH
  double roll = atan2(accY, accZ) * RAD_TO_DEG;
  double pitch = atan(-accX / sqrt(accY * accY + accZ * accZ)) * RAD_TO_DEG;
#else
  double roll = atan(accY / sqrt(accX * accX + accZ * accZ)) * RAD_TO_DEG;
  double pitch = atan2(-accX, accZ) * RAD_TO_DEG;
#endif

  kalmanX.setAngle(roll);
  kalmanY.setAngle(pitch);
  gyroXangle = roll;
  gyroYangle = pitch;
  compAngleX = roll;
  compAngleY = pitch;
  yaw = 0;
  smoothedYaw = 0;

  timer = micros();
}

void loop() {
  // Чтение потенциометра для управления обоими двигателями
  int potValue = analogRead(POT_PIN); // 0–1023
  int pwm = map(potValue, 0, 1023, 0, 255); // Для ENA (ШИМ)
  int enb = map(potValue, 0, 1023, 0, 1);   // Для ENB (вкл/выкл)
  analogWrite(ENA_PIN, pwm);
  digitalWrite(ENB_PIN, enb * 255);

  // Чтение IMU
  I2Cdev::readBytes(0x68, 0x3B, 14, i2cData);
  accX = ((i2cData[0] << 8) | i2cData[1]);
  accY = ((i2cData[2] << 8) | i2cData[3]);
  accZ = ((i2cData[4] << 8) | i2cData[5]);
  tempRaw = (i2cData[6] << 8) | i2cData[7];
  gyroX = (i2cData[8] << 8) | i2cData[9];
  gyroY = (i2cData[10] << 8) | i2cData[11];
  gyroZ = (i2cData[12] << 8) | i2cData[13];

  double dt = (double)(micros() - timer) / 1000000;
  timer = micros();

#ifdef RESTRICT_PITCH
  double roll = atan2(accY, accZ) * RAD_TO_DEG;
  double pitch = atan(-accX / sqrt(accY * accY + accZ * accZ)) * RAD_TO_DEG;
#else
  double roll = atan(accY / sqrt(accX * accX + accZ * accZ)) * RAD_TO_DEG;
  double pitch = atan2(-accX, accZ) * RAD_TO_DEG;
#endif

  double gyroXrate = gyroX / 131.0;
  double gyroYrate = gyroY / 131.0;
  double gyroZrate = gyroZ / 131.0;

  yaw += gyroZrate * dt;
  if (yaw < -180 || yaw > 180) yaw = yaw - 360 * (yaw > 0 ? 1 : -1);

  // Сглаживание yaw
  smoothedYaw = 0.9 * smoothedYaw + 0.1 * yaw;

#ifdef RESTRICT_PITCH
  if ((roll < -90 && kalAngleX > 90) || (roll > 90 && kalAngleX < -90)) {
    kalmanX.setAngle(roll);
    compAngleX = roll;
    kalAngleX = roll;
    gyroXangle = roll;
  } else
    kalAngleX = kalmanX.getAngle(roll, gyroXrate, dt);

  if (abs(kalAngleX) > 90)
    gyroYrate = -gyroYrate;
  kalAngleY = kalmanY.getAngle(pitch, gyroYrate, dt);
#else
  if ((pitch < -90 && kalAngleY > 90) || (pitch > 90 && kalAngleY < -90)) {
    kalmanY.setAngle(pitch);
    compAngleY = pitch;
    kalAngleY = pitch;
    gyroYangle = pitch;
  } else
    kalAngleY = kalmanY.getAngle(pitch, gyroYrate, dt);

  if (abs(kalAngleY) > 90)
    gyroXrate = -gyroXrate;
  kalAngleX = kalmanX.getAngle(roll, gyroXrate, dt);
#endif

  gyroXangle += gyroXrate * dt;
  gyroYangle += gyroYrate * dt;

  compAngleX = 0.93 * (compAngleX + gyroXrate * dt) + 0.07 * roll;
  compAngleY = 0.93 * (compAngleY + gyroYrate * dt) + 0.07 * pitch;

  if (gyroXangle < -180 || gyroXangle > 180)
    gyroXangle = kalAngleX;
  if (gyroYangle < -180 || gyroYangle > 180)
    gyroYangle = kalAngleY;

  // Вывод данных
  Serial.print(kalAngleX); Serial.print("\t");
  Serial.print(kalAngleY); Serial.print("\t");
  Serial.print(yaw); Serial.print("\t");
  Serial.print("\r\n");

  // Управление двигателями
  int valuex = smoothedYaw; // yaw для stepper2
  int stepx = valuex - previousx;
  if (abs(stepx) > 10) stepx = stepx > 0 ? 10 : -10;
  stepper2.step(stepx);
  previousx += stepx;

  int valuey = kalAngleY; // pitch для stepper1
  int stepy = valuey - previousy;
  if (abs(stepy) > 10) stepy = stepy > 0 ? 10 : -10;
  stepper1.step(stepy);
  previousy += stepy;

  delay(2); // Задержка для стабилизации
}
