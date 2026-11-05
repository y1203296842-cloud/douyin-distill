# douyin-distill

![douyin-distill banner](assets/banner.png)

**把爆款，蒸馏成你的公式。**

## 先说你正在焦虑的事

做抖音，你是不是也这样：

- **爆款全靠玄学**——发了几百条，火不火看命，数据好一点你都说不清为什么；
- **从零开始摸索**——选题、标题、封面、钩子，一个坑一个坑踩，三年才攒下那点感觉；
- **爆款看了白看**——别人那条几百万播放，你也刷到了，然后……就没有然后了，除了羡慕你什么都没留下。

这不是你不努力，是**你在靠感觉做一件可以靠拆解做的事**。

## 这个工具干什么

`douyin-distill` 把对标博主的每一条视频拆开、蒸馏，直接给你答案：

> **看懂别人为什么火。**

- 他的赛道和选题靠什么吃饭，列给你；
- 他的标题是哪种套路，8 类模式直接拆给你看；
- 他的封面为什么有人点，8 个视觉维度逐条分析；
- 他的真爆款是哪几条、靠什么爆，证据榜现算，不用猜。

看完你就能回答那句最值钱的话：**他为什么火？**

## 然后是大饼

- 不用从零摸索，**站在成功者肩膀上起步**；
- 钩子、标题、封面套路拆成**可复用模板**，拿到手就能照着拍；
- 爆款不是玄学，是能拆出来的——**拆出来，就是你的公式**。

开源免费，拿去就用。

## 它到底给你什么（直说）

| 你缺的 | 它给的 |
|---|---|
| 不会选题 | 赛道 + 选题分布：对标博主靠什么吃饭，一目了然 |
| 标题不抓人 | 8 类标题模式拆解，钩子套路直接复用 |
| 封面没人点 | 8 维封面视觉分析：一眼点进来的公式 |
| 看不懂数据 | 爆款证据榜现算：点赞/收藏/评论，谁是真爆款 |
| 学不到东西 | 三层蒸馏：认知层（他是谁）→ 策略层（怎么做）→ 内容层（具体套路） |

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

### 命令一览

| 命令 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `distill` | 博主方向蒸馏：现算事实底座（赛道/选题/钩子/标题模式/爆款证据榜/节奏），可合并 Agent 语义洞察写回 | `data/creators/<博主>.json` | 对标卡 MD / JSON |
| `covers` | 封面视觉分析：ffmpeg 抽首帧 → 生成 8 维度分析任务文件 | 数据仓 json + `data/media/*.mp4` | 首帧 jpg + 分析任务 MD |
| `show` | 查看博主全量对标卡 | `data/creators/<博主>.json` | 完整 MD |

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

## 完整工作流里还有哪些能力（本项目是其中「蒸馏」子集）

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
