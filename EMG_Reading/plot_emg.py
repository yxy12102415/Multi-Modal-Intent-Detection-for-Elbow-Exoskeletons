import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import threading

# 配置串口 (根据你的系统调整端口)
SERIAL_PORT = '/dev/tty.usbserial-0001'  # macOS 示例，Windows 如 'COM3'
BAUD_RATE = 9600

# 数据存储
raw_data = []
filtered_data = []
time_data = []

start_time = time.time()

def read_serial(ser):
    global raw_data, filtered_data, time_data
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            if ',' in line:
                try:
                    raw, filtered = map(float, line.split(','))
                    current_time = time.time() - start_time
                    raw_data.append(raw)
                    filtered_data.append(filtered)
                    time_data.append(current_time)
                except ValueError:
                    pass

def animate(i):
    plt.cla()
    plt.plot(time_data, raw_data, label='Raw EMG')
    plt.plot(time_data, filtered_data, label='Filtered EMG')
    plt.xlabel('Time (s)')
    plt.ylabel('EMG Value')
    plt.title('EMG Signal')
    plt.legend()
    plt.grid(True)

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("Connected to serial port")

        # 发送开始指令
        ser.write(b'START\n')
        print("Sent START command")

        # 启动读取线程
        thread = threading.Thread(target=read_serial, args=(ser,))
        thread.daemon = True
        thread.start()

        # 设置matplotlib
        fig = plt.figure()
        ani = animation.FuncAnimation(fig, animate, interval=20)  # 每20ms更新

        plt.savefig('/Users/milesye/Desktop/EMG_Reading/emg_plot.png')
        plt.show()

        # 等待用户输入停止
        input("Press Enter to stop...")

        # 发送停止指令
        ser.write(b'STOP\n')
        print("Sent STOP command")

        ser.close()
        print("Disconnected")

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("Interrupted")

if __name__ == "__main__":
    main()