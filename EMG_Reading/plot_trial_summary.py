import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRIALS_CSV = os.path.join(OUTPUT_DIR, "emg_trials.csv")
SUMMARY_PNG = os.path.join(OUTPUT_DIR, "emg_trial_summary.png")


def load_trials():
    trials = []
    with open(TRIALS_CSV, "r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            trials.append(row)
    return trials


def compute_metrics(trials):
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}

    for trial in trials:
        result = trial.get("result", "").strip()
        if result in counts:
            counts[result] += 1

    tp = counts["TP"]
    fp = counts["FP"]
    fn = counts["FN"]
    tn = counts["TN"]
    total = tp + fp + fn + tn

    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0

    delays = []
    for trial in trials:
        if trial.get("result") == "TP":
            delay = trial.get("trigger_delay_ms", "").strip()
            if delay:
                delays.append(float(delay))

    avg_delay = sum(delays) / len(delays) if delays else None

    return counts, {
        "total": total,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "avg_delay": avg_delay,
    }


def draw_summary(counts, metrics):
    fig, ax = plt.subplots(figsize=(7, 6))

    matrix = [
        [counts["TP"], counts["FN"]],
        [counts["FP"], counts["TN"]],
    ]
    labels = [
        ["TP", "FN"],
        ["FP", "TN"],
    ]

    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks([0, 1], labels=["Triggered", "Not Triggered"])
    ax.set_yticks([0, 1], labels=["Positive", "Negative"])
    ax.set_xlabel("System output")
    ax.set_ylabel("Ground truth")
    ax.set_title("EMG Trigger Confusion Matrix")

    max_value = max(max(row) for row in matrix) if matrix else 0
    threshold = max_value / 2 if max_value else 0

    for row_index in range(2):
        for col_index in range(2):
            value = matrix[row_index][col_index]
            text_color = "white" if value > threshold else "black"
            ax.text(
                col_index,
                row_index,
                f"{labels[row_index][col_index]}\n{value}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=16,
                fontweight="bold",
            )

    fig.tight_layout()
    fig.savefig(SUMMARY_PNG, dpi=200, bbox_inches="tight")


def main():
    if not os.path.exists(TRIALS_CSV):
        raise FileNotFoundError(f"Missing file: {TRIALS_CSV}")

    trials = load_trials()
    counts, metrics = compute_metrics(trials)
    draw_summary(counts, metrics)

    avg_delay = metrics["avg_delay"]
    avg_delay_text = f"{avg_delay:.1f} ms" if avg_delay is not None else "N/A"
    print(
        f"TP={counts['TP']} FP={counts['FP']} FN={counts['FN']} TN={counts['TN']} | "
        f"Accuracy={metrics['accuracy']:.3f} Precision={metrics['precision']:.3f} "
        f"Recall={metrics['recall']:.3f} Specificity={metrics['specificity']:.3f} | "
        f"Avg TP delay={avg_delay_text}"
    )
    print(f"Saved summary chart to: {SUMMARY_PNG}")


if __name__ == "__main__":
    main()
