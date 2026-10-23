# MinerU 文档解析模型

通用文件入口使用 [MinerU 4.0.12](https://github.com/opendatalab/MinerU) 的本地 SDK。PDF、Office 和图片的版面解析在独立容器完成；扫描页和图片使用 Basic ONNX CPU 档位，并进入整版本待复核。运行时不使用 MinerU 云端 API。MinerU 本身的许可与模型仓库许可应分别按上游发布内容核对。

模型权重不进入 Git。开发验证可将 Basic ONNX 模型下载到本目录的 `models/`，容器挂载整个目录到 `/opt/mineru`；staging 使用仓库外 `MINERU_ASSET_DIR`，推荐 `/home/crmdeploy/assets/mineru`，只读挂载。目录结构必须包含 `models/MinerU-4_models_onnx/`。下载与核验命令在 `src/deploy/staging/rootless/README.md`，以镜像固定版本和实际模型校验结果为准。
