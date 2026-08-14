import json


def export_json(report_data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, default=str)
