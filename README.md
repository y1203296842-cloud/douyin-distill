# douyin-distill

**抖音博主蒸馏器（独立子集版）**：把采集好的博主数据仓蒸馏成「对标卡」——赛道、选题、钩子分布、爆款证据榜、标题模式、封面视觉风格，全部现算，**纯离线、零 API、不编造**。

本项目是从完整工作流 **DouyinCreatorCollector**（本地 `完整工作流`）中**复制**出的「蒸馏」链路，独立成库。原工作流不受影响，两边可各自演进。

## 有什么功能

| 命令 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `distill` | 博主方向蒸馏：现算事实底座（赛道/选题/钩子/标题模式/爆款证据榜/节奏），可合并 Agent 语义洞察写回 | `data/creators/<博主>.json` | 对标卡 MD / JSON |
| `covers` | 封面视觉分析：ffmpeg 抽首帧 → 生成 8 维度分析任务文件 | 数据仓 json + `data/media/*.mp4` | 首帧 jpg + 分析任务 MD |
| `show` | 查看博主全量对标卡 | `data/creators/<博主>.json` | 完整 MD |

## 快速开始

```bash
# 1. 把博主数据仓 json 放进 data/creators/（格式见下文「数据格式」）
# 2. 蒸馏（只看草稿，不落盘）
python -m workflow.cli distill --creator "油条条" --draft

# 3. 蒸馏 + 语义洞察写回（insights.json 由 Agent 撰写三层语义结论）
python -m workflow.cli distill --creator "油条条" --insights-file data/insights.json

# 4. 封面视觉分析（需要 data/media/ 下有对应 mp4，本地 ffmpeg）
python -m workflow.cli covers --creator "油条条" --top 10

# 5. 看全量对标卡
python -m workflow.cli show --creator "油条条"
```

样例数据已附带：`data/creators/油条条.json`（60 条视频，含逐字稿与点赞数据），`--draft` 可直接跑通。
`covers` 需要视频文件：把 mp4 放入 `data/media/`（文件名与 json 中 `media_path` 相对路径一致）；媒体缺失时如实报告，不伪造。

## 数据格式

`data/creators/<博主>.json`（唯一事实来源）：

```json
{
  "creator_profile": {"name": "油条条", "douyin_id": "...", "home_url": "...", "bio": "..."},
  "meta": {"md_file": "creators/油条条.md", "last_crawl_time": "..."},
  "distill": {"facts": {...}, "insights": {...}},
  "videos": [
    {
      "video_id": "7692418680675694833",
      "title": "...",
      "publish_date": "...",
      "stats": {"digg_raw": "45.6万", "digg": 456000, "comment_raw": "...", "collect_raw": "..."},
      "media_path": "data/media/douyin_7692418680675694833.mp4",
      "transcript": {"status": "ok", "segments": [...], "text": "..."}
    }
  ]
}
```

规则与约束（沿用完整工作流设计原则）：
- 取不到写 `未获取` / `N/A`，绝不编造；规则判不了的语义项留空。
- `distill` 三层：**认知层**（他是谁/赛道/受众）→ **策略层**（选题/钩子/节奏）→ **内容层**（爆款证据榜/标题模式/封面公式）。
- 封面 = 视频首帧近似（作者自定义封面可能有偏差，产物会注明）。

## 完整工作流里有哪些能力（本项目是其中「蒸馏」子集）

完整工作流 `DouyinCreatorCollector` 还包含：浏览器采集（列表/详情/断点续爬）、ASR 转写、术语纠错、评论采集与口径检查、经验库（knowledge/retro）、持续学习状态机、doctor 自检、导出 Skill 等。本项目不包含这些，只聚焦「拿到数据仓之后怎么榨出创作决策」。

## 依赖

- Python 3.9+（仅标准库）
- `covers` 需要本机 ffmpeg（查找顺序：`config.json` 的 `external.ffmpeg_bin` → PATH → 常见安装位置）

## 隐私与合规

- 数据由使用者自行采集，请遵守平台规则与当地法律；脚本本身纯离线、零外部 API。
- `data/media/`、`data/covers/` 已入 .gitignore，不随仓库上传。
- 示例博主数据为公开内容，仅用于演示。

## 许可证

MIT（与上游 DouyinCreatorCollector 一致；评估吸收自开源项目 [blogger-distiller](https://github.com/otter1101/blogger-distiller) 的标题模式/封面分析思路，MIT 许可）。
