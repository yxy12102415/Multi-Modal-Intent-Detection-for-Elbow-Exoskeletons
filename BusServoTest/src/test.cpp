#include <Arduino.h>
#include <Dynamixel2Arduino.h>

// 硬件引脚定义
#define DXL_RX_PIN 2    
#define DXL_TX_PIN 4    
#define DXL_DIR_PIN 18  
#define DXL_SERIAL Serial2

const uint8_t DXL_ID = 1; 
Dynamixel2Arduino dxl(DXL_SERIAL, DXL_DIR_PIN);

// 物理量转换与阈值
const float TICK_TO_DEG = 360.0 / 4096.0; 
const float VELOCITY_THRESHOLD = 30.0; 

// 状态控制变量
bool isRecording = false;
bool thresholdReached = false;
unsigned long sessionStartTime = 0;
unsigned long timeToReachThreshold = 0;
int32_t last_pos = 0;
unsigned long last_time = 0;

void setup() {
  Serial.begin(115200);
  
  // 电机通讯初始化
  DXL_SERIAL.begin(57600, SERIAL_8N1, DXL_RX_PIN, DXL_TX_PIN);
  dxl.begin(57600);
  dxl.setPortProtocolVersion(2.0);

  // 释放扭矩以便手动拨动
  dxl.reboot(DXL_ID);
  delay(1000); 
  dxl.torqueOff(DXL_ID);

  Serial.println(">>> System Ready <<<");
  Serial.println("Type 'd' to START recording CSV");
  Serial.println("Type 'f' to STOP and see summary");
}

void loop() {
  // 检查键盘指令
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == 'd' || cmd == 'D') {
      isRecording = true;
      thresholdReached = false;
      sessionStartTime = millis();
      timeToReachThreshold = 0;
      // 打印 CSV 表头，Excel 会自动识别
      Serial.println("\nTime_ms,Angle_deg,Velocity_degs,Threshold_Met");
    } 
    else if (cmd == 'f' || cmd == 'F') {
      isRecording = false;
      Serial.println("\n--- Recording Finished ---");
      if (thresholdReached) {
        Serial.print("Response Time to 30 deg/s: ");
        Serial.print(timeToReachThreshold);
        Serial.println(" ms");
      } else {
        Serial.println("Target threshold was not reached.");
      }
    }
  }

  // 测量逻辑
  if (isRecording) {
    unsigned long current_time = millis();
    int32_t current_pos = dxl.getPresentPosition(DXL_ID);

    if (current_pos != -1) {
      // 1. 计算角度
      float angle = (current_pos % 4096) * TICK_TO_DEG;

      // 2. 计算速度
      float delta_time = (float)(current_time - last_time) / 1000.0; 
      int32_t delta_pos = current_pos - last_pos;
      if (delta_pos > 2048) delta_pos -= 4096;
      if (delta_pos < -2048) delta_pos += 4096;

      float calc_vel = 0;
      if (delta_time > 0) {
        calc_vel = abs((delta_pos * TICK_TO_DEG) / delta_time);
      }

      // 3. 响应时间检测
      if (!thresholdReached && calc_vel >= VELOCITY_THRESHOLD) {
        thresholdReached = true;
        timeToReachThreshold = current_time - sessionStartTime;
      }

      // 4. 标准 CSV 输出
      Serial.print(current_time - sessionStartTime); // 时间戳
      Serial.print(",");
      Serial.print(angle, 2);
      Serial.print(",");
      Serial.print(calc_vel, 2);
      Serial.print(",");
      Serial.println(thresholdReached ? "1" : "0"); // 1表示已达标，0表示未达标

      // 更新历史记录
      last_pos = current_pos;
      last_time = current_time;
    }
  }
  
  delay(20); // 50Hzd
}