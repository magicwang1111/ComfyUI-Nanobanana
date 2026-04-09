# ComfyUI-Nanobanana

`ComfyUI-Nanobanana` 是一个直接封装 Google Gemini Image 原生 REST API 的 ComfyUI 自定义节点包，首版聚焦 `Nano Banana` 系列图像生成与图像编辑能力，不依赖 `google-genai` SDK，也不做 grounding、多轮会话或任务轮询。

## 节点列表

- `ComfyUI-Nanobanana Client`
- `ComfyUI-Nanobanana Nano Banana`
- `ComfyUI-Nanobanana Nano Banana 2`
- `ComfyUI-Nanobanana Nano Banana Pro`

## 模型映射

- `Nano Banana` -> `gemini-2.5-flash-image`
- `Nano Banana 2` -> `gemini-3.1-flash-image-preview`
- `Nano Banana Pro` -> `gemini-3-pro-image-preview`

## 设计范围

- 原生 REST 调用 `POST /v1beta/models/{model}:generateContent`
- 使用 ComfyUI 批量 `IMAGE` 输入作为参考图，不拆成多个单独图像插口
- 输出标准 `IMAGE`，可直接接 `PreviewImage` / `SaveImage`
- 输出 `text` 和 `response_json` 便于调试
- `Nano Banana 2` 额外支持 `include_thoughts` 并输出 `thought_image`

首版刻意不包含：

- `Google Search grounding`
- `Image Search grounding`
- 会话历史 / thought signatures 续传
- SDK 依赖、代理层、第三方 prompt operation 封装

## 参数说明

### Client

- `api_key`
- `request_timeout`

鉴权优先级固定为：

1. Client 节点内填写的 `api_key`
2. 环境变量 `GEMINI_API_KEY`
3. 当前仓库根目录下的 `config.ini`

### Nano Banana

- `client`
- `prompt`
- `images` 可选
- `aspect_ratio`
- `response_mode`

### Nano Banana 2

- `client`
- `prompt`
- `images` 可选
- `aspect_ratio`
- `response_mode`
- `resolution`
- `thinking_level`
- `include_thoughts`

### Nano Banana Pro

- `client`
- `prompt`
- `images` 可选
- `aspect_ratio`
- `response_mode`
- `resolution`
- `thinking_level`

## 模型差异

| 节点 | 分辨率 | Thinking | 备注 |
| --- | --- | --- | --- |
| Nano Banana | 不开放 | 不开放 | 首版最多 3 张输入参考图 |
| Nano Banana 2 | `1K` `2K` `4K` | `minimal` `low` `medium` `high` | 可输出 `thought_image` |
| Nano Banana Pro | `1K` `2K` `4K` | `low` `high` | 面向高保真资产制作 |

补充说明：

- `response_mode` 默认为 `IMAGE+TEXT`
- `aspect_ratio=auto` 时不显式写入 `imageConfig.aspectRatio`
- `response_json` 会保留原始结构，但会把返回里的 base64 图片数据替换成占位文本，避免字符串输出过大
- 如果 `Nano Banana 2` 未返回 thought 图，`thought_image` 会输出一个占位黑图张量

## 安装

### 手动安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/magicwang1111/ComfyUI-Nanobanana.git
cd ComfyUI-Nanobanana
python -m pip install -r requirements.txt
```

### API Key

你可以任选一种方式配置：

- 在 `ComfyUI-Nanobanana Client` 节点里填写 `api_key`
- 设置环境变量 `GEMINI_API_KEY`
- 在 [config.ini](./config.ini) 中填写

```ini
[API]
GEMINI_API_KEY = your_key_here
```

## 示例工作流

示例工作流位于 [examples/README.md](./examples/README.md)：

- `01_comfyui_nanobanana_nano_banana.json`
- `02_comfyui_nanobanana_nano_banana_2.json`
- `03_comfyui_nanobanana_nano_banana_pro.json`

## 测试

运行单元测试：

```bash
python -m unittest discover -s tests -v
```

## 已知限制

- v1 只支持单次请求，不保存会话 thought signatures
- 不做 grounding，因此不会返回来源链接或搜索元数据
- 节点对输入图像数量做了保守上限控制：`Nano Banana` 最多 3 张，`Nano Banana 2/Pro` 最多 14 张
- `Nano Banana Pro` 官方强调 Thinking 能力，但首版只暴露单轮 `thinking_level`

## 参考

- Google AI for Developers: https://ai.google.dev/gemini-api/docs/image-generation
- Gemini 3 guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
