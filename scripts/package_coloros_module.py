#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


MODULE_ID = "installerx-coloros-packageinstaller"
EXPECTED_APP_ID = "com.android.packageinstaller"
UPDATE_BINARY = """#!/sbin/sh

#################
# Initialization
#################

umask 022

# echo before loading util_functions
ui_print() { echo "$1"; }

require_new_magisk() {
  ui_print "*******************************"
  ui_print " Please install Magisk v20.4+! "
  ui_print "*******************************"
  exit 1
}

#########################
# Load util_functions.sh
#########################

OUTFD=$2
ZIPFILE=$3

mount /data 2>/dev/null

[ -f /data/adb/magisk/util_functions.sh ] || require_new_magisk
. /data/adb/magisk/util_functions.sh
[ $MAGISK_VER_CODE -lt 20400 ] && require_new_magisk

install_module
exit 0
"""

CUSTOMIZE_TEMPLATE = """# This ensures Magisk extracts the module files automatically
SKIPUNZIP=0

# UI print command to show status in the flashing console
ui_print "- Installing PackageInstaller Replacement ({flavor})..."

# Define permissions
# Syntax: set_perm_recursive <directory> <owner> <group> <dir_permission> <file_permission>
# 0 0 corresponds to root:root
# 0755 is rwxr-xr-x (required for directories)
# 0644 is rw-r--r-- (required for system apks)

ui_print "- Setting permissions..."
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
"""


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def load_metadata(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        fail(f"metadata 格式异常: {path}")
    return data


def metadata_values(data: dict[str, Any]) -> tuple[str, str, int, str]:
    application_id = data.get("applicationId")
    elements = data.get("elements") or []
    if not application_id or not isinstance(elements, list) or not elements:
        fail("output-metadata.json 缺少 applicationId 或 elements。")

    element = elements[0]
    output_file = element.get("outputFile")
    version_name = element.get("versionName")
    version_code = element.get("versionCode")

    if not output_file or not version_name or version_code is None:
        fail("output-metadata.json 缺少 outputFile/versionName/versionCode。")

    try:
        parsed_version_code = int(version_code)
    except (TypeError, ValueError) as exc:
        fail(f"versionCode 不是有效整数: {version_code!r} ({exc})")

    return application_id, str(version_name), parsed_version_code, str(output_file)


def write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755 if executable else 0o644)


def write_module_prop(
    path: Path,
    flavor: str,
    version_name: str,
    version_code: int,
    author: str,
) -> None:
    content = "\n".join(
        [
            f"id={MODULE_ID}",
            f"name=InstallerX ColorOS PackageInstaller ({flavor})",
            f"version={version_name}",
            f"versionCode={version_code}",
            f"author={author}",
            (
                "description=ColorOS PackageInstaller replacement built from InstallerX Revived "
                f"({flavor}). Requires metamodule/meta-overlayfs. High risk: may cause bootloop or system instability."
            ),
            "",
        ]
    )
    write_text(path, content)


def extract_native_libs(apk_path: Path, package_dir: Path) -> bool:
    found = False
    with zipfile.ZipFile(apk_path) as apk:
        for member in sorted(apk.namelist()):
            if not member.startswith("lib/") or not member.endswith(".so"):
                continue
            found = True
            target = package_dir / member
            target.parent.mkdir(parents=True, exist_ok=True)
            with apk.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            target.chmod(0o644)
    return found


def zip_tree(root_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root_dir.rglob("*")):
            relative = path.relative_to(root_dir).as_posix()
            if path.is_dir():
                archive.write(path, relative + "/")
            else:
                archive.write(path, relative)


def write_outputs(path: str, outputs: dict[str, str]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="将 InstallerX APK 打包为 ColorOS 系统安装器模块。")
    parser.add_argument("--apk", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--flavor", choices=["online", "offline"], required=True)
    parser.add_argument("--upstream-tag", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--github-output", dest="github_output", default=None)
    args = parser.parse_args()

    apk_path = Path(args.apk).resolve()
    metadata_path = Path(args.metadata).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata(metadata_path)
    application_id, version_name, version_code, output_file = metadata_values(metadata)

    if application_id != EXPECTED_APP_ID:
        fail(
            f"metadata applicationId 校验失败: 期望 {EXPECTED_APP_ID!r}，实际为 {application_id!r}。"
        )
    if version_name != args.upstream_tag:
        fail(
            f"metadata versionName 校验失败: 期望 {args.upstream_tag!r}，实际为 {version_name!r}。"
        )
    if apk_path.name != output_file:
        fail(
            f"传入 APK 与 metadata outputFile 不一致: {apk_path.name!r} != {output_file!r}。"
        )

    raw_apk_name = f"InstallerX-ColorOS-{args.flavor}-{version_name}.apk"
    raw_apk_path = output_dir / raw_apk_name
    shutil.copy2(apk_path, raw_apk_path)

    module_zip_name = f"InstallerX-ColorOS-Module-{args.flavor}-{version_name}.zip"
    module_zip_path = output_dir / module_zip_name

    with tempfile.TemporaryDirectory(prefix=f"installerx-{args.flavor}-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        package_dir = temp_dir / "system/priv-app/PackageInstaller"
        (temp_dir / "META-INF/com/google/android").mkdir(parents=True, exist_ok=True)
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "oat").mkdir(parents=True, exist_ok=True)

        write_module_prop(
            temp_dir / "module.prop",
            flavor=args.flavor,
            version_name=version_name,
            version_code=version_code,
            author=args.author,
        )
        write_text(
            temp_dir / "customize.sh",
            CUSTOMIZE_TEMPLATE.format(flavor=args.flavor),
            executable=True,
        )
        write_text(
            temp_dir / "META-INF/com/google/android/update-binary",
            UPDATE_BINARY,
            executable=True,
        )
        write_text(temp_dir / "META-INF/com/google/android/updater-script", "#MAGISK\n")
        write_text(
            temp_dir / "action.sh",
            "#!/system/bin/sh\nrm -r /data/system/package_cache/*\n",
            executable=True,
        )
        write_text(
            temp_dir / "service.sh",
            "#!/system/bin/sh\nrm -r /data/system/package_cache/*\n",
            executable=True,
        )
        write_text(
            temp_dir / "uninstall.sh",
            "#!/system/bin/sh\nrm -r /data/system/package_cache/*\n",
            executable=True,
        )

        module_apk_path = package_dir / "PackageInstaller.apk"
        shutil.copy2(raw_apk_path, module_apk_path)
        module_apk_path.chmod(0o644)
        extract_native_libs(raw_apk_path, package_dir)

        zip_tree(temp_dir, module_zip_path)

    outputs = {
        f"{args.flavor}_raw_apk": str(raw_apk_path),
        f"{args.flavor}_module_zip": str(module_zip_path),
    }
    if args.github_output:
        write_outputs(args.github_output, outputs)
    print(json.dumps(outputs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
