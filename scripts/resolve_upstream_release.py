#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


UPSTREAM_TAG_RE = re.compile(r"^(?P<base>\d{2}\.\d{2})\.(?P<hash>[0-9a-f]{7,})$")


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def github_get(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "InstallerX-ColorOS-PackageInstaller",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        fail(f"GitHub API 请求失败: {exc.code} {exc.reason}\n{body}")
    except urllib.error.URLError as exc:
        fail(f"GitHub API 请求失败: {exc}")


def ensure_prerelease_assets(release: dict[str, Any]) -> None:
    assets = release.get("assets") or []
    if not assets:
        fail("上游 release 没有 assets，按约定直接失败。")

    asset_names = [asset.get("name", "") for asset in assets]
    has_online = any(name.endswith(".apk") and "-online-" in name for name in asset_names)
    has_offline = any(name.endswith(".apk") and "-offline-" in name for name in asset_names)
    if not has_online or not has_offline:
        fail("上游 prerelease assets 不完整，未同时找到 online/offline APK。")


def pick_release(repo: str, tag: str | None) -> dict[str, Any]:
    if tag:
        encoded_tag = urllib.parse.quote(tag, safe="")
        release = github_get(f"https://api.github.com/repos/{repo}/releases/tags/{encoded_tag}")
        if not release.get("prerelease"):
            fail(f"指定 tag {tag} 不是 prerelease，按约定直接失败。")
        ensure_prerelease_assets(release)
        return release

    releases = github_get(f"https://api.github.com/repos/{repo}/releases?per_page=20")
    if not isinstance(releases, list):
        fail("GitHub API 返回格式异常，未拿到 releases 列表。")

    for release in releases:
        if release.get("prerelease"):
            ensure_prerelease_assets(release)
            return release

    fail("未找到可用的 upstream prerelease release。")


def release_to_outputs(release: dict[str, Any]) -> dict[str, str]:
    tag_name = release.get("tag_name") or ""
    target_commitish = release.get("target_commitish") or ""
    release_name = release.get("name") or ""
    html_url = release.get("html_url") or ""

    if not tag_name:
        fail("上游 release 缺少 tag_name。")
    if not target_commitish:
        fail("上游 release 缺少 target_commitish。")

    match = UPSTREAM_TAG_RE.fullmatch(tag_name)
    if not match:
        fail(
            "上游 prerelease tag 格式不符合预期，"
            f"当前拿到的是 {tag_name!r}，期望类似 '26.03.4d16c34'。"
        )

    return {
        "tag_name": tag_name,
        "target_commitish": target_commitish,
        "base_version": match.group("base"),
        "short_hash": match.group("hash"),
        "release_name": release_name,
        "html_url": html_url,
    }


def write_github_output(path: str, outputs: dict[str, str]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="解析 InstallerX-Revived 上游 prerelease 信息。")
    parser.add_argument("--repo", default="wxxsfxyzm/InstallerX-Revived")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--github-output", dest="github_output", default=None)
    args = parser.parse_args()

    release = pick_release(args.repo, args.tag)
    outputs = release_to_outputs(release)
    print(json.dumps(outputs, indent=2, ensure_ascii=False))

    if args.github_output:
        write_github_output(args.github_output, outputs)


if __name__ == "__main__":
    main()
