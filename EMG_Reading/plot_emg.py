import csv
import os
import threading
import time
from collections import deque

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import serial

SERIAL_PORT = "/dev/cu.usbserial-0001"
BAUD_RATE = 115200

ACTIVE_SECONDS = 2.0
PLOT_HISTORY_SECONDS = 10.0
MAX_POINTS = 3000

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_CSV = os.path.join(OUTPUT_DIR, "emg_samples.csv")
TRIALS_CSV = os.path.join(OUTPUT_DIR, "emg_trials.csv")

samples = deque(maxlen=MAX_POINTS)
samples_lock = threading.Lock()
stop_event = threading.Event()
trial_lock = threading.Lock()

trial_counter = 0
current_trial = None
completed_trials = []
animation_handle = None


def ensure_csv_headers():
    if not os.path.exists(SAMPLES_CSV):
        with open(SAMPLES_CSV, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "host_time_s",
                    "device_time_ms",
                    "raw_value",
                    "filtered_value",
                    "triggered",
                    "trial_id",
                    "label",
                    "phase",
                ]
            )

    if not os.path.exists(TRIALS_CSV):
        with open(TRIALS_CSV, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "trial_id",
                    "label",
                    "prep_start_host_s",
                    "go_host_s",
                    "window_end_host_s",
                    "triggered",
                    "trigger_delay_ms",
                    "result",
                ]
            )

def detect_phase(now, trial):
    if trial is None:
        return "", ""

    if now <= trial["window_end"]:
        return "active", ""

    if trial["finalized"]:
        return "", ""

    return "post", "finalize"


def finalize_trial(trial):
    triggered = trial["triggered"]
    label = trial["label"]

    if label == 1:
        result = "TP" if triggered else "FN"
    else:
        result = "FP" if triggered else "TN"

    delay_ms = ""
    if label == 1 and trial["trigger_time"] is not None:
        delay_ms = round((trial["trigger_time"] - trial["go_time"]) * 1000, 1)

    record = {
        "trial_id": trial["id"],
        "label": label,
        "prep_start_host_s": round(trial["start_time"], 3),
        "go_host_s": round(trial["start_time"], 3),
        "window_end_host_s": round(trial["window_end"], 3),
        "triggered": int(triggered),
        "trigger_delay_ms": delay_ms,
        "result": result,
    }

    with open(TRIALS_CSV, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(record.values())

    trial["finalized"] = True
    completed_trials.append(record)
    print(
        f"Trial {trial['id']} finished: label={label}, "
        f"triggered={int(triggered)}, delay_ms={delay_ms}, result={result}"
    )


def classify_current_trial(now, triggered):
    global current_trial

    with trial_lock:
        phase = ""
        trial_id = ""
        label = ""
        action = ""

        if current_trial is not None:
            phase, action = detect_phase(now, current_trial)
            trial_id = current_trial["id"]
            label = current_trial["label"]

            if (
                phase == "active"
                and triggered
                and not current_trial["triggered"]
            ):
                current_trial["triggered"] = True
                current_trial["trigger_time"] = now

            if action == "finalize":
                finalize_trial(current_trial)
                current_trial = None
                phase = ""
                trial_id = ""
                label = ""

        return trial_id, label, phase


def append_sample_to_csv(sample):
    with open(SAMPLES_CSV, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                round(sample["host_time"], 4),
                sample["device_time_ms"],
                sample["raw_value"],
                round(sample["filtered_value"], 2),
                sample["triggered"],
                sample["trial_id"],
                sample["label"],
                sample["phase"],
            ]
        )


def read_serial(ser, session_start):
    while not stop_event.is_set():
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except serial.SerialException:
            break

        if not line or line.count(",") != 3:
            continue

        try:
            device_time_ms, raw_value, filtered_value, triggered = line.split(",")
            sample = {
                "host_time": time.time() - session_start,
                "device_time_ms": int(device_time_ms),
                "raw_value": int(raw_value),
                "filtered_value": float(filtered_value),
                "triggered": int(triggered),
            }
        except ValueError:
            continue

        sample["trial_id"], sample["label"], sample["phase"] = classify_current_trial(
            sample["host_time"], sample["triggered"]
        )

        with samples_lock:
            samples.append(sample)

        append_sample_to_csv(sample)


def start_trial(label):
    global current_trial, trial_counter

    with trial_lock:
        if current_trial is not None:
            print("A trial is already running. Wait for it to finish.")
            return

        trial_counter += 1
        now = time.time() - session_start_time
        current_trial = {
            "id": trial_counter,
            "label": label,
            "start_time": now,
            "go_time": now,
            "window_end": now + ACTIVE_SECONDS,
            "triggered": False,
            "trigger_time": None,
            "finalized": False,
        }

    action_text = "CONTRACT biceps" if label == 1 else "STAY RELAXED"
    print(f"Trial {trial_counter} started. {action_text} for {ACTIVE_SECONDS:.0f}s.")


def summarize_trials():
    if not completed_trials:
        return "No completed trials yet."

    tp = sum(1 for trial in completed_trials if trial["result"] == "TP")
    fn = sum(1 for trial in completed_trials if trial["result"] == "FN")
    fp = sum(1 for trial in completed_trials if trial["result"] == "FP")
    tn = sum(1 for trial in completed_trials if trial["result"] == "TN")
    total = tp + fn + fp + tn

    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    delays = [
        float(trial["trigger_delay_ms"])
        for trial in completed_trials
        if trial["result"] == "TP" and str(trial["trigger_delay_ms"]).strip() != ""
    ]
    avg_delay = round(sum(delays) / len(delays), 1) if delays else "N/A"

    return (
        f"Trials={total} | TP={tp} FP={fp} FN={fn} TN={tn} | "
        f"Accuracy={accuracy:.3f} Precision={precision:.3f} Recall={recall:.3f} | "
        f"Avg delay(ms)={avg_delay}"
    )


def key_handler(event):
    key = event.key.lower() if event.key else ""

    if key == "d":
        start_trial(label=1)
    elif key == "r":
        start_trial(label=0)
    elif key == "q":
        stop_event.set()
        plt.close(event.canvas.figure)


def animate(_frame):
    now = time.time() - session_start_time

    with trial_lock:
        trial = current_trial

    status_line = "Idle"
    if trial is not None:
        if now <= trial["window_end"]:
            remaining = trial["window_end"] - now
            action_text = "CONTRACT NOW" if trial["label"] == 1 else "STAY RELAXED"
            status_line = f"Trial {trial['id']}: {action_text}, {remaining:.1f}s left"
        else:
            status_line = f"Trial {trial['id']}: finalizing..."

    with samples_lock:
        recent_samples = list(samples)

    if recent_samples:
        latest_time = recent_samples[-1]["host_time"]
        min_time = max(0.0, latest_time - PLOT_HISTORY_SECONDS)
        visible_samples = [sample for sample in recent_samples if sample["host_time"] >= min_time]
        times = [sample["host_time"] for sample in visible_samples]
        raw_values = [sample["raw_value"] for sample in visible_samples]
        filtered_values = [sample["filtered_value"] for sample in visible_samples]
        trigger_values = [
            sample["filtered_value"] if sample["triggered"] else None
            for sample in visible_samples
        ]
    else:
        times = []
        raw_values = []
        filtered_values = []
        trigger_values = []

    plt.cla()
    plt.plot(times, raw_values, label="Raw EMG", alpha=0.4)
    plt.plot(times, filtered_values, label="Filtered EMG", linewidth=2)
    plt.scatter(times, trigger_values, label="Trigger", color="red", s=14)
    plt.xlabel("Host time (s)")
    plt.ylabel("EMG value")
    plt.title("EMG Trigger Experiment")
    plt.legend(loc="upper right")
    plt.grid(True, alpha=0.3)
    plt.figtext(
        0.02,
        0.02,
        "Keys: d=positive trial, r=negative trial, q=quit",
        fontsize=10,
    )
    plt.figtext(0.02, 0.95, status_line, fontsize=11)
    plt.figtext(0.02, 0.91, summarize_trials(), fontsize=10)


def main():
    global animation_handle, session_start_time

    ensure_csv_headers()
    session_start_time = time.time()

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.2)
        print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud")
        ser.write(b"START\n")
        print("Sent START command")

        thread = threading.Thread(
            target=read_serial,
            args=(ser, session_start_time),
            daemon=True,
        )
        thread.start()

        fig = plt.figure(figsize=(12, 6))
        fig.canvas.mpl_connect("key_press_event", key_handler)
        animation_handle = animation.FuncAnimation(
            fig,
            animate,
            interval=50,
            cache_frame_data=False,
        )
        plt.show()

        stop_event.set()
        ser.write(b"STOP\n")
        ser.close()

        print("Sent STOP command")
        print("Saved samples to:", SAMPLES_CSV)
        print("Saved trials to:", TRIALS_CSV)
        print(summarize_trials())

    except serial.SerialException as error:
        print(f"Serial error: {error}")
    except KeyboardInterrupt:
        print("Interrupted")


if __name__ == "__main__":
    main()
