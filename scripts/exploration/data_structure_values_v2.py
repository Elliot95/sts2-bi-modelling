import os
import json
import csv

data_path = r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history"
output_path = r"C:\Users\1995e\OneDrive\Desktop\Downloads\STS2\structure_3_levels.csv"

def explore(data, parent_key="", level=1, max_level=3, rows=None):
    if rows is None:
        rows = []

    if level > max_level:
        return rows

    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            rows.append([full_key, type(value).__name__, level])
            explore(value, full_key, level + 1, max_level, rows)

    elif isinstance(data, list):
        # Look at first item only (structure should be consistent)
        if len(data) > 0:
            value = data[0]
            full_key = f"{parent_key}[]"
            rows.append([full_key, type(value).__name__, level])
            explore(value, full_key, level + 1, max_level, rows)

    return rows


all_rows = []

for file in os.listdir(data_path):
    if file.endswith(".run"):
        with open(os.path.join(data_path, file)) as f:
            data = json.load(f)

        rows = explore(data)
        all_rows.extend(rows)
        break  # only need ONE file for structure

# Remove duplicates
unique_rows = list(set(tuple(row) for row in all_rows))

# Write CSV
with open(output_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["key_path", "type", "level"])
    writer.writerows(sorted(unique_rows))

print("Done! Structure saved to:", output_path)