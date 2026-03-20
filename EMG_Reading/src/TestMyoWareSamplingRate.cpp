#include <Arduino.h>

const int emgPin = 35;        // ENV 接 GPIO34
const int threshold = 1200;   // 触发阈值（根据实际调整）

float filteredEMG = 0;        // 滤波后的 EMG
const float alpha = 0.1;      // 低通滤波系数 (0~1)

bool reading = false;         // 控制是否读取的标志

void setup()
{
    Serial.begin(9600);
    delay(1000);
    Serial.println("EMG Trigger System Ready");
}

void loop()
{
    if (Serial.available() > 0)
    {
        String command = Serial.readStringUntil('\n');
        command.trim();
        if (command == "START")
        {
            reading = true;
            Serial.println("Reading started");
        }
        else if (command == "STOPs")
        {
            reading = false;
            Serial.println("Reading stopped");
        }
    }

    if (reading)
    {
        int rawValue = analogRead(emgPin);

        // 一阶低通滤波
        filteredEMG = alpha * rawValue + (1 - alpha) * filteredEMG;

        // 发送数据到串口
        Serial.print(rawValue);
        Serial.print(",");
        Serial.println(filteredEMG);

        delay(10);   // 100 Hz 采样
    }
}