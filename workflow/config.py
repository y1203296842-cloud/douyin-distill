# -*- coding: utf-8 -*-
"""配置层：所有可调参数集中在 config.json，代码不写死任何数量或阈值。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

_DEFAULTS = {
    "paths": {
        "creators_dir": "creators",
        "data_dir": "data",
        "media_dir": "data/media",
        "raw_dir": "data/raw",
        "transcript_dir": "data/transcripts",
        "creator_store_dir": "data/creators",
        "covers_dir": "data/covers",
        "index_file": "data/index.json",
        "history_file": "data/crawl-history.json",
        "plan_dir": "data/plans",
        "learning_dir": "data/learning",
        "knowledge_dir": "knowledge",
    },
    # 外部项目/服务位置（运行环境层，用户本机配置；留空=功能降级不报错）
    "external": {
        "cheat_root": "",          # 内容工作区（如 <内容工作区>）；空=不写 brief
        "cheat_from_collector": "",  # cheat 侧接收摘要的目录；空=用 cheat_root/from_collector
        "asr_model_dir": "",       # 本地 ASR 模型目录；空=仅 mediakit-cli
        "sherpa_bin": "",          # sherpa-onnx 可执行文件；空=自动探测 PATH
        "ffmpeg_bin": "",
        "media_fallback_dir": "",  # 浏览器下载目录（采集器搬媒体前）
    },
    "collection": {
        "default_count": 50,
        "sort": "homepage_order",
        "filters": {
            "min_digg": None,
            "max_digg": None,
            "publish_after": None,
            "publish_before": None,
            "keywords_any": [],
            "keywords_none": [],
            "content_types": [],
            "require_transcript": False,
            "min_duration_sec": None,
            "max_duration_sec": None,
            "pinned_only": False
        },
        "transcript": {"enabled": True, "retry_failed": True, "max_retry": 3},
        "dedupe": {"key_priority": ["video_id", "canonical_url", "content_hash"]},
        "update": {"update_stats": True, "keep_history": True, "max_history_per_video": 10},
        "network": {
            "page_wait_sec": 6,
            "between_videos_sec": 2,
            "max_videos_per_run": 60,
            "stop_on_captcha": True,
            "page_load_timeout_sec": 25
        },
        "retry": {"max_attempts": 2, "backoff_sec": 5}
    },
    "tags_ignore_in_hotspot": ["dou上热门", "上热门", "热门"],
    "transcripts": {
        "punctuate": True,
        "comma_gap_sec": 0.18,
        "period_gap_sec": 0.35,
        "paragraph_gap_sec": 0.6,
        "sentence_max_chars": 22,
        "paragraph_sentences": 4,
        "confidence": True,
        "low_confidence_threshold": 0.9,
        "corrections": {},
        "corrections_by_creator": {}
    }
}


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=None):
    p = Path(path) if path else CONFIG_PATH
    if not p.exists():
        return json.loads(json.dumps(_DEFAULTS))
    with p.open("r", encoding="utf-8") as f:
        user_cfg = json.load(f)
    return _deep_merge(_DEFAULTS, user_cfg)


def resolve(cfg, key):
    """把 paths 里的相对路径解析成绝对路径（相对项目根）。"""
    rel = cfg["paths"][key]
    p = Path(rel)
    return p if p.is_absolute() else (ROOT / p)


def external_path(cfg, key):
    """返回外部路径（external.<key>）。未配置或为空 → None。
    用于 cheat 工作区、模型目录等运行环境层设置；None 时调用方降级，不报错。"""
    ext = (cfg.get("external") or {}).get(key) or ""
    return Path(ext) if ext.strip() else None


def ensure_dirs(cfg):
    for key in ("creators_dir", "data_dir", "media_dir", "raw_dir",
                "transcript_dir", "creator_store_dir", "covers_dir", "plan_dir"):
        resolve(cfg, key).mkdir(parents=True, exist_ok=True)
    return ROOT
