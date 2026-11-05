# -*- coding: utf-8 -*-
"""douyin-distill 精简 CLI：博主方向蒸馏（对标卡）+ 封面视觉分析。

用法（在项目根目录执行）：
    python -m workflow.cli show --creator "<博主名>"                  # 看博主全量对标卡（MD）
    python -m workflow.cli distill --creator "<博主名>" --draft       # 只看蒸馏结论草稿，不落盘
    python -m workflow.cli distill --creator "<博主名>" --insights-file data/insights.json  # 语义洞察写回并落盘
    python -m workflow.cli covers --creator "<博主名>" --top 10       # 封面视觉分析：抽首帧 + 8 维度任务

本 CLI 是从 DouyinCreatorCollector 完整工作流拆出的「蒸馏」子集，
只包含：show / distill / covers。采集、转写、评论、经验库等能力不在本项目中。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许直接 python workflow/cli.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from workflow import config as cfgmod  # type: ignore
    from workflow import render, store  # type: ignore
else:
    from . import config as cfgmod
    from . import render, store


def _out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_show(args):
    cfg = cfgmod.load_config(args.config)
    slug = store.find_creator_in_index(cfg, args.creator) or args.creator
    doc = store.load_creator(cfg, slug)
    if not doc:
        _out({"error": f"creator not found: {args.creator}"})
        return 1
    print(render.render_creator(doc))
    return 0


def cmd_distill(args):
    """博主方向蒸馏（对标卡）：现算规则事实底座；可选把 Agent 写好的语义洞察写回。

    - 不带 --insights-file：只输出 facts（赛道/选题/钩子分布/爆款证据榜/钩子库/节奏），不写盘。
    - 带 --insights-file：把三层语义结论合并进 doc["distill"]，重算 facts，落盘并重渲染 MD。
    纯离线、不调 ASR、不联网；规则判不了的语义项留空，绝不编造。
    """
    from . import distill as D
    cfg = cfgmod.load_config(args.config)
    slug = store.find_creator_in_index(cfg, args.creator) or store.creator_slug(args.creator)
    doc = store.load_creator(cfg, slug)
    if not doc:
        _out({"error": f"creator not found: {args.creator}"})
        return 1

    insights = None
    if args.insights_file:
        insights = store.read_json(args.insights_file)
        if insights is None:
            _out({"error": f"insights 文件读不到或不是 JSON: {args.insights_file}"})
            return 1

    D.build_distill(doc, insights=insights, top_n=args.top)

    if args.insights_file:
        md_rel = doc.get("meta", {}).get("md_file") or f'{cfg["paths"]["creators_dir"]}/{slug}.md'
        store.save_creator(cfg, slug, doc)
        md_path = cfgmod.ROOT / md_rel
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render.render_creator(doc), encoding="utf-8")
        store.upsert_index(cfg, slug, doc)
        _out({"saved": True, "creator": slug, "md_file": md_rel,
              "insights_fields": (doc.get("distill", {}).get("insights_meta") or {}).get("fields_present")})
        return 0

    if args.draft:
        print("\n".join(render._render_distill(doc)))
        return 0
    _out(doc.get("distill", {}))
    return 0


def cmd_covers(args):
    """封面视觉风格分析：从数据仓视频抽首帧 → 生成 8 维度分析任务文件。

    纯离线（本地 ffmpeg 抽帧，零外部 API）；ffmpeg 找不到/视频缺失/抽帧失败均如实报告。
    产出 data/covers/<slug>/ 帧 + data/covers/<slug>_封面分析任务.md，供 AI 视觉能力逐张看图分析。
    """
    from . import cover_analysis as CA
    cfg = cfgmod.load_config(args.config)
    res, code = CA.run(cfg, args.creator, top_n=args.top, out=args.out)
    _out(res)
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(prog="douyin-distill")
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show"); p.add_argument("--creator", required=True); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("distill", help="博主方向蒸馏（对标卡）：现算事实底座；--insights-file 写回语义层")
    p.add_argument("--creator", required=True)
    p.add_argument("--insights-file", default=None, help="Agent 撰写的三层语义洞察 JSON，给了就合并写回并重渲染")
    p.add_argument("--draft", action="store_true", help="只打印可读对标卡草稿，不落盘")
    p.add_argument("--top", type=int, default=10, help="爆款证据榜条数，默认 10")
    p.set_defaults(fn=cmd_distill)

    p = sub.add_parser("covers", help="封面视觉风格分析：抽首帧 + 生成 8 维度分析任务（纯离线）")
    p.add_argument("--creator", required=True)
    p.add_argument("--top", type=int, default=10, help="按点赞降序取几条抽帧，默认 10")
    p.add_argument("--out", default=None, help="分析任务 md 输出路径（默认 data/covers/<slug>_封面分析任务.md）")
    p.set_defaults(fn=cmd_covers)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
