import json

with open("/app/data/studio.json") as f:
    data = json.load(f)

for p in data["projects"]:
    if p["id"] == "fa2c3f706184":
        e = p["episodes"][0]
        # Write raw_text
        with open("/app/data/out_raw.txt", "w") as f:
            f.write(e.get("raw_text", ""))
        # Write dialogues as JSON
        with open("/app/data/out_dialogues.json", "w") as f:
            json.dump(e.get("dialogues", []), f, ensure_ascii=False, indent=2)
        print("OK")
        break
