# -*- coding: utf-8 -*-
"""通用工具层：数值解析、时间解析、唯一标识、文件名规范化。

本模块不含任何采集逻辑，可被任意采集层/整理层复用。
"""
from __future__ import annotations

import datetime
import hashlib
import re

TZ = datetime.timezone(datetime.timedelta(hours=8))

_CN_UNITS = {
    "万": 10_000, "w": 10_000, "W": 10_000,
    "亿": 100_000_000,
    "k": 1_000, "K": 1_000,
    "千": 1_000,
    "m": 1_000_000, "M": 1_000_000,
}

_COUNT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(万|亿|w|W|k|K|千|m|M)?$")

_ILLEGAL_FS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


# ---------------------------------------------------------------- 数值

def parse_cn_count(raw):
    """把抖音展示数值转成整数近似值。

    '45.6万' -> 456000 ; '7415' -> 7415 ; '1.5万' -> 15000
    无法识别时返回 None（绝不猜测）。
    """
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("，", "").replace(" ", "")
    if not s or s in {"-", "暂无", "未获取", "N/A"}:
        return None
    m = _COUNT_RE.match(s)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit:
        value *= _CN_UNITS[unit]
    return int(round(value))


def format_count(n):
    """反向格式化，仅用于人读展示。"""
    if n is None:
        return "未获取"
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n)


# ---------------------------------------------------------------- 时间

def now():
    return datetime.datetime.now(TZ)


def now_iso():
    return now().replace(microsecond=0).isoformat()


def video_id_to_time(video_id):
    """抖音 aweme_id 高 32 位是发布时间的 Unix 秒。

    已用「页面显示的发布日期」交叉验证：5/5 一致。
    无法解析时返回 None。
    """
    try:
        v = int(str(video_id).strip())
    except (TypeError, ValueError):
        return None
    ts = v >> 32
    if not (1_000_000_000 <= ts <= 4_000_000_000):
        return None
    return datetime.datetime.fromtimestamp(ts, TZ).replace(microsecond=0)


def parse_relative_date(raw, base=None):
    """把 '5天前' / '3小时前' / '1月16日' 这类展示值解析成 ISO 时间。

    只做确定性换算；无法确定年份的（如 '1月16日'）返回 (iso, 'display_only')。
    返回 (iso 字符串或 None, 说明)
    """
    if not raw:
        return None, "empty"
    s = str(raw).strip()
    base = base or now()

    m = re.match(r"^(\d+)\s*(秒|分钟|小时|天)前$", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = {
            "秒": datetime.timedelta(seconds=n),
            "分钟": datetime.timedelta(minutes=n),
            "小时": datetime.timedelta(hours=n),
            "天": datetime.timedelta(days=n),
        }[unit]
        return (base - delta).replace(microsecond=0).isoformat(), "relative"

    m = re.match(r"^(\d{1,2})月(\d{1,2})日$", s)
    if m:
        return None, "no_year"  # 交给 video_id_to_time，避免猜年份

    m = re.match(r"^(\d{4})[-年](\d{1,2})[-月](\d{1,2})", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return datetime.datetime(y, mo, d, tzinfo=TZ).isoformat(), "absolute"

    return None, "unrecognized"


# ---------------------------------------------------------------- 标识

def canonical_url(url):
    """规范化 URL：去查询串与尾斜杠，用于兜底去重。"""
    if not url:
        return None
    u = str(url).strip().split("?")[0].split("#")[0].rstrip("/")
    return u


def content_hash(publish_date, title, transcript_text):
    """兜底唯一标识：发布时间 + 标题 + 逐字稿文本。"""
    parts = [str(publish_date or ""), str(title or ""), str(transcript_text or "")[:5000]]
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:16]


def safe_filename(name, default="未命名"):
    cleaned = _ILLEGAL_FS.sub("_", str(name or "").strip()).strip("._ ")
    return cleaned or default


def extract_tags(text):
    """从描述里提取 #话题 标签。"""
    if not text:
        return []
    return [t.strip() for t in re.findall(r"#([^#\s]+)", str(text)) if t.strip()]


def strip_episode_prefix(title):
    """去掉 '第5集：' 这类集数前缀，保留主题。"""
    if not title:
        return title
    return re.sub(r"^第\s*\d+\s*[集条期]\s*[：:]\s*", "", str(title).strip()).strip()


def merge_unique(*lists):
    seen, out = set(), []
    for lst in lists:
        for item in lst or []:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out
