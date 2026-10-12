import os
import json
import csv

data_path = r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history"
output_path = r"C:\Users\1995e\OneDrive\Desktop\Downloads\STS2\structure.csv"

with open(output_path, "w", newline="") as out_file:
    writer = csv.writer(out_file)
    
    writer.writerow(["file", "key", "type"])

    for file in os.listdir(data_path):
        if file.endswith(".run"):
            with open(os.path.join(data_path, file)) as f:
                data = json.load(f)

            for key, value in data.items():
                writer.writerow([file, key, type(value).__name__])