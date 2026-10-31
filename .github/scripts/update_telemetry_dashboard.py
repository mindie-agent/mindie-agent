#!/usr/bin/env python3
"""MindIE Agent org-wide GitHub telemetry collector and SVG/Markdown dashboard generator.

[Role]
Collects repository metadata (Stars, Forks), 14-day Git traffic (Clones, Views), and
permanent Release asset download counts across the @mindie-agent GitHub organization,
merges daily time-series into a cumulative JSON ledger, and renders bilingual SVG
dashboards (dashboard.zh.svg, dashboard.en.svg) plus a detailed Markdown report.

[Invariants]
- Daily traffic records in telemetry-history.json are keyed by ISO date (YYYY-MM-DD)
  and monotonically updated via max(existing, latest) so historical counts beyond
  GitHub's 14-day retention window are permanently preserved.
- Release package downloads exclude checksum/benchmark metadata files (*SHA256SUMS,
  benchmark-*) from the primary package counter while tracking total asset downloads.
- All XML/SVG text interpolations are strictly HTML-escaped to guarantee valid SVG 1.1.

[Timeouts & Locks]
- Each GitHub REST API request enforces a bounded 15-second HTTP timeout.
- Total script execution across 21 repositories completes within < 90 seconds.

[Side-Effect Policy]
- Read-only against GitHub REST APIs; writes output artifacts strictly into the
  caller-specified --output-dir without mutating the active git branch directly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import html
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ORG = "mindie-agent"
HTTP_TIMEOUT_SECONDS = 15
DEFAULT_CHANNEL_PATH = Path(__file__).resolve().parents[2] / "channels" / "0.1.json"

CORE_REPOS: list[tuple[str, str, str, str]] = [
    # (repo, category_zh, category_en, badge_color)
    ("mindie-agent", "产品入口", "Main Entry", "#7045F5"),
    ("awesome-mindie-skills", "技能目录", "Skills Hub", "#0F766E"),
    ("mindie-agent-codex", "客户端插件", "Client Plugin", "#10A37F"),
    ("mindie-agent-cc", "客户端插件", "Client Plugin", "#D97757"),
    ("mindie-agent-kimi", "客户端插件", "Client Plugin", "#2563EB"),
    ("mindie-agent-dsh", "客户端插件", "Client Plugin", "#0EA5E9"),
    ("mindie-agent-agy", "客户端插件", "Client Plugin", "#4285F4"),
    ("knowledge", "运行时组件", "Core Runtime", "#475569"),
    ("remote-dev", "运行时组件", "Core Runtime", "#475569"),
    ("coordinator", "运行时组件", "Core Runtime", "#475569"),
    ("profiler", "运行时组件", "Core Runtime", "#475569"),
    ("sim", "运行时组件", "Core Runtime", "#475569"),
    ("npu-top", "NPU 监控", "Observability", "#D97706"),
    ("diagnostics", "运行时组件", "Core Runtime", "#475569"),
    ("mindie-bench", "评测工具", "Benchmark", "#64748B"),
    ("knowledge-vllm-ascend", "领域知识库", "Knowledge Repo", "#0D9488"),
    ("knowledge-operators", "领域知识库", "Knowledge Repo", "#0D9488"),
    ("knowledge-infer-core", "领域知识库", "Knowledge Repo", "#0D9488"),
    ("knowledge-infer-distributed", "领域知识库", "Knowledge Repo", "#0D9488"),
    ("knowledge-infer-observability", "领域知识库", "Knowledge Repo", "#0D9488"),
    ("knowledge-infer-ops-compat", "领域知识库", "Knowledge Repo", "#0D9488"),
    ("knowledge-agent-engineering", "领域知识库", "Knowledge Repo", "#0D9488"),
]

PLUGIN_REPOS: list[tuple[str, str, str]] = [
    ("mindie-agent-codex", "OpenAI Codex", "#10A37F"),
    ("mindie-agent-cc", "Claude Code", "#D97757"),
    ("mindie-agent-kimi", "Kimi Code", "#2563EB"),
    ("mindie-agent-dsh", "DeepSeek Harness", "#0EA5E9"),
    ("mindie-agent-agy", "Google Antigravity", "#4285F4"),
]


def github_get(path: str, token: str) -> object:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mindie-agent-telemetry-dashboard",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API HTTP {exc.code} on {path}: {body}") from exc


def is_auxiliary_asset(name: str) -> bool:
    return (
        name.endswith("SHA256SUMS")
        or name.startswith("benchmark-")
        or name == "product-release-provenance.json"
    )


def format_release_tag(tag: str) -> str:
    if tag.startswith("knowledge-v") and len(tag) > 18:
        return tag[:18]
    if len(tag) > 16:
        return tag[:15] + "…"
    return tag


def load_history(history_path: Path) -> dict:
    if not history_path.is_file():
        return {"schema_version": 1, "org": ORG, "repositories": {}}
    return json.loads(history_path.read_text(encoding="utf-8"))


def merge_daily_series(
    existing_days: dict[str, dict[str, int]],
    api_items: list[dict],
) -> dict[str, dict[str, int]]:
    merged = dict(existing_days)
    for item in api_items:
        day = item["timestamp"][:10]
        count = int(item.get("count", 0))
        uniques = int(item.get("uniques", 0))
        prev = merged.get(day, {"count": 0, "uniques": 0})
        merged[day] = {
            "count": max(int(prev.get("count", 0)), count),
            "uniques": max(int(prev.get("uniques", 0)), uniques),
        }
    return dict(sorted(merged.items()))


def load_channel_pins(channel_path: Path) -> dict[str, str]:
    if not channel_path.is_file():
        return {}
    data = json.loads(channel_path.read_text(encoding="utf-8"))
    pins: dict[str, str] = {}
    patch_ver = data.get("current_patch_version")
    if patch_ver:
        pins["mindie-agent"] = f"v{patch_ver}"
    for name, comp in data.get("components", {}).items():
        tag = comp.get("tag") or (f"v{comp['version']}" if comp.get("version") else "")
        if tag:
            pins[name] = str(tag)
    for name, corp in data.get("corpora", {}).items():
        commit = str(corp.get("commit") or "")
        if commit:
            pins[name] = f"commit@{commit[:8]}"
    return pins


def resolve_repo_version(repo: str, releases: list, channel_pins: dict[str, str], token: str) -> str:
    # Domain knowledge corpora are pinned by commit in channels/0.1.json and do not cut software releases.
    if repo.startswith("knowledge-") and repo in channel_pins:
        return channel_pins[repo]
    if releases:
        tag = str(releases[0].get("tag_name") or "").strip()
        if tag:
            return tag
    if repo in channel_pins:
        return channel_pins[repo]
    tags = github_get(f"/repos/{ORG}/{repo}/tags?per_page=1", token)
    if isinstance(tags, list) and tags:
        tag_name = str(tags[0].get("name") or "").strip()
        if tag_name:
            return tag_name
    head = github_get(f"/repos/{ORG}/{repo}/commits/HEAD", token)
    if isinstance(head, dict) and head.get("sha"):
        return f"commit@{str(head['sha'])[:8]}"
    return "-"


def collect_org_telemetry(token: str, history: dict, channel_pins: dict[str, str]) -> tuple[dict, list[dict]]:
    repos_meta = history.setdefault("repositories", {})
    rows: list[dict] = []

    for repo, cat_zh, cat_en, badge_color in CORE_REPOS:
        info = github_get(f"/repos/{ORG}/{repo}", token)
        assert isinstance(info, dict)
        clones_data = github_get(f"/repos/{ORG}/{repo}/traffic/clones", token)
        assert isinstance(clones_data, dict)
        views_data = github_get(f"/repos/{ORG}/{repo}/traffic/views", token)
        assert isinstance(views_data, dict)
        releases = github_get(f"/repos/{ORG}/{repo}/releases?per_page=100", token)
        assert isinstance(releases, list)

        repo_hist = repos_meta.setdefault(repo, {"daily_clones": {}, "daily_views": {}})
        repo_hist["daily_clones"] = merge_daily_series(
            repo_hist.get("daily_clones", {}),
            clones_data.get("clones", []),
        )
        repo_hist["daily_views"] = merge_daily_series(
            repo_hist.get("daily_views", {}),
            views_data.get("views", []),
        )

        cum_clones = sum(d["count"] for d in repo_hist["daily_clones"].values())
        cum_clone_uniques = sum(d["uniques"] for d in repo_hist["daily_clones"].values())
        cum_views = sum(d["count"] for d in repo_hist["daily_views"].values())
        cum_view_uniques = sum(d["uniques"] for d in repo_hist["daily_views"].values())

        clones_14d = int(clones_data.get("count", 0))
        clones_14d_uniq = int(clones_data.get("uniques", 0))
        views_14d = int(views_data.get("count", 0))
        views_14d_uniq = int(views_data.get("uniques", 0))

        cum_clones = max(cum_clones, clones_14d)
        cum_clone_uniques = max(cum_clone_uniques, clones_14d_uniq)
        cum_views = max(cum_views, views_14d)
        cum_view_uniques = max(cum_view_uniques, views_14d_uniq)

        pkg_dl = 0
        all_asset_dl = 0
        latest_tag = resolve_repo_version(repo, releases, channel_pins, token)
        for rel in releases:
            for asset in rel.get("assets", []):
                dc = int(asset.get("download_count", 0))
                all_asset_dl += dc
                if not is_auxiliary_asset(str(asset.get("name", ""))):
                    pkg_dl += dc

        stars = int(info.get("stargazers_count", 0))
        forks = int(info.get("forks_count", 0))
        repo_hist["latest_snapshot"] = {
            "stars": stars,
            "forks": forks,
            "clones_14d": clones_14d,
            "clones_14d_uniques": clones_14d_uniq,
            "cumulative_clones": cum_clones,
            "cumulative_clone_uniques": cum_clone_uniques,
            "views_14d": views_14d,
            "views_14d_uniques": views_14d_uniq,
            "cumulative_views": cum_views,
            "pkg_downloads": pkg_dl,
            "all_asset_downloads": all_asset_dl,
            "latest_release": latest_tag,
        }

        rows.append(
            {
                "repo": repo,
                "cat_zh": cat_zh,
                "cat_en": cat_en,
                "badge_color": badge_color,
                "stars": stars,
                "forks": forks,
                "clones_14d": clones_14d,
                "clones_14d_uniq": clones_14d_uniq,
                "cum_clones": cum_clones,
                "cum_clone_uniq": cum_clone_uniques,
                "views_14d": views_14d,
                "views_14d_uniq": views_14d_uniq,
                "cum_views": cum_views,
                "pkg_dl": pkg_dl,
                "all_asset_dl": all_asset_dl,
                "latest_tag": latest_tag,
            }
        )

    return history, rows


def fmt_num(n: int) -> str:
    return f"{n:,}"


def render_svg(rows: list[dict], updated_at_cst: str, lang: str) -> str:
    is_zh = lang == "zh"
    by_repo = {r["repo"]: r for r in rows}
    main_row = by_repo["mindie-agent"]

    total_stars = sum(r["stars"] for r in rows)
    total_forks = sum(r["forks"] for r in rows)
    total_14d_clones = sum(r["clones_14d"] for r in rows)
    total_cum_clones = sum(r["cum_clones"] for r in rows)
    total_pkg_dl = sum(r["pkg_dl"] for r in rows)
    total_all_dl = sum(r["all_asset_dl"] for r in rows)

    plugin_cum_clones = sum(by_repo[p[0]]["cum_clones"] for p in PLUGIN_REPOS)
    plugin_14d_uniq = sum(by_repo[p[0]]["clones_14d_uniq"] for p in PLUGIN_REPOS)

    title = (
        "MindIE Agent 开源仓库与下载统计"
        if is_zh
        else "MindIE Agent Repository & Download Statistics"
    )
    sync_badge = (
        f"每 12 小时自动更新 · {updated_at_cst} (UTC+8)"
        if is_zh
        else f"Updated every 12h · {updated_at_cst} (UTC+8)"
    )

    kpis = [
        (
            "Stars / Forks",
            f"{fmt_num(main_row['stars'])} ★  ·  {fmt_num(main_row['forks'])} ⑂",
            f"全组织合计 {fmt_num(total_stars)} Stars · {fmt_num(total_forks)} Forks"
            if is_zh
            else f"Org total: {fmt_num(total_stars)} Stars · {fmt_num(total_forks)} Forks",
            "#7045F5",
        ),
        (
            "客户端插件 Clone" if is_zh else "Client Plugin Clones",
            fmt_num(plugin_cum_clones),
            f"近 14 天 {fmt_num(plugin_14d_uniq)} 个独立环境"
            if is_zh
            else f"{fmt_num(plugin_14d_uniq)} unique cloners (14d)",
            "#10A37F",
        ),
        (
            "全仓库 Git Clone" if is_zh else "Total Git Clones",
            fmt_num(total_cum_clones),
            f"覆盖 {len(rows)} 个公开仓库"
            if is_zh
            else f"Across {len(rows)} public repositories",
            "#2563EB",
        ),
        (
            "Release 下载量" if is_zh else "Release Downloads",
            fmt_num(total_pkg_dl),
            f"含全部附件共 {fmt_num(total_all_dl)} 次"
            if is_zh
            else f"{fmt_num(total_all_dl)} total asset downloads",
            "#0F766E",
        ),
    ]

    width = 960
    row_height = 33
    table_top = 314
    table_height = 40 + len(rows) * row_height
    height = table_top + table_height + 44

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">',
        "  <style>",
        "    .font { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Helvetica, Arial, sans-serif; }",
        "    .mono { font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace; }",
        "    .title { font-size: 17px; font-weight: 700; fill: #0F172A; }",
        "    .sync { font-size: 11.5px; font-weight: 500; fill: #64748B; }",
        "    .kpi-label { font-size: 12px; font-weight: 600; fill: #475569; }",
        "    .kpi-val { font-size: 22px; font-weight: 700; fill: #0F172A; }",
        "    .kpi-sub { font-size: 11px; font-weight: 400; fill: #64748B; }",
        "    .sec-title { font-size: 12.5px; font-weight: 700; fill: #1E293B; }",
        "    .th { font-size: 11.5px; font-weight: 700; fill: #475569; }",
        "    .td-repo { font-size: 12px; font-weight: 600; fill: #0F172A; }",
        "    .td-cat { font-size: 11px; font-weight: 500; fill: #334155; }",
        "    .td-num { font-size: 12px; font-weight: 500; fill: #1E293B; }",
        "    .td-bold { font-size: 12px; font-weight: 600; fill: #0F172A; }",
        "    .td-sub { font-size: 11px; font-weight: 400; fill: #64748B; }",
        "    .footer { font-size: 11px; fill: #64748B; }",
        "  </style>",
        f'  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.5"/>',
        f'  <rect x="1" y="1" width="{width - 2}" height="56" rx="12" fill="#F8FAFC"/>',
        f'  <line x1="1" y1="57" x2="{width - 1}" y2="57" stroke="#E2E8F0" stroke-width="1"/>',
        f'  <text x="24" y="35" class="font title">{html.escape(title)}</text>',
        f'  <text x="{width - 24}" y="35" text-anchor="end" class="font sync">{html.escape(sync_badge)}</text>',
    ]

    # 4 KPI Cards
    card_w = 216
    card_gap = 16
    for idx, (label, val, sub, accent) in enumerate(kpis):
        cx = 24 + idx * (card_w + card_gap)
        cy = 72
        lines.extend(
            [
                f'  <rect x="{cx}" y="{cy}" width="{card_w}" height="86" rx="8" fill="#F8FAFC" stroke="#E2E8F0" stroke-width="1"/>',
                f'  <rect x="{cx}" y="{cy}" width="4" height="86" rx="2" fill="{accent}"/>',
                f'  <text x="{cx + 14}" y="{cy + 23}" class="font kpi-label">{html.escape(label)}</text>',
                f'  <text x="{cx + 14}" y="{cy + 52}" class="font kpi-val">{html.escape(val)}</text>',
                f'  <text x="{cx + 14}" y="{cy + 72}" class="font kpi-sub">{html.escape(sub)}</text>',
            ]
        )

    # Client Plugin Distribution Section
    bar_sec_y = 174
    sec_label = (
        "客户端插件拉取分布"
        if is_zh
        else "Client Plugin Distribution"
    )
    lines.extend(
        [
            f'  <rect x="24" y="{bar_sec_y}" width="{width - 48}" height="124" rx="8" fill="#F8FAFC" stroke="#E2E8F0" stroke-width="1"/>',
            f'  <text x="40" y="{bar_sec_y + 24}" class="font sec-title">{html.escape(sec_label)}</text>',
        ]
    )

    stack_x = 40
    stack_y = bar_sec_y + 36
    stack_w = width - 80
    stack_h = 12
    lines.append(f'  <rect x="{stack_x}" y="{stack_y}" width="{stack_w}" height="{stack_h}" rx="6" fill="#E2E8F0"/>')

    cur_x = float(stack_x)
    denom = max(plugin_cum_clones, 1)
    for repo_name, _, color in PLUGIN_REPOS:
        c_val = by_repo[repo_name]["cum_clones"]
        seg_w = (c_val / denom) * stack_w
        if seg_w > 0:
            lines.append(
                f'  <rect x="{cur_x:.1f}" y="{stack_y}" width="{max(seg_w - 1.5, 3.0):.1f}" height="{stack_h}" rx="3" fill="{color}"/>'
            )
            cur_x += seg_w

    leg_w = (width - 80) // len(PLUGIN_REPOS)
    for idx, (repo_name, host_name, color) in enumerate(PLUGIN_REPOS):
        r_data = by_repo[repo_name]
        lx = 40 + idx * leg_w
        ly = bar_sec_y + 68
        pct = (r_data["cum_clones"] / denom) * 100.0
        title_line = f"{host_name} ({pct:.1f}%)"
        stat_line = (
            f"{fmt_num(r_data['cum_clones'])} Clones · 14d 独立 {fmt_num(r_data['clones_14d_uniq'])}"
            if is_zh
            else f"{fmt_num(r_data['cum_clones'])} clones · {fmt_num(r_data['clones_14d_uniq'])} unique"
        )
        lines.extend(
            [
                f'  <circle cx="{lx + 6}" cy="{ly}" r="5" fill="{color}"/>',
                f'  <text x="{lx + 16}" y="{ly + 4}" class="font td-repo">{html.escape(title_line)}</text>',
                f'  <text x="{lx + 16}" y="{ly + 21}" class="mono td-sub">{html.escape(repo_name)}</text>',
                f'  <text x="{lx + 16}" y="{ly + 37}" class="font td-sub">{html.escape(stat_line)}</text>',
            ]
        )

    # Repository Table
    lines.extend(
        [
            f'  <rect x="24" y="{table_top}" width="{width - 48}" height="{table_height}" rx="8" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1"/>',
            f'  <rect x="24" y="{table_top}" width="{width - 48}" height="38" rx="8" fill="#F1F5F9"/>',
            f'  <line x1="24" y1="{table_top + 38}" x2="{width - 24}" y2="{table_top + 38}" stroke="#CBD5E1" stroke-width="1"/>',
        ]
    )

    col_repo = 36
    col_cat = 268
    col_ver = 368
    col_sf = 545
    col_ccum = 665
    col_c14 = 815
    col_dl = 920

    headers = (
        [
            (col_repo, "start", "仓库"),
            (col_cat, "start", "类型"),
            (col_ver, "start", "最新版本"),
            (col_sf, "end", "Star / Fork"),
            (col_ccum, "end", "累计 Clone"),
            (col_c14, "end", "近 14 天 Clone (独立)"),
            (col_dl, "end", "Release 下载"),
        ]
        if is_zh
        else [
            (col_repo, "start", "Repository"),
            (col_cat, "start", "Category"),
            (col_ver, "start", "Latest Release"),
            (col_sf, "end", "Star / Fork"),
            (col_ccum, "end", "Total Clones"),
            (col_c14, "end", "14d Clones (Unique)"),
            (col_dl, "end", "Release DL"),
        ]
    )

    for cx, anchor, h_text in headers:
        lines.append(
            f'  <text x="{cx}" y="{table_top + 24}" text-anchor="{anchor}" class="font th">{html.escape(h_text)}</text>'
        )

    for idx, r in enumerate(rows):
        ry = table_top + 38 + idx * row_height
        if idx % 2 == 1:
            lines.append(
                f'  <rect x="25" y="{ry}" width="{width - 50}" height="{row_height}" fill="#F8FAFC"/>'
            )
        if idx > 0:
            lines.append(
                f'  <line x1="24" y1="{ry}" x2="{width - 24}" y2="{ry}" stroke="#F1F5F9" stroke-width="1"/>'
            )

        ty = ry + 21
        cat = r["cat_zh"] if is_zh else r["cat_en"]
        tag_disp = format_release_tag(r["latest_tag"])
        sf_str = f"{r['stars']} / {r['forks']}"
        ccum_str = fmt_num(r["cum_clones"])
        c14_str = f"{fmt_num(r['clones_14d'])} ({fmt_num(r['clones_14d_uniq'])})"
        dl_str = fmt_num(r["pkg_dl"]) if r["pkg_dl"] > 0 else "-"

        lines.extend(
            [
                f'  <circle cx="{col_repo + 4}" cy="{ty - 4}" r="3.5" fill="{r["badge_color"]}"/>',
                f'  <text x="{col_repo + 14}" y="{ty}" class="mono td-repo">{html.escape(r["repo"])}</text>',
                f'  <text x="{col_cat}" y="{ty}" class="font td-cat">{html.escape(cat)}</text>',
                f'  <text x="{col_ver}" y="{ty}" class="mono td-sub">{html.escape(tag_disp)}</text>',
                f'  <text x="{col_sf}" y="{ty}" text-anchor="end" class="mono td-num">{html.escape(sf_str)}</text>',
                f'  <text x="{col_ccum}" y="{ty}" text-anchor="end" class="mono td-bold">{html.escape(ccum_str)}</text>',
                f'  <text x="{col_c14}" y="{ty}" text-anchor="end" class="mono td-num">{html.escape(c14_str)}</text>',
                f'  <text x="{col_dl}" y="{ty}" text-anchor="end" class="mono td-num">{html.escape(dl_str)}</text>',
            ]
        )

    footer_y = table_top + table_height + 25
    footer_note = (
        "数据来源：GitHub REST API · Star / Fork 与 Release 下载为历史累计值，Git Clone 按日自动归档累加（括号内为近 14 天去重数）"
        if is_zh
        else "Source: GitHub REST API · Stars, Forks, and Release downloads are all-time totals; Git Clones are archived daily (14d unique in parentheses)"
    )
    lines.append(f'  <text x="24" y="{footer_y}" class="font footer">{html.escape(footer_note)}</text>')
    lines.append("</svg>\n")
    return "\n".join(lines)


def render_markdown_report(rows: list[dict], updated_at_cst: str) -> str:
    total_stars = sum(r["stars"] for r in rows)
    total_forks = sum(r["forks"] for r in rows)
    total_14d_clones = sum(r["clones_14d"] for r in rows)
    total_cum_clones = sum(r["cum_clones"] for r in rows)
    total_pkg_dl = sum(r["pkg_dl"] for r in rows)
    total_all_dl = sum(r["all_asset_dl"] for r in rows)

    md = [
        "# 📊 MindIE Agent 开源仓库与下载统计",
        "",
        f"> **最近更新**：`{updated_at_cst} (UTC+8)` · 每 12 小时通过 GitHub Actions 自动同步。",
        "",
        "![MindIE Agent Repository & Download Statistics](./dashboard.zh.svg)",
        "",
        "## 仓库统计明细",
        "",
        "| 类型 | 仓库 | 最新版本 | Stars | Forks | 累计 Clone | 近 14 天 Clone (独立) | 近 14 天浏览 (独立) | Release 下载 (含附件) |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        repo_link = f"[`{r['repo']}`](https://github.com/{ORG}/{r['repo']})"
        md.append(
            f"| {r['cat_zh']} | {repo_link} | `{r['latest_tag']}` | {r['stars']} | {r['forks']} "
            f"| **{fmt_num(r['cum_clones'])}** "
            f"| {fmt_num(r['clones_14d'])} ({fmt_num(r['clones_14d_uniq'])}) "
            f"| {fmt_num(r['views_14d'])} ({fmt_num(r['views_14d_uniq'])}) "
            f"| {fmt_num(r['pkg_dl'])} ({fmt_num(r['all_asset_dl'])}) |"
        )
    md.append(
        f"| **合计** | **{len(rows)} 个公开仓库** | — | **{fmt_num(total_stars)}** | **{fmt_num(total_forks)}** "
        f"| **{fmt_num(total_cum_clones)}** | **{fmt_num(total_14d_clones)}** | — | **{fmt_num(total_pkg_dl)}** ({fmt_num(total_all_dl)}) |"
    )
    md.extend(
        [
            "",
            "## 数据文件",
            "",
            "- [`dashboard.zh.svg`](./dashboard.zh.svg)：中文统计看板 SVG",
            "- [`dashboard.en.svg`](./dashboard.en.svg)：英文统计看板 SVG",
            "- [`telemetry-history.json`](./telemetry-history.json)：按日归档累加的历史统计 JSON",
            "",
        ]
    )
    return "\n".join(md)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update MindIE Agent telemetry dashboard artifacts.")
    parser.add_argument("--output-dir", required=True, help="Directory containing telemetry-history.json and SVG outputs.")
    parser.add_argument("--channel-file", default=str(DEFAULT_CHANNEL_PATH), help="Path to channels/0.1.json.")
    args = parser.parse_args()

    token = os.environ.get("TELEMETRY_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEMETRY_TOKEN / GH_TOKEN / GITHUB_TOKEN in environment.")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = out_dir / "telemetry-history.json"
    channel_pins = load_channel_pins(Path(args.channel_file).resolve())

    cst_tz = timezone(timedelta(hours=8))
    updated_at_cst = datetime.now(cst_tz).strftime("%Y-%m-%d %H:%M")

    history = load_history(history_path)
    history["updated_at_cst"] = updated_at_cst
    history, rows = collect_org_telemetry(token, history, channel_pins)

    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "dashboard.zh.svg").write_text(render_svg(rows, updated_at_cst, "zh"), encoding="utf-8")
    (out_dir / "dashboard.en.svg").write_text(render_svg(rows, updated_at_cst, "en"), encoding="utf-8")
    (out_dir / "README.md").write_text(render_markdown_report(rows, updated_at_cst), encoding="utf-8")
    print(f"Successfully generated telemetry artifacts in {out_dir} at {updated_at_cst} (UTC+8)")


if __name__ == "__main__":
    main()
