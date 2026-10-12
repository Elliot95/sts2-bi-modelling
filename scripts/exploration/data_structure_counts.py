import os
import json
import csv
from collections import defaultdict

# Paths
data_path = r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history"
output_path = r"C:\Users\1995e\OneDrive\Desktop\Downloads\STS2\key_values_counts.csv"

# Storage
key_values = {}
key_counts_per_run = defaultdict(list)

# Loop through files
for file in os.listdir(data_path):
    if file.endswith(".run"):
        with open(os.path.join(data_path, file)) as f:
            data = json.load(f)

        for key, value in data.items():
            # Track unique values
            if key not in key_values:
                key_values[key] = set()

            if isinstance(value, list):
                for v in value:
                    key_values[key].add(str(v))
                count = len(value)
            else:
                key_values[key].add(str(value))
                count = 1

            # Track count per run
            key_counts_per_run[key].append(count)

# Write CSV
with open(output_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["key", "values", "counts_per_run"])

    for key in key_values:
        writer.writerow([
            key,
            "; ".join(sorted(key_values[key])),
            ", ".join(map(str, key_counts_per_run[key]))
        ])

print("Done! File saved to:", output_path)