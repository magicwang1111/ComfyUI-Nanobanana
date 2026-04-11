# ComfyUI-Nanobanana Examples

本目录包含 3 个可导入的 ComfyUI workflow JSON。

## 使用前

- 先在仓库根目录创建并填写 `config.local.json`
- 可以直接复制根目录的 `config.example.json` 作为模板
- 如果 workflow 包含参考图，请先把占位输入图换成你自己的 ComfyUI `Load Image`
- `response_mode` 默认使用 `IMAGE+TEXT`，更方便排查 API 返回

## 包含内容

- `01_comfyui_nanobanana_nano_banana.json`
  基础 `Nano Banana` 文生图 workflow
- `02_comfyui_nanobanana_nano_banana_2.json`
  `Nano Banana 2` 单图参考编辑 workflow，带 `include_thoughts`
- `03_comfyui_nanobanana_nano_banana_pro.json`
  `Nano Banana Pro` 高保真多图参考 workflow
