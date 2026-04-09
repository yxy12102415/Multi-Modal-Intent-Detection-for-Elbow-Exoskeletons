#include <Arduino.h>

const int emgPin = 35;              // ENV 接 GPIO35
const int triggerThreshold = 2200;  // 触发阈值（根据实际调整）
const int releaseThreshold = 1800;  // 释放阈值，略低于触发阈值形成滞回

const float alpha = 0.1;            // 低通滤波系数 (0~1)
const int triggerFrames = 2;        // 连续多少帧超过阈值才算触发
const int releaseFrames = 3;        // 连续多少帧低于释放阈值才解除触发

float filteredEMG = 0;              // 滤波后的 EMG
bool reading = false;               // 控制是否读取的标志
bool triggeredState = false;        // 去抖后的触发状态
int aboveThresholdCount = 0;        // 连续高于阈值的采样计数
int belowThresholdCount = 0;        // 连续低于释放阈值的采样计数

void setup()
{
    Serial.begin(115200);
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
            triggeredState = false;
            aboveThresholdCount = 0;
            belowThresholdCount = 0;
            Serial.println("Reading started");
        }
        else if (command == "STOP")
        {
            reading = false;
            triggeredState = false;
            aboveThresholdCount = 0;
            belowThresholdCount = 0;
            Serial.println("Reading stopped");
        }
    }

    if (reading)
    {
        int rawValue = analogRead(emgPin);

        // 一阶低通滤波
        filteredEMG = alpha * rawValue + (1 - alpha) * filteredEMG;

        if (filteredEMG >= triggerThreshold)
        {
            aboveThresholdCount++;
            belowThresholdCount = 0;
        }
        else if (filteredEMG <= releaseThreshold)
        {
            belowThresholdCount++;
            aboveThresholdCount = 0;
        }
        else
        {
            // 位于滞回区间时维持当前状态，避免边界来回抖动
            aboveThresholdCount = 0;
            belowThresholdCount = 0;
        }

        if (!triggeredState && aboveThresholdCount >= triggerFrames)
        {
            triggeredState = true;
        }
        else if (triggeredState && belowThresholdCount >= releaseFrames)
        {
            triggeredState = false;
        }

        int triggered = triggeredState ? 1 : 0;

        // 发送带时间戳和触发状态的数据，方便上位机统计延迟和准确率
        Serial.print(millis());
        Serial.print(",");
        Serial.print(rawValue);
        Serial.print(",");
        Serial.print(filteredEMG, 2);
        Serial.print(",");
        Serial.println(triggered);

        delay(5);    // 约 200 Hz 采样
    }
}
