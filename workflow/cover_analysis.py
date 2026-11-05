# -*- coding: utf-8 -*-
"""封面视觉风格分析：从数据仓读视频 → ffmpeg 抽首帧 → 生成 8 维度分析任务。

背景：借鉴开源项目 blogger-distiller（otter1101，MIT）的封面视觉分析思路
（8 维度视觉拆解：风格类型/构图/标题钩子/文字设计/人物出镜/装饰元素/信息密度/视觉一致性），
但**不复制其采集层**（TikHub 付费 API）与封面 URL 依赖——本模块完全离线：
封面 = 本地 mp4 视频首帧（抖音口播封面即首帧，无需网络、零 API 调用）。

设计原则（与全工作流一致）：
- **只读**数据仓 ``videos[].media_path / stats``，不写回 doc、不改采集层、不改老字段。
- **不编造**：ffmpeg 找不到、视频文件缺失、抽帧失败都如实记录原因，绝不伪造封面图。
- **纯离线**：唯一外部依赖是本地 ffmpeg 可执行文件。

用法：
    python -m workflow.cli covers --creator <博主名> [--top 10]

产出：
    data/covers/<slug>/          抽出的首帧 jpg（按点赞降序编号）
    data/covers/<slug>_封面分析任务.md   8 维度分析指令（内联帧路径，供 AI 视觉能力逐张看图）
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import config as cfgmod
from . import store
from .util import format_count

# ffmpeg 常见安装位置探测（config 未配置 ffmpeg_bin 且 PATH 没有时的兜底）
FFMPEG_PROBE_PATHS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
]


def find_ffmpeg(cfg):
    """定位 ffmpeg 可执行文件。优先级：config.external.ffmpeg_bin → PATH → 常见位置。
    找不到返回 None（调用方如实报告，不抛异常）。"""
    ext = cfgmod.external_path(cfg, "ffmpeg_bin")
    if ext and ext.is_file():
        return str(ext)
    which = shutil.which("ffmpeg")
    if which:
        return which
    for p in FFMPEG_PROBE_PATHS:
        if Path(p).is_file():
            return p
    return None


def _digg_of(v):
    st = v.get("stats") or {}
    return st.get("digg") or -1


def extract_covers(cfg, doc, slug, top_n=10):
    """按点赞降序取 top_n 条有本地媒体的视频，抽首帧到 data/covers/<slug>/。

    返回条目列表：
        {video_id, title, digg, frame_path(绝对), frame_rel(相对项目根), error}
    抽帧失败的条目带 error 原因，不中断整体。
    """
    ffmpeg = find_ffmpeg(cfg)
    if not ffmpeg:
        return None, "未找到 ffmpeg（config.external.ffmpeg_bin / PATH / 常见位置均无），封面抽帧不可用。"

    videos = [v for v in (doc.get("videos") or []) if v.get("media_path")]
    if not videos:
        return None, "数据仓中该博主没有任何带 media_path 的视频，无法抽帧。"

    ranked = sorted(videos, key=_digg_of, reverse=True)[:top_n]
    covers_dir = cfgmod.resolve(cfg, "covers_dir") / slug
    covers_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for i, v in enumerate(ranked, 1):
        rel = v["media_path"]
        src = cfgmod.ROOT / rel
        st = v.get("stats") or {}
        digg_raw = st.get("digg_raw")
        if not src.is_file():
            items.append({"video_id": v.get("video_id"), "title": v.get("title"),
                          "digg": _digg_of(v), "digg_raw": digg_raw,
                          "frame_path": None, "frame_rel": None,
                          "error": f"媒体文件缺失: {rel}"})
            continue
        frame_rel = f"data/covers/{slug}/{i:02d}_{v.get('video_id')}.jpg"
        frame = cfgmod.ROOT / frame_rel
        try:
            r = subprocess.run(
                [ffmpeg, "-y", "-ss", "0.1", "-i", str(src), "-vframes", "1", "-q:v", "3", str(frame)],
                capture_output=True, text=True, timeout=60)
            if r.returncode != 0 or not frame.is_file():
                items.append({"video_id": v.get("video_id"), "title": v.get("title"),
                              "digg": _digg_of(v), "digg_raw": digg_raw,
                              "frame_path": None, "frame_rel": None,
                              "error": "抽帧失败: " + (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "ffmpeg 返回非零")})
                continue
            items.append({"video_id": v.get("video_id"), "title": v.get("title"),
                          "digg": _digg_of(v), "digg_raw": digg_raw,
                          "frame_path": str(frame), "frame_rel": frame_rel,
                          "error": None})
        except (subprocess.TimeoutExpired, OSError) as e:
            items.append({"video_id": v.get("video_id"), "title": v.get("title"),
                          "digg": _digg_of(v), "digg_raw": digg_raw,
                          "frame_path": None, "frame_rel": None,
                          "error": f"抽帧异常: {e}"})
    return items, None


def _digg_label(it):
    """封面条目展示用点赞：原文（如 45.6万）优先，其次正数，都没有显示 —。"""
    raw = it.get("digg_raw")
    if raw:
        return str(raw)
    d = it.get("digg")
    return str(d) if isinstance(d, int) and d > 0 else "—"


def build_analysis_task(cfg, creator_name, items, out_md):
    """生成《<博主名>_封面分析任务.md》：内联帧绝对路径 + 8 维度分析指令。

    指令结构借鉴 blogger-distiller cover_analyzer（8 维度视觉拆解），
    输出契约：封面公式 + 内容-封面匹配度 + 3 条可落地建议。
    """
    ok = [it for it in items if it.get("frame_path")]
    L = []
    L.append(f"# 封面视觉分析任务 — {creator_name}")
    L.append("")
    L.append(f"> 由 workflow.cover_analysis 自动生成（基于本地视频首帧抽帧，零外部 API）")
    L.append(f"> 共抽帧 {len(ok)}/{len(items)} 张（按点赞降序取 top）。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 操作步骤")
    L.append("")
    L.append("1. 用 Read 工具**逐张打开**下方封面帧图片（绝对路径），每张都要真正看图。")
    L.append("2. 按 8 个 Step 完成视觉拆解，结论必须**基于看到的画面**，不许泛泛而谈。")
    L.append("3. 最后输出三项总结（封面公式 / 内容-封面匹配度 / 3 条可落地建议）。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 1：封面风格类型识别")
    L.append("")
    L.append("整体判断该博主主要使用哪种封面风格（可多选，标注占比）：")
    L.append("")
    L.append("| 风格类型 | 特征 |")
    L.append("|---------|------|")
    L.append("| **人物风** | 真人出镜为主视觉，靠表情/动作建立信任感与情绪共鸣 |")
    L.append("| **文字大字报风** | 文字占主导（≥50% 画面），信息密度高，干货感强 |")
    L.append("| **场景/素材风** | 以画面素材、影视截图、AI 图为主，文字点缀 |")
    L.append("| **拼贴风** | 多图拼接，风格化处理 |")
    L.append("| **杂志风** | 高级感排版，构图接近平面设计 |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 2：构图类型分析")
    L.append("")
    L.append("逐一判断每张封面构图，汇总最常用的类型：")
    L.append("")
    L.append("| 构图类型 | 特征 |")
    L.append("|---------|------|")
    L.append("| **四角压字** | 大字压画面四角，中间留给画面 |")
    L.append("| **三明治排版** | 上文字-中画面-下文字 |")
    L.append("| **居中构图** | 主视觉居中，秩序感强 |")
    L.append("| **左右构图** | 文字在一侧，画面在另一侧 |")
    L.append("| **上下构图** | 文字在上/下，画面在另一侧 |")
    L.append("| **文字铺满** | 文字铺满全屏，画面只作背景 |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 3：标题钩子类型分析（点击率核心）")
    L.append("")
    L.append("判断封面标题/文字属于哪种钩子（可多选），给出典型例句：")
    L.append("")
    L.append("| 钩子类型 | 特征 | 示例 |")
    L.append("|---------|------|------|")
    L.append("| **数字型** | 具体数字制造确定感 | '3招''1小时搞定' |")
    L.append("| **疑问型** | 提问引发好奇/自我对照 | '你做对了吗？' |")
    L.append("| **利益型** | 直接说出能得到什么 | '看完就能用' |")
    L.append("| **反常识型** | 颠覆认知制造冲突 | '成绩越好混得越差？' |")
    L.append("| **情绪共鸣型** | 说出受众的处境/感受 | '允许自己烂一下' |")
    L.append("| **目标人群型** | 直接点名受众 | 'AI新手''打工人' |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 4：文字设计分析")
    L.append("")
    L.append("- 字号层级：几层文字（主标题/副标题/说明）？比例如何？")
    L.append("- 字体风格：粗体 / 手写体 / 综艺大字 / 克制细体")
    L.append("- 特殊处理：变形 / 旋转 / 叠加 / 描边 / 颜色混排？")
    L.append("- 排布：错落有致 vs 整齐排列？")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 5：人物出镜分析")
    L.append("")
    L.append("- 出镜频率：几成封面有真人出镜？")
    L.append("- 拍摄视角：平拍 / 仰拍 / 俯拍？")
    L.append("- 情绪表达：表情夸张吗？动作配合标题吗？")
    L.append("- 人物与文字空间关系：左右分 / 文字环绕 / 人物即背景？")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 6：装饰元素分析")
    L.append("")
    L.append("统计常用装饰元素：手绘箭头/波浪线、抠图描边、角标徽章（必看/NEW）、贴纸 emoji、英文混排、其他特征元素。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 7：信息密度判断")
    L.append("")
    L.append("- **高密度**：文字层级多、装饰丰富（教程/攻略）")
    L.append("- **中密度**：主标题+副标题，清晰不拥挤")
    L.append("- **低密度**：一句话/大字+大图，情绪感强")
    L.append("- 该博主整体偏向哪个密度？不同类型是否有差异？")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 8：视觉一致性评估")
    L.append("")
    L.append("- 封面间是否有统一视觉语言（固定色系/构图/字体）？")
    L.append("- 一眼能否认出是同一个博主？")
    L.append("- 一致性强 / 中等 / 弱，说明原因")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 封面帧清单（按点赞降序）")
    L.append("")
    for it in items:
        label = _digg_label(it)
        if it.get("frame_path"):
            L.append(f"### 封面（{label} 赞）：《{it['title']}》")
            L.append(f"绝对路径：`{it['frame_path']}`")
            L.append(f"![封面]({it['frame_path']})")
            L.append("")
        else:
            L.append(f"### 封面（{label} 赞）：《{it['title']}》")
            L.append(f"⚠️ {it.get('error')}")
            L.append("")
    L.append("---")
    L.append("")
    L.append("## 输出格式（三项总结）")
    L.append("")
    L.append("### 封面公式")
    L.append("一行提炼：`[构图类型] + [标题钩子类型] + [主视觉风格] + [标志性装饰元素]`")
    L.append("")
    L.append("### 内容-封面匹配度")
    L.append("判断封面风格是否匹配其内容赛道（匹配/错位 + 具体错位案例）")
    L.append("")
    L.append("### 3 条可落地的优化建议")
    L.append("必须结合上面分析到的具体问题，不要通用建议。")
    L.append("")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(L), encoding="utf-8")
    return out_md


def run(cfg, creator, top_n=10, out=None):
    """CLI 入口：抽帧 + 生成分析任务文件。返回 (dict, exit_code)。"""
    slug = store.find_creator_in_index(cfg, creator) or store.creator_slug(creator)
    doc = store.load_creator(cfg, slug)
    if not doc:
        return {"error": f"creator not found: {creator}"}, 1

    items, err = extract_covers(cfg, doc, slug, top_n=top_n)
    if err:
        return {"error": err, "creator": slug}, 1

    ok_count = sum(1 for it in items if it.get("frame_path"))
    fail_count = len(items) - ok_count
    if ok_count == 0:
        return {"error": "全部抽帧失败，无可用封面。", "creator": slug, "detail": items}, 1

    out_md = Path(out) if out else cfgmod.resolve(cfg, "covers_dir") / f"{slug}_封面分析任务.md"
    out_md = build_analysis_task(cfg, doc.get("creator_name") or slug, items, out_md)

    return {
        "saved": True,
        "creator": slug,
        "frames": ok_count,
        "failed": fail_count,
        "frames_dir": str(cfgmod.resolve(cfg, "covers_dir") / slug),
        "task_file": str(out_md),
        "note": "封面为视频首帧抽帧（近似封面），分析与真实封面可能有偏差",
    }, 0
