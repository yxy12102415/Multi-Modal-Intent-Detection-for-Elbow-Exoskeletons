#include <Arduino.h>
#include <Dynamixel2Arduino.h>

// =========================
// Dynamixel pins
// =========================
#define DXL_RX_PIN 2
#define DXL_TX_PIN 4
#define DXL_DIR_PIN 18
#define DXL_SERIAL Serial2

// =========================
// EMG pin
// =========================
#define EMG_PIN 34   // MyoWare ENV -> P34

// =========================
// Dynamixel config
// =========================
const uint8_t DXL_ID = 1;
Dynamixel2Arduino dxl(DXL_SERIAL, DXL_DIR_PIN);

// =========================
// Constants
// =========================
const float TICK_TO_DEG = 360.0f / 4096.0f;
const unsigned long SAMPLE_INTERVAL_MS = 20;   // 50 Hz
const float EMG_ALPHA = 0.10f;                 // EMA滤波系数，越大越灵敏

// =========================
// Recording state
// =========================
bool isRecording = false;
bool firstSample = true;

unsigned long sessionStartTime = 0;
unsigned long lastSampleTime = 0;
unsigned long lastCalcTime = 0;

int32_t lastPos = 0;
float emgFiltered = 0.0f;

// =========================
// Helper functions
// =========================
void startRecording() {
  isRecording = true;
  firstSample = true;

  sessionStartTime = millis();
  lastSampleTime = sessionStartTime;
  lastCalcTime = sessionStartTime;

  int32_t pos = dxl.getPresentPosition(DXL_ID);
  if (pos == -1) {
    lastPos = 0;
  } else {
    lastPos = pos;
  }

  int emgRaw = analogRead(EMG_PIN);
  emgFiltered = (float)emgRaw;

  Serial.println("time_ms,angle_deg,velocity_deg_s,emg_raw,emg_filtered");
}

void stopRecording() {
  isRecording = false;
  Serial.println("# Recording stopped");
}

float computeAngleDeg(int32_t pos) {
  int32_t wrapped = pos % 4096;
  if (wrapped < 0) wrapped += 4096;
  return wrapped * TICK_TO_DEG;
}

float computeVelocityDegS(int32_t currentPos, int32_t previousPos, unsigned long dtMs) {
  if (dtMs == 0) return 0.0f;

  int32_t deltaPos = currentPos - previousPos;

  // 处理编码器回绕
  if (deltaPos > 2048) deltaPos -= 4096;
  if (deltaPos < -2048) deltaPos += 4096;

  float dt = dtMs / 1000.0f;
  return (deltaPos * TICK_TO_DEG) / dt;
}

// =========================
// Setup
// =========================
void setup() {
  Serial.begin(115200);
  delay(1000);

  // EMG ADC setup
  analogReadResolution(12); // 0~4095

  // Dynamixel setup
  DXL_SERIAL.begin(57600, SERIAL_8N1, DXL_RX_PIN, DXL_TX_PIN);
  dxl.begin(57600);
  dxl.setPortProtocolVersion(2.0);

  dxl.reboot(DXL_ID);
  delay(1000);
  dxl.torqueOff(DXL_ID);

  Serial.println(">>> Multimodal Recorder Ready <<<");
  Serial.println("Commands:");
  Serial.println("  d = start recording");
  Serial.println("  f = stop recording");
}

// =========================
// Main loop
// =========================
void loop() {
  // 串口命令
  while (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == 'd' || cmd == 'D') {
      startRecording();
    } else if (cmd == 'f' || cmd == 'F') {
      stopRecording();
    }
  }

  if (!isRecording) {
    delay(5);
    return;
  }

  unsigned long now = millis();
  if (now - lastSampleTime < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleTime = now;

  // ========= Read motor position =========
  int32_t currentPos = dxl.getPresentPosition(DXL_ID);
  if (currentPos == -1) {
    return;
  }

  // ========= Compute angle =========
  float angleDeg = computeAngleDeg(currentPos);

  // ========= Compute velocity =========
  unsigned long dtMs = now - lastCalcTime;
  float velocityDegS = 0.0f;

  if (!firstSample) {
    velocityDegS = computeVelocityDegS(currentPos, lastPos, dtMs);
  }

  // ========= Read EMG =========
  int emgRaw = analogRead(EMG_PIN);
  emgFiltered = EMG_ALPHA * emgRaw + (1.0f - EMG_ALPHA) * emgFiltered;

  // ========= Output CSV =========
  Serial.print(now - sessionStartTime);
  Serial.print(",");
  Serial.print(angleDeg, 2);
  Serial.print(",");
  Serial.print(velocityDegS, 2);
  Serial.print(",");
  Serial.print(emgRaw);
  Serial.print(",");
  Serial.println(emgFiltered, 2);

  // ========= Update state =========
  lastPos = currentPos;
  lastCalcTime = now;
  firstSample = false;
}