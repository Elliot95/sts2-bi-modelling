import os
import json
import csv
from collections import defaultdict

data_path = r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history"
output_path = r"C:\Users\1995e\OneDrive\Desktop\Downloads\STS2\key_values_with_counts.csv"

key_values = {}
key_counts = defaultdict(int)
run_counts = defaultdict(int)

total_runs = 0

for file in os.listdir(data_path):
    if file.endswith(".run"):
        total_runs += 1

        with open(os.path.join(data_path, file)) as f:
            data = json.load(f)

        for key, value in data.items():
            if key not in key_values:
                key_values[key] = set()

            # Track values
            if isinstance(value, list):
                for v in value:
                    key_values[key].add(str(v))
                count = len(value)
            else:
                key_values[key].add(str(value))
                count = 1

            # Track total counts
            key_counts[key] += count
            run_counts[key] += 1  # appears in this run

# Write CSV
with open(output_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["key", "values", "avg_count_per_run"])

    for key in key_values:
        avg_count = key_counts[key] / run_counts[key]

        writer.writerow([
            key,
            "; ".join(sorted(key_values[key])),
            round(avg_count, 2)
        ])