# -*- coding: utf-8 -*-
"""存储层：索引、博主数据仓、采集历史、原始产物的读写。

设计原则
- data/creators/<博主>.json 是**唯一事实来源**（结构化、机器可读）
- creators/<博主>.md 只是由它渲染出来的产物，每次整篇重生成，天然不会重复
- data/index.json 是轻量索引，用于「这个博主爬过没有 / 爬到哪了」
- data/crawl-history.json 是追加式历史，永不覆盖
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config as cfgmod
from .util import now_iso, safe_filename


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(p)
    return p


# ---------------------------------------------------------------- 索引

def load_index(cfg):
    return read_json(cfgmod.resolve(cfg, "index_file"), {"creators": {}, "version": 1})


def save_index(cfg, index):
    return write_json(cfgmod.resolve(cfg, "index_file"), index)


def find_creator_in_index(cfg, key):
    """按 抖音号 / 主页URL / 名称 / sec_uid 在索引里找博主。"""
    if not key:
        return None
    index = load_index(cfg)
    key = str(key).strip().rstrip("/")
    for slug, item in index.get("creators", {}).items():
        if key in {slug, item.get("name"), item.get("douyin_id"), item.get("sec_uid")}:
            return slug
        if item.get("home_url") and key.split("?")[0] == item["home_url"].split("?")[0]:
            return slug
        if item.get("sec_uid") and item["sec_uid"] in key:
            return slug
    return None


# ---------------------------------------------------------------- 博主数据仓

def creator_slug(name):
    return safe_filename(name)


def load_creator(cfg, slug):
    return read_json(cfgmod.resolve(cfg, "creator_store_dir") / f"{slug}.json")


def save_creator(cfg, slug, doc):
    return write_json(cfgmod.resolve(cfg, "creator_store_dir") / f"{slug}.json", doc)


def upsert_index(cfg, slug, doc, task_status="ok"):
    index = load_index(cfg)
    videos = doc.get("videos", [])
    index.setdefault("creators", {})[slug] = {
        "name": doc.get("creator_profile", {}).get("name"),
        "douyin_id": doc.get("creator_profile", {}).get("douyin_id"),
        "sec_uid": doc.get("creator_profile", {}).get("sec_uid"),
        "home_url": doc.get("creator_profile", {}).get("home_url"),
        "md_file": doc.get("meta", {}).get("md_file"),
        "video_count": len(videos),
        "transcript_ok": sum(1 for v in videos if (v.get("transcript") or {}).get("status") == "ok"),
        "transcript_failed": sum(1 for v in videos if (v.get("transcript") or {}).get("status") == "failed"),
        "last_crawl_time": doc.get("meta", {}).get("last_crawl_time"),
        "last_task_status": task_status,
    }
    save_index(cfg, index)
    return index


# ---------------------------------------------------------------- 历史

def append_history(cfg, entry):
    path = cfgmod.resolve(cfg, "history_file")
    history = read_json(path, {"runs": []}) or {"runs": []}
    history.setdefault("runs", []).append(entry)
    return write_json(path, history)


# ---------------------------------------------------------------- 原始产物

def next_raw_path(cfg, slug, stamp=None):
    stamp = stamp or now_iso()[:10].replace("-", "")
    d = cfgmod.resolve(cfg, "raw_dir")
    i = 1
    while True:
        p = d / f"{stamp}_{slug}_{i}.json"
        if not p.exists():
            return p
        i += 1


def load_raw(path):
    return read_json(path)


def transcript_path(cfg, video_id):
    return cfgmod.resolve(cfg, "transcript_dir") / f"asr_{video_id}.json"


def load_transcript(cfg, video_id):
    return read_json(transcript_path(cfg, video_id))


def save_transcript(cfg, video_id, payload):
    return write_json(transcript_path(cfg, video_id), payload)


# ---------------------------------------------------------------- 高赞评论
# 与逐字稿同构：一条视频一个文件，采集层写、ingest 自动挂到视频对象上。
# 这样「采评论」和「采视频」互不阻塞，重采也不会丢上次的结果。

def comment_path(cfg, video_id):
    return cfgmod.resolve(cfg, "comment_dir") / f"cmt_{video_id}.json"


def load_comments(cfg, video_id):
    return read_json(comment_path(cfg, video_id))


def save_comments(cfg, video_id, payload):
    return write_json(comment_path(cfg, video_id), payload)

