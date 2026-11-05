# -*- coding: utf-8 -*-
"""渲染层：把结构化博主数据仓（data/creators/*.json）渲染成 creators/*.md。

- MD 每次整篇重新生成，因此永远不会出现重复视频段落
- 字段标签固定、顺序固定、无自然语言大段 → 可正则解析，可直接丢给 AI 分析
- 真正的机器可读源是 data/creators/*.json（见 SCHEMA.md）
"""
from __future__ import annotations

from .util import format_count, strip_episode_prefix

NA = "未获取"


def _v(value, suffix=""):
    if value is None or value == "" or value == []:
        return NA
    if isinstance(value, list):
        return "、".join(str(x) for x in value) if value else NA
    if isinstance(value, bool):
        return "是" if value else "否"
    return f"{value}{suffix}"


def _flag_line(name, flag):
    if not flag:
        return f"- {name}：{NA}"
    v = flag.get("value")
    if v is None:
        return f"- {name}：{NA}（{flag.get('reason') or '无判定依据'}）"
    ev = flag.get("evidence")
    tail = f"（依据：{ev}）" if ev else ""
    return f"- {name}：{'是' if v else '否'}{tail}"


def render_creator(doc):
    p = doc.get("creator_profile", {})
    stats = doc.get("account_stats", []) or []
    latest = stats[-1] if stats else {}
    videos = doc.get("videos", []) or []
    summary = doc.get("content_summary", {}) or {}
    meta = doc.get("meta", {}) or {}

    lines = []
    lines.append(f"# {_v(p.get('name'))}")
    lines.append("")

    # ---------------- 一、基本信息
    lines.append("## 一、博主基本信息")
    lines.append("")
    lines.append(f"- 博主名称：{_v(p.get('name'))}")
    lines.append(f"- 抖音号：{_v(p.get('douyin_id'))}")
    lines.append(f"- 主页：{_v(p.get('home_url'))}")
    lines.append(f"- 主页标识（sec_uid）：{_v(p.get('sec_uid'))}")
    lines.append(f"- IP属地：{_v(p.get('ip_location'))}")
    lines.append(f"- 博主方向：{_v(summary.get('direction'))}")
    lines.append(f"- 内容赛道：{_v(summary.get('track'))}")
    lines.append(f"- 内容风格：{_v(summary.get('style'))}")
    lines.append(f"- 主要受众：{_v(p.get('audience'))}")
    lines.append(f"- 简介原文：{_v(p.get('bio'))}")
    lines.append(f"- 数据采集时间：{_v(meta.get('first_crawl_time'))}")
    lines.append(f"- 数据更新时间：{_v(meta.get('last_crawl_time'))}")
    lines.append(f"- 当前已采集视频数：{len(videos)}")
    lines.append(f"- 视频总数（主页显示）：{_v(p.get('works_total'))}")
    lines.append("")

    # ---------------- 二、账号总数据
    lines.append("## 二、账号总数据")
    lines.append("")
    lines.append(f"- 粉丝数：{_v(latest.get('fans_raw'))}")
    lines.append(f"- 获赞总数：{_v(latest.get('likes_raw'))}")
    lines.append(f"- 作品数：{_v(latest.get('works_raw'))}")
    lines.append(f"- 其他可见核心数据：{_v(p.get('extra_stats'))}")
    lines.append(f"- 数据采集时间：{_v(latest.get('crawled_at') or meta.get('last_crawl_time'))}")
    lines.append("")
    lines.append("### 账号数据快照")
    lines.append("")
    lines.append("| 日期 | 粉丝 | 获赞 | 作品数 |")
    lines.append("|---|---:|---:|---:|")
    if stats:
        for s in stats:
            lines.append(f"| {_v(s.get('date'))} | {_v(s.get('fans_raw'))} | "
                         f"{_v(s.get('likes_raw'))} | {_v(s.get('works_raw'))} |")
    else:
        lines.append(f"| {NA} | {NA} | {NA} | {NA} |")
    lines.append("")

    # ---------------- 三、内容方向概述
    lines.append("## 三、内容方向概述")
    lines.append("")
    lines.append("### 主要内容方向")
    lines.append("")
    lines.extend(_bullet_or_na(summary.get("directions"), "按已采集视频的话题标签统计"))
    lines.append("")
    lines.append("### 高频选题")
    lines.append("")
    lines.extend(_bullet_or_na(summary.get("topics"), "按已采集视频标题归并"))
    lines.append("")
    lines.append("### 常见内容结构")
    lines.append("")
    lines.extend(_bullet_or_na(summary.get("structures"), "按逐字稿结构标记统计"))
    lines.append("")
    lines.append("### 常见表达方式")
    lines.append("")
    lines.extend(_bullet_or_na(summary.get("expressions"), "按逐字稿表达标记统计"))
    lines.append("")
    lines.append("### 账号明显特征")
    lines.append("")
    lines.extend(_bullet_or_na(summary.get("features"), "由上述统计导出"))
    lines.append("")

    # ---------------- 四、视频数据
    lines.append("## 四、视频数据")
    lines.append("")
    if not videos:
        lines.append(f"（暂无已采集视频）")
        lines.append("")
    for i, v in enumerate(videos, 1):
        lines.extend(_render_video(v, i))
    # 五、博主方向蒸馏（对标卡）：仅有 distill 数据时才输出，存量博主不受影响
    lines.extend(_render_distill(doc))
    return "\n".join(lines).rstrip() + "\n"


def _render_distill(doc):
    """渲染「五、博主方向蒸馏（对标卡）」。无 distill 时返回空列表，老 MD 逐字不变。"""
    distill = doc.get("distill") or {}
    facts = distill.get("facts") or {}
    if not facts and not distill.get("insights"):
        return []
    out = ["", "## 五、博主方向蒸馏（对标卡）", ""]
    sample = facts.get("sample") or {}
    acct = facts.get("account") or {}
    snap = acct.get("latest_snapshot") or {}

    # ---- 样本与可信度 ----
    out.append("### 样本与可信度")
    out.append("")
    out.append(f"- 已采视频：{_v(sample.get('total'))} 条；"
               f"带逐字稿 {_v(sample.get('with_transcript'))} 条；"
               f"带高赞评论 {_v(sample.get('with_comments'))} 条")
    if sample.get("note"):
        out.append(f"- 样本判定：{sample['note']}")
    out.append("")

    # ---- 账号基本面（全部来自主页/快照原文，不推断） ----
    out.append("### 账号基本面")
    out.append("")
    out.append(f"- 昵称：{_v(acct.get('name'))}　抖音号：{_v(acct.get('douyin_id'))}"
               f"　IP属地：{_v(acct.get('ip_location'))}")
    out.append(f"- 主页简介原文：{_v(acct.get('bio'))}")
    out.append(f"- 粉丝：{_v(snap.get('fans_raw'))}　获赞：{_v(snap.get('likes_raw'))}"
               f"　作品：{_v(snap.get('works_raw'))}（主页显示 {_v(acct.get('works_total'))}）")
    out.append("")

    # ---- 赛道分布 ----
    cd = facts.get("category_dist") or []
    if cd:
        out.append("### 赛道分布（规则按话题标签判定）")
        out.append("")
        out.append("| 方向 | 条数 | 占比 |")
        out.append("|---|---:|---:|")
        for r in cd:
            out.append(f"| {_v(r.get('label'))} | {r.get('count')} | {r.get('pct')}% |")
        out.append("")

    # ---- 高频选题 ----
    topics = facts.get("topics") or []
    if topics:
        out.append("### 高频选题（标题归并）")
        out.append("")
        for t in topics[:12]:
            out.append(f"- {_v(t.get('label'))}：{t.get('count')} 条")
        out.append("")

    # ---- 钩子 / 结构 / 表达分布 ----
    hd = facts.get("hook_dist") or []
    if hd:
        out.append("### 钩子与表达标记分布（规则判定，附命中证据见各视频）")
        out.append("")
        out.append("| 标记 | 命中条数 | 占比 |")
        out.append("|---|---:|---:|")
        for r in hd:
            out.append(f"| {_v(r.get('label'))} | {r.get('count')} | {r.get('pct')}% |")
        out.append("")
    sd = facts.get("structure_dist") or []
    if sd:
        out.append("### 常见内容结构")
        out.append("")
        for r in sd:
            out.append(f"- {_v(r.get('label'))}：{r.get('count')} 条（{r.get('pct')}%）")
        out.append("")
    ed = facts.get("expression_dist") or []
    if ed:
        out.append("### 常见表达方式")
        out.append("")
        for r in ed:
            out.append(f"- {_v(r.get('label'))}：{r.get('count')} 条（{r.get('pct')}%）")
        out.append("")

    # ---- 标题模式分布（distill facts 现算；老数据无此键则跳过） ----
    tp = facts.get("title_pattern_dist") or []
    if tp:
        out.append("### 标题模式分布（8 类正则现算，附示例）")
        out.append("")
        out.append("| 模式 | 条数 | 占比 | 示例 |")
        out.append("|---|---:|---:|---|")
        for r in tp:
            ex = "；".join(r.get("examples") or [])
            out.append(f"| {_v(r.get('label'))} | {r.get('count')} | {r.get('pct')}% | {_v(ex)} |")
        out.append("")

    # ---- 爆款证据榜 ----
    th = facts.get("top_hits") or []
    if th:
        out.append("### 爆款证据榜（按点赞降序，供提炼公式时逐条对照）")
        out.append("")
        out.append("| # | 标题 | 赞 | 评 | 藏 | 转 | 开场3秒 |")
        out.append("|---:|---|---:|---:|---:|---:|---|")
        for h in th:
            out.append(
                f"| {h.get('rank')} | {_v(h.get('title'))} | "
                f"{_v(h.get('digg_raw'))} | {_v((h.get('comment')))} | "
                f"{_v(h.get('collect'))} | {_v(h.get('share'))} | "
                f"{_v((h.get('opening_3s')))} |")
        out.append("")

    # ---- 开场钩子库 ----
    hl = facts.get("hook_library") or []
    if hl:
        out.append("### 开场钩子库（0–3 秒原文，去重）")
        out.append("")
        for s in hl:
            out.append(f"- {s}")
        out.append("")

    # ---- 时长与节奏 ----
    tm = facts.get("timing") or {}
    if tm:
        out.append("### 时长与节奏")
        out.append("")
        out.append(f"- 时长区间：{_v(tm.get('duration_min'))}–{_v(tm.get('duration_max'))} 秒"
                   f"（均值 {_v(tm.get('duration_mean'))} 秒）")
        out.append(f"- 口播类：{_v(tm.get('talk_count'))} 条（{_v(tm.get('talk_ratio'))}%）")
        months = tm.get("months") or {}
        if months:
            out.append("- 发布月份分布：" + "、".join(f"{k}×{v}" for k, v in months.items()))
        out.append("")

    # ---- 评论共鸣点 ----
    ce = facts.get("comment_echoes") or []
    if ce:
        out.append("### 评论共鸣点（已采高赞评论，扫描范围内非全量）")
        out.append("")
        for e in ce:
            out.append(f"- 「{_v(e.get('text'))}」（赞 {_v(e.get('digg'))}，视频 {_v(e.get('video_id'))}）")
        out.append("")

    # ---- 语义洞察层（Agent 撰写，逐条挂证据）；未撰写则给占位，不编造 ----
    ins = distill.get("insights")
    out.append("### 语义洞察（认知 / 策略 / 内容三层，由 Agent 基于上方事实撰写）")
    out.append("")
    if not ins:
        out.append("> 尚未撰写。先用 `distill --creator <名>` 取事实底座，"
                   "再把三层结论（每条挂 video_id 证据）经 `--insights-file` 写回。")
        out.append("")
        return out

    if ins.get("identity"):
        out.append(f"- **一句话身份**：{ins['identity']}")
    for key, title in [("beliefs", "认知层·核心信念（他相信什么）"),
                       ("principles", "策略层·运营准则（他怎么打）"),
                       ("redlines", "策略层·红线 / 避坑")]:
        items = ins.get(key) or []
        if items:
            out.append("")
            out.append(f"**{title}**")
            out.append("")
            for it in items:
                if isinstance(it, dict):
                    ev = "、".join(str(x) for x in (it.get("evidence") or []))
                    tail = f"（证据：{ev}）" if ev else ""
                    out.append(f"- {it.get('point')}{tail}")
                else:
                    out.append(f"- {it}")
    formulas = ins.get("formulas") or []
    if formulas:
        out.append("")
        out.append("**内容层·爆款公式（每条配真实爆款例证）**")
        out.append("")
        for f in formulas:
            if isinstance(f, dict):
                ex = f.get("example") or {}
                q = ex.get("quote")
                vid = ex.get("video_id")
                tail = f"　例：「{q}」（{vid}）" if q else (f"　证据：{vid}" if vid else "")
                out.append(f"- {f.get('formula')}{tail}")
            else:
                out.append(f"- {f}")
    tr = ins.get("translation_rules") or []
    if tr:
        out.append("")
        out.append("**翻译原则 / 可迁移骨架（建模，不是抄句子）**")
        out.append("")
        for r in tr:
            out.append(f"- {r}")
    if ins.get("audience"):
        out.append("")
        out.append(f"- **目标受众**：{ins['audience']}")
    bench = ins.get("benchmark") or []
    if bench:
        out.append("")
        out.append("**对标建议（可学 / 别照搬）**")
        out.append("")
        for b in bench:
            if isinstance(b, dict):
                out.append(f"- 可学：{b.get('do')}　｜　别照搬：{b.get('dont')}")
            else:
                out.append(f"- {b}")
    if ins.get("verify_suggestion"):
        out.append("")
        out.append(f"- **验证建议（拿他没写过的话题试写，像才算成）**：{ins['verify_suggestion']}")
    if ins.get("confidence_note"):
        out.append("")
        out.append(f"- 可信度说明：{ins['confidence_note']}")
    out.append("")
    return out


def _bullet_or_na(items, note):
    if not items:
        return [f"- {NA}（{note}）"]
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append(f"- {it.get('label')}：{it.get('count')} 条")
        else:
            out.append(f"- {it}")
    return out


def _render_video(v, idx):
    st = v.get("stats", {}) or {}
    t = v.get("transcript") or {}
    ca = v.get("content_analysis") or {}
    crawl = v.get("crawl") or {}
    lines = []
    lines.append(f"### 视频 {idx:03d}")
    lines.append("")
    lines.append(f"- 视频标题：{_v(v.get('title'))}")
    lines.append(f"- 视频链接：{_v(v.get('url'))}")
    lines.append(f"- 视频ID：{_v(v.get('video_id'))}")
    lines.append(f"- 发布时间：{_v(v.get('publish_time'))}")
    lines.append(f"- 发布时间（页面原文）：{_v(v.get('publish_time_raw'))}")
    lines.append(f"- 视频时长：{_v(v.get('duration_sec'), ' 秒')}")
    lines.append(f"- 视频时长（页面原文）：{_v(v.get('duration_raw'))}")
    lines.append(f"- 视频类型：{_v(v.get('video_type'))}")
    lines.append(f"- 视频对应账号：{_v(v.get('creator_name'))}")
    lines.append(f"- 标签/话题：{_v(v.get('tags'))}")
    lines.append(f"- 音乐/背景音乐：{_v(v.get('music'))}")
    lines.append(f"- 是否置顶：{_v(v.get('pinned'))}")
    lines.append(f"- 合集：{_v(v.get('collection'))}")
    lines.append(f"- 点赞：{_v(st.get('digg_raw'))}（约 {format_count(st.get('digg'))}）")
    lines.append(f"- 评论：{_v(st.get('comment_raw'))}（约 {format_count(st.get('comment'))}）")
    lines.append(f"- 收藏：{_v(st.get('collect_raw'))}（约 {format_count(st.get('collect'))}）")
    lines.append(f"- 转发：{_v(st.get('share_raw'))}（约 {format_count(st.get('share'))}）")
    lines.append(f"- 其他可见互动数据：{_v(st.get('extra'))}")
    lines.append(f"- 数据更新时间：{_v(crawl.get('data_update_time'))}")
    lines.append("")

    lines.append("#### 视频逐字稿")
    lines.append("")
    if t.get("status") == "ok" and t.get("text"):
        # 优先用后处理版（已断句加标点、术语已纠错）；没有就退回原样连续文本
        paras = t.get("paragraphs") or None
        for para in (paras or [t.get("text_polished") or t["text"]]):
            lines.append(f"> {para}")
            lines.append("")
        st = t.get("polish_stats") or {}
        if paras:
            lines.append(f"- 逐字稿处理：已自动断句加标点（{st.get('paragraphs')} 段 / "
                         f"{st.get('sentences')} 句，按语音停顿与句长规则生成，非原样）")
        corr = t.get("corrections_applied") or []
        if corr:
            lines.append("- 术语纠错：" + "；".join(
                f"`{c['from']}`→`{c['to']}`×{c['count']}" for c in corr))
        low = t.get("low_confidence") or []
        if low:
            lines.append(f"- 存疑片段（置信度 < {st.get('low_confidence_threshold')}，建议人工核对）"
                         f"：{len(low)} 处")
            for s in low:
                lines.append(f"  - {s.get('start_time')}s–{s.get('end_time')}s"
                             f"（{s.get('confidence')}）{s.get('subtitle_text')}")
        if paras or corr or low:
            lines.append("")
        segs = t.get("segments") or []
        if segs:                      # 没有分段信息时不要空印一个标题
            lines.append("**分段时间轴（原样识别结果，未加工）**")
            lines.append("")
            for s in segs:
                lines.append(f"- {s.get('start_time')}s–{s.get('end_time')}s　{s.get('subtitle_text')}")
    else:
        reason = t.get("error") or "未转录"
        lines.append(f"> [转录失败：{reason}]")
    lines.append("")

    # ---- 高赞评论（自适应检索，从不整段扫完；没采过就不出这段）
    cm = v.get("comments") or {}
    cst = cm.get("stats") or {}
    citems = cm.get("items") or []
    if citems:
        from . import comments as _cm
        cov = cst.get("coverage")
        lines.append("#### 高赞评论")
        lines.append("")
        lines.append(f"- 检索说明：{_cm.explain(cst)}")
        lines.append(f"- 评论总数（页面显示）：{_v(cst.get('total_estimate'))}")
        lines.append(f"- 实际检索条数：{_v(cst.get('scan_count'))} 条"
                     f"（占全部评论 {('%.1f%%' % (cov * 100)) if cov else '未知'}；"
                     f"扫描上限 {_v(cst.get('max_scan'))} 条，未遍历整个评论区）")
        order = cst.get("order") or {}
        lines.append(f"- 排序可靠性：{'按点赞排序' if order.get('reliable') else '非按点赞排序（因此按实际点赞数比较后取值）'}"
                     f"；逆序比 {_v(order.get('violation_ratio'))}")
        lines.append(f"- 停止原因：{_v(cst.get('stopped_by'))}；置信度：{_v(cst.get('confidence'))}"
                     f"（{_v(cst.get('confidence_basis'))}）")
        lines.append(f"- 检索策略：{_v(cst.get('strategy'))}；采集时间：{_v(cm.get('fetched_at'))}")
        lines.append("")
        for i, c in enumerate(citems, 1):
            lines.append(f"{i}. 「{c.get('text')}」")
            lines.append(f"   - 点赞：{_v(c.get('digg_raw'))}（约 {format_count(c.get('digg'))}）")
            lines.append(f"   - 作者：{_v(c.get('author'))}")
            lines.append(f"   - 时间：{_v(c.get('time_text'))}　属地：{_v(c.get('place'))}")
            lines.append(f"   - 回复数：{_v(c.get('reply_raw'))}")
            lines.append(f"   - 排序位置：第 {int(c.get('position') or 0) + 1} 条")
            if c.get("tag"):
                lines.append(f"   - 标记：{c['tag']}")
        lines.append("")

    lines.append("#### 内容补充信息")
    lines.append("")
    lines.append(f"- 开头钩子（0–3 秒）：{_v(ca.get('opening_3s'))}")
    lines.append(f"- 开头内容（0–5 秒）：{_v(ca.get('opening_5s'))}")
    lines.append(f"- 视频核心主题：{_v(ca.get('core_topic'))}")
    lines.append(f"- 内容方向：{_v(ca.get('content_categories'))}")
    lines.append(f"- 选题：{_v(strip_episode_prefix(ca.get('core_topic')))}")
    lines.append(f"- 核心观点：{_v(ca.get('core_viewpoint'))}")
    lines.append(f"- 内容结构：{_v(ca.get('content_structure'))}")
    lines.append(f"- 结构标记：{_v(ca.get('structure_markers'))}")
    lines.append(f"- CTA/结尾动作：{_v(ca.get('cta'))}")
    lines.append(f"- 特殊表达：{_v(ca.get('special_expression'))}")
    lines.append(f"- 备注：{_v(ca.get('notes'))}")
    lines.append("")
    lines.append("**内容特征标记（规则判定，附证据）**")
    lines.append("")
    for name, flag in (ca.get("flags") or {}).items():
        lines.append(_flag_line(name, flag))
    lines.append("")

    lines.append("#### 采集状态")
    lines.append("")
    lines.append(f"- 逐字稿状态：{_v(t.get('status'))}")
    if t.get("status") != "ok":
        lines.append(f"- 待补数据：transcription_status: {_v(t.get('status') or 'pending')}")
        lines.append(f"- 可重试：{'是' if t.get('retryable', True) else '否'}")
    lines.append(f"- 首次采集时间：{_v(crawl.get('first_crawl_time'))}")
    lines.append(f"- 最近采集时间：{_v(crawl.get('last_crawl_time'))}")
    lines.append(f"- 媒体文件：{_v(v.get('media_path'))}")
    lines.append(f"- 采集错误：{_v(v.get('errors'))}")
    lines.append("")

    hist = crawl.get("update_history") or []
    if hist:
        lines.append("#### 数据更新记录")
        lines.append("")
        lines.append("| 更新时间 | 字段 | 旧值 | 新值 |")
        lines.append("|---|---|---|---|")
        for h in hist:
            lines.append(f"| {_v(h.get('time'))} | {_v(h.get('field'))} | "
                         f"{_v(h.get('old'))} | {_v(h.get('new'))} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    return lines
