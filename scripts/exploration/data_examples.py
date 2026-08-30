import os
import json
import csv

data_path = r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history"
output_path = r"C:\Users\1995e\OneDrive\Desktop\Downloads\STS2\structure_with_examples.csv"

def get_sample_value(value):
    if isinstance(value, dict):
        return "{...}"
    elif isinstance(value, list):
        return f"[{len(value)} items]"
    else:
        return str(value)

def explore(data, parent_key="", max_level=10, level=1, rows=None):
    if rows is None:
        rows = []

    if level > max_level:
        return rows

    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            sample = get_sample_value(value)
            rows.append([full_key, type(value).__name__, sample])
            explore(value, full_key, max_level, level + 1, rows)

    elif isinstance(data, list):
        if len(data) > 0:
            value = data[0]
            full_key = f"{parent_key}[]"
            sample = get_sample_value(value)
            rows.append([full_key, type(value).__name__, sample])
            explore(value, full_key, max_level, level + 1, rows)

    return rows


all_rows = []

for file in os.listdir(data_path):
    if file.endswith(".run"):
        with open(os.path.join(data_path, file)) as f:
            data = json.load(f)

        rows = explore(data)
        all_rows.extend(rows)
        break

# Remove duplicates
unique_rows = list(set(tuple(row) for row in all_rows))

# Write CSV
with open(output_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["key_path", "type", "example_value"])
    writer.writerows(sorted(unique_rows))

print("Done! File saved to:", output_path)