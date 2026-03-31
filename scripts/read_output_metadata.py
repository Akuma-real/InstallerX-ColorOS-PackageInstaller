#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="读取 Android output-metadata.json 中的常用字段。")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--field", choices=["applicationId", "outputFile", "versionCode", "versionName"], required=True)
    args = parser.parse_args()

    metadata_path = Path(args.metadata)
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"metadata 格式异常: {metadata_path}")

    if args.field == "applicationId":
        value = data.get("applicationId")
    else:
        elements = data.get("elements") or []
        if not elements:
            fail(f"metadata 缺少 elements: {metadata_path}")
        value = elements[0].get(args.field)

    if value is None:
        fail(f"metadata 缺少字段 {args.field}: {metadata_path}")

    print(value)


if __name__ == "__main__":
    main()

