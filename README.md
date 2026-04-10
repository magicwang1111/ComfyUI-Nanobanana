# ComfyUI-Nanobanana

`ComfyUI-Nanobanana` 是一个直接封装 Gemini 原生 `generateContent` 图像接口的 ComfyUI 自定义节点包，支持：

- Google 官方 Gemini 原生直连
- 保留 Gemini 原生路径形态的中转站
- ComfyUI `IMAGE` 批量输入作为参考图
- 标准 `IMAGE` 输出，可直接接 `PreviewImage` / `SaveImage`
- `text` 与 `response_json` 调试输出

本项目当前只兼容 Gemini 原生格式：

- `POST /v1beta/models/{model}:generateContent`

本项目当前不兼容：

- `/v1/chat/completions`
- OpenAI Chat 兼容格式
- grounding、多轮会话、thought signature 续传

## 节点列表

- `ComfyUI-Nanobanana Client`
- `ComfyUI-Nanobanana Nano Banana`
- `ComfyUI-Nanobanana Nano Banana 2`
- `ComfyUI-Nanobanana Nano Banana Pro`

## 模型映射

- `Nano Banana` -> `gemini-2.5-flash-image`
- `Nano Banana 2` -> `gemini-3.1-flash-image-preview`
- `Nano Banana Pro` -> `gemini-3-pro-image-preview`

## Client 参数

`ComfyUI-Nanobanana Client` 现在支持官方直连和 Gemini 原生中转站两种连接方式。

- `api_key`
- `request_timeout`
- `base_url`
- `auth_mode`
- `send_seed`

### auth_mode

- `x-goog-api-key`
  适用于 Google 官方 Gemini 原生接口
- `bearer`
  适用于要求 `Authorization: Bearer <token>` 的 Gemini 原生中转站

### send_seed

- `true`
  会透传 `generationConfig.seed`
- `false`
  不发送 `generationConfig.seed`

如果某个中转站返回 `Invalid value at 'generation_config.seed'`，请把 `send_seed` 关闭。

### 配置优先级

#### api_key

1. Client 节点中的 `api_key`
2. 环境变量 `NANOBANANA_API_KEY`
3. 环境变量 `GEMINI_API_KEY`
4. `config.ini` 中的 `NANOBANANA_API_KEY`
5. `config.ini` 中的 `GEMINI_API_KEY`

#### base_url

1. Client 节点中的 `base_url`
2. 环境变量 `NANOBANANA_BASE_URL`
3. `config.ini` 中的 `NANOBANANA_BASE_URL`
4. 默认值 `https://generativelanguage.googleapis.com`

#### auth_mode

1. Client 节点中的 `auth_mode`
2. 环境变量 `NANOBANANA_AUTH_MODE`
3. `config.ini` 中的 `NANOBANANA_AUTH_MODE`
4. 默认值 `x-goog-api-key`

#### send_seed

1. Client 节点中的 `send_seed`
2. 环境变量 `NANOBANANA_SEND_SEED`
3. `config.ini` 中的 `NANOBANANA_SEND_SEED`
4. 默认值 `true`

## 生成节点参数

三个生成节点都会保留原有本地能力校验，并新增一个用于中转站模型别名的参数：

- `model_override`

规则如下：

- 留空时，继续使用节点内置官方模型名
- 填值时，请求会发往覆盖后的模型名
- 本地参数校验仍按当前节点原始模型规格执行

### Nano Banana

- `client`
- `prompt`
- `seed`
- `images` 可选
- `aspect_ratio`
- `response_mode`
- `system_prompt`
- `model_override`

### Nano Banana 2

- `client`
- `prompt`
- `seed`
- `images` 可选
- `aspect_ratio`
- `response_mode`
- `system_prompt`
- `model_override`
- `resolution`
- `thinking_level`
- `include_thoughts`

### Nano Banana Pro

- `client`
- `prompt`
- `seed`
- `images` 可选
- `aspect_ratio`
- `response_mode`
- `system_prompt`
- `model_override`
- `resolution`
- `thinking_level`

## 中转站配置示例

### Google 官方直连

- `base_url = https://generativelanguage.googleapis.com`
- `auth_mode = x-goog-api-key`
- `send_seed = true`

### Gemini 原生中转站

- `base_url = https://your-relay.example.com`
- `auth_mode = bearer`
- `send_seed = true`
- 如中转站模型名与官方不同，可在生成节点里填写 `model_override`

如果中转站不接受 `generationConfig.seed`，把 `send_seed` 改成 `false` 即可。

例如：

```ini
[API]
NANOBANANA_API_KEY = your_token_here
NANOBANANA_BASE_URL = https://your-relay.example.com
NANOBANANA_AUTH_MODE = bearer
NANOBANANA_SEND_SEED = false
```

## 行为说明

- `response_mode` 默认是 `IMAGE+TEXT`
- `send_seed=true` 时才会透传 `generationConfig.seed`
- `aspect_ratio=auto` 时不会显式写入 `imageConfig.aspectRatio`
- `system_prompt` 默认是一段“始终产图”的图像生成提示词
- `response_json` 会保留原始返回结构，但会把 base64 图片数据替换为占位文本
- 响应解析兼容 `inlineData/mimeType` 与 `inline_data/mime_type`
- `Nano Banana 2` 若没有返回 thought 图，`thought_image` 会输出占位黑图

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/magicwang1111/ComfyUI-Nanobanana.git
cd ComfyUI-Nanobanana
python -m pip install -r requirements.txt
```

## 配置方式

你可以任选一种方式提供连接信息：

- 在 `ComfyUI-Nanobanana Client` 节点内填写
- 设置环境变量
- 修改仓库根目录下的 `config.ini`

## 示例工作流

示例 workflow 位于 [examples/README.md](./examples/README.md)：

- `01_comfyui_nanobanana_nano_banana.json`
- `02_comfyui_nanobanana_nano_banana_2.json`
- `03_comfyui_nanobanana_nano_banana_pro.json`

## 测试

```bash
python -m unittest discover -s tests -v
```

## 已知限制

- 只支持单次请求，不保存会话与 thought signatures
- 不兼容 `/v1/chat/completions`
- 不做 grounding，因此不会返回来源链接或搜索元数据
- 输入图像数量仍做保守限制：
  - `Nano Banana` 最多 3 张
  - `Nano Banana 2 / Pro` 最多 14 张

## 参考

- Google AI for Developers: https://ai.google.dev/gemini-api/docs/image-generation
- Gemini 3 guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
