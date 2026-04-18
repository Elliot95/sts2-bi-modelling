import os
import json
import pandas as pd
import datetime

print("🚀 Script is running...")

# 📂 SOURCE: where your .run files are
folder_path = r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history"

# 📂 OUTPUT: where your CSV will go
output_path = r"C:\Users\1995e\OneDrive\Desktop\Downloads\STS2\runs_analysis.csv"

# Create output folder if it doesn't exist
os.makedirs(os.path.dirname(output_path), exist_ok=True)

runs = []
failed_files = []

for filename in os.listdir(folder_path):
    if filename.endswith(".run"):
        file_path = os.path.join(folder_path, filename)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # 📅 Extract timestamp from filename
                timestamp = int(filename.replace(".run", ""))
                date = datetime.datetime.fromtimestamp(timestamp)

                # 🧠 Safe extraction from nested structure
                map_history = data.get("map_point_history", [])

                last_gold = None
                if map_history and isinstance(map_history[-1], list):
                    last_room = map_history[-1][-1] if map_history[-1] else {}
                    player_stats = last_room.get("player_stats", [])
                    if player_stats:
                        last_gold = player_stats[0].get("current_gold")

                runs.append({
                    "file": filename,
                    "date": date,
                    "ascension": data.get("ascension"),
                    "game_mode": data.get("game_mode"),
                    "killed_by": data.get("killed_by_encounter"),
                    "acts_completed": len(data.get("acts", [])),
                    "last_gold": last_gold
                })

        except Exception as e:
            print(f"❌ Failed to process {filename}: {e}")
            failed_files.append(filename)

# 📊 Convert to DataFrame
df = pd.DataFrame(runs)

# 💾 Save to CSV
df.to_csv(output_path, index=False)

# 📢 Output summary
print("✅ Done!")
print(f"Processed runs: {len(df)}")
print(f"Failed files: {len(failed_files)}")

print("\n📊 Sample data:")
print(df.head())

print("\n🏆 Runs by cause of death:")
print(df["killed_by"].value_counts())

print("\n📈 Avg acts completed:")
print(df["acts_completed"].mean())