# -*- coding: utf-8 -*-
"""博主方向蒸馏（对标卡）：规则事实底座 + Agent 语义洞察层。

设计原则（与全工作流一致）
- 本模块**只读**博主数据仓，不参与采集 / 转录 / 合并，不改任何老路径与老字段。
- ``facts``（事实底座）全部由真实数据现算，每条都带可复核的数值或 video_id 证据，
  规则判不了的一律留空，**绝不编造**。
- ``insights``（认知信念 / 运营准则 / 爆款公式 / 翻译原则等语义结论）规则层生成不了，
  由执行 Agent 基于 facts 撰写后经 ``apply_insights`` 写回；每条结论必须挂证据 video_id。
- 数据仓新增独立键 ``distill``；老代码读不到该键即忽略，因此对存量博主零影响。

参考方法论（样本《AI蒸馏技巧大揭秘·一切博主皆可蒸馏》@觉醒书院）：
读取 → 识别（认知层 / 策略层 / 内容层，自上而下不可跳）→ 归档 → 模板化（翻译原则）→ 验证。
本模块把「读取 + 归档事实」自动化，「识别 / 模板化」的语义判断交给 insights 层。
"""
from __future__ import annotations

import re
from collections import Counter

from .util import now_iso, format_count

# 样本量经验阈值（来自样本视频实测口径：<30 看不出稳定模式，50–60 较优）
SAMPLE_MIN = 30
SAMPLE_IDEAL = (30, 60)

# 纳入钩子/表达分布的规则 flag（与 analyze.py flags 对齐；结果前置规则判不了，不纳入）
HOOK_FLAGS = [
    "是否提问开场", "是否冲突开场", "是否数字开场",
    "是否教程", "是否案例", "是否剧情", "是否热点借势",
    "是否反常识表达", "是否有评论区引导", "是否有关注/私信/收藏引导",
]


def _pct(part, total):
    if not total:
        return 0.0
    return round(part * 100.0 / total, 1)


def _flag_true(flags, name):
    f = (flags or {}).get(name) or {}
    return f.get("value") is True


def _sample_tier(n):
    if n < SAMPLE_MIN:
        return ("thin",
                f"已采 {n} 条 < {SAMPLE_MIN}，样本不足，模式不稳定，以下结论仅供参考，"
                f"建议补到 {SAMPLE_MIN} 条以上再下判断")
    if n <= SAMPLE_IDEAL[1]:
        return ("adequate", f"已采 {n} 条，落在 {SAMPLE_IDEAL[0]}–{SAMPLE_IDEAL[1]} 的较优区间")
    return ("rich", f"已采 {n} 条，样本充足（>{SAMPLE_IDEAL[1]}），边际收益递减")


# 标题模式正则（8 类，借鉴开源 blogger-distiller 的标题模式识别思路并适配抖音标题）
TITLE_PATTERNS = {
    "数字型": r"\d+",
    "疑问型": r"[？?]|怎么|如何|为什么|什么|吗",
    "感叹型": r"[！!]|绝了|太|真的|居然|竟然",
    "教程型": r"教程|手把手|保姆级|步骤|方法|攻略|教学",
    "列表型": r"合集|盘点|推荐|必备|top|榜|清单",
    "对比型": r"vs|对比|区别|差异|还是",
    "故事型": r"我|亲身|经历|踩坑|分享|心得",
    "悬念型": r"\.\.\.|…|竟然|没想到|万万|千万",
}


def extract_title_patterns(titles):
    """从标题列表现算 8 类标题模式分布（每类带条数/占比/最多 3 条示例）。

    纯函数、零依赖；标题为空或 None 的条目跳过。
    """
    valid = [t for t in titles if t and str(t).strip()]
    if not valid:
        return []
    out = []
    for name, regex in TITLE_PATTERNS.items():
        rx = re.compile(regex, re.IGNORECASE)
        hits = [t for t in valid if rx.search(str(t))]
        if hits:
            out.append({
                "label": name,
                "count": len(hits),
                "pct": round(len(hits) * 100.0 / len(valid), 1),
                "examples": [str(t)[:40] for t in hits[:3]],
            })
    out.sort(key=lambda x: x["count"], reverse=True)
    return out


def _latest_snapshot(doc):
    snaps = doc.get("account_stats") or []
    return snaps[-1] if snaps else {}


def build_facts(doc, top_n=10):
    """从数据仓现算规则事实底座。纯函数，不写盘、不改 doc。"""
    videos = doc.get("videos") or []
    profile = doc.get("creator_profile") or {}
    total = len(videos)

    with_tr = sum(1 for v in videos if (v.get("transcript") or {}).get("status") == "ok")
    with_cmt = sum(1 for v in videos if (v.get("comments") or {}).get("items"))

    # 赛道分布（复用规则层已判定的 content_categories）
    cats = Counter()
    hooks = Counter()
    structs = Counter()
    exprs = Counter()
    months = Counter()
    talk = 0
    durations = []
    hook_library = []
    seen_open = set()

    for v in videos:
        ca = v.get("content_analysis") or {}
        for c in ca.get("content_categories") or []:
            cats[c] += 1
        flags = ca.get("flags") or {}
        for name in HOOK_FLAGS:
            if _flag_true(flags, name):
                hooks[name] += 1
        if ca.get("content_structure"):
            structs[ca["content_structure"]] += 1
        if ca.get("special_expression"):
            exprs[ca["special_expression"]] += 1
        if _flag_true(flags, "是否口播"):
            talk += 1
        dur = v.get("duration_sec")
        if isinstance(dur, (int, float)):
            durations.append(float(dur))
        pt = v.get("publish_time") or ""
        if len(pt) >= 7:
            months[pt[:7]] += 1
        op = ca.get("opening_3s")
        if op and op not in seen_open:
            seen_open.add(op)
            hook_library.append(op)

    # 爆款证据榜：按详情页点赞降序，取 top_n，全部带原始互动数值与开场原文
    def digg_of(v):
        return (v.get("stats") or {}).get("digg")
    ranked = sorted(videos, key=lambda v: digg_of(v) or -1, reverse=True)
    top_hits = []
    for i, v in enumerate(ranked[:top_n], 1):
        st = v.get("stats") or {}
        ca = v.get("content_analysis") or {}
        digg = st.get("digg")
        collect = st.get("collect")
        top_hits.append({
            "rank": i,
            "video_id": v.get("video_id"),
            "url": v.get("url"),
            "title": v.get("title"),
            "digg": digg,
            "digg_raw": st.get("digg_raw"),
            "comment": st.get("comment"),
            "collect": collect,
            "share": st.get("share"),
            "collect_digg_ratio": (round(collect / digg, 3) if digg and collect else None),
            "opening_3s": ca.get("opening_3s"),
            "structure": ca.get("content_structure"),
            "markers": ca.get("structure_markers"),
        })

    # 评论共鸣点：汇总各视频已采高赞评论（只取扫描范围内已采到的，不承诺全量）
    echoes = []
    for v in videos:
        for c in ((v.get("comments") or {}).get("items") or []):
            echoes.append({
                "video_id": v.get("video_id"),
                "text": c.get("text"),
                "digg": c.get("digg"),
            })
    echoes.sort(key=lambda e: e.get("digg") or -1, reverse=True)

    tier, tier_note = _sample_tier(total)
    snap = _latest_snapshot(doc)

    return {
        "generated_at": now_iso(),
        "sample": {
            "total": total,
            "with_transcript": with_tr,
            "with_comments": with_cmt,
            "tier": tier,
            "note": tier_note,
        },
        "account": {
            "name": profile.get("name"),
            "douyin_id": profile.get("douyin_id"),
            "ip_location": profile.get("ip_location"),
            "bio": profile.get("bio"),
            "works_total": profile.get("works_total"),
            "latest_snapshot": {
                "fans_raw": snap.get("fans_raw"),
                "likes_raw": snap.get("likes_raw"),
                "works_raw": snap.get("works_raw"),
                "crawled_at": snap.get("crawled_at"),
            },
            "snapshot_count": len(doc.get("account_stats") or []),
        },
        "category_dist": [{"label": k, "count": c, "pct": _pct(c, total)}
                          for k, c in cats.most_common()],
        "title_pattern_dist": extract_title_patterns([v.get("title") or "" for v in videos]),
        "topics": (doc.get("content_summary") or {}).get("topics") or [],
        "hook_dist": [{"label": k, "count": c, "pct": _pct(c, total)}
                      for k, c in hooks.most_common()],
        "structure_dist": [{"label": k, "count": c, "pct": _pct(c, total)}
                           for k, c in structs.most_common()],
        "expression_dist": [{"label": k, "count": c, "pct": _pct(c, total)}
                            for k, c in exprs.most_common()],
        "top_hits": top_hits,
        "hook_library": hook_library,
        "timing": {
            "duration_min": min(durations) if durations else None,
            "duration_max": max(durations) if durations else None,
            "duration_mean": round(sum(durations) / len(durations), 1) if durations else None,
            "talk_count": talk,
            "talk_ratio": _pct(talk, total),
            "months": dict(sorted(months.items())),
        },
        "comment_echoes": echoes[:8],
    }


# insights 语义层允许的字段（供校验与渲染；多余字段保留不删）
INSIGHT_FIELDS = [
    "identity", "beliefs", "principles", "redlines", "formulas",
    "translation_rules", "audience", "benchmark", "verify_suggestion",
    "confidence_note",
]


def apply_insights(doc, insights):
    """把 Agent 撰写的语义洞察合并进 doc["distill"]，facts 由调用方重算。

    - 只写 ``distill.insights`` 与元信息，不动 doc 其他任何键。
    - insights 必须是 dict；否则原样返回并标注，不抛异常打断流程。
    """
    if not isinstance(insights, dict):
        doc.setdefault("distill", {})["insights"] = None
        doc["distill"]["insights_error"] = "insights 必须是对象（dict），已忽略"
        return doc
    doc.setdefault("distill", {})
    doc["distill"]["insights"] = insights
    doc["distill"]["insights_meta"] = {
        "written_at": now_iso(),
        "schema": 1,
        "fields_present": [k for k in INSIGHT_FIELDS if insights.get(k)],
    }
    doc["distill"].pop("insights_error", None)
    return doc


def build_distill(doc, insights=None, top_n=10):
    """一次性产出完整 distill 对象：facts 现算 + insights 写回（若给）。"""
    distill = doc.setdefault("distill", {})
    distill["facts"] = build_facts(doc, top_n=top_n)
    if insights is not None:
        apply_insights(doc, insights)
    distill["updated_at"] = now_iso()
    return distill
