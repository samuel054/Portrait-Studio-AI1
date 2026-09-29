# Run Portrait Studio AI locally

This app has three parts: the website, the API, and ComfyUI. The face checker runs on a CPU; portrait generation is practical on a computer that can run SDXL. All image processing stays on the computer or the private GPU host you configure.

For Windows 11 with an NVIDIA RTX card and 8 GB of dedicated graphics memory, follow the [Windows setup walkthrough](WINDOWS_NVIDIA_SETUP.md). The website starts with two candidates to reduce the initial memory demand; three and four remain available.

## 1. Install the app

Install Python 3.12, Node.js 22, and Git. Open a terminal in the project directory.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python scripts/setup_identity_models.py
npm --prefix frontend ci
.\.venv\Scripts\python scripts/run_local.py
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
python3 scripts/setup_identity_models.py
npm --prefix frontend ci
.venv/bin/python scripts/run_local.py
```

Open **http://127.0.0.1:3000**. You can now test uploads and photo analysis. The website will explain which generation components are still missing. Keep the terminal open; Ctrl+C stops the app.

The setup script installs pinned OpenCV Zoo YuNet and SFace weights (about 39 MB total), verifies their SHA-256 checksums, and saves the upstream license files beside them. No face data is sent during this installation. The model paths default to `models/identity`.

## 2. Connect the image engine

1. Install and start [ComfyUI](https://docs.comfy.org/installation/overview) using the installation route for your hardware. Set its port to **8188** to match the example configuration, or change `COMFYUI_BASE_URL` to the port it reports.
2. Download `sd_xl_base_1.0.safetensors` from [Stability AI's SDXL model page](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0). Place it in ComfyUI's `models/checkpoints` directory. The checkpoint is a separate multi-gigabyte download.
3. Restart ComfyUI if needed. The bundled workflow uses core nodes: `LoadImage`, `ImageScaleToTotalPixels`, `VAEEncode`, `RepeatLatentBatch`, `KSampler`, `VAEDecode`, `SaveImage`, `CLIPTextEncode`, and `CheckpointLoaderSimple`.
4. In Portrait Studio, press **Check connection**. Both the checkpoint/workflow and the likeness checker must be ready before generation is enabled.

The app uses `workflows/portrait_api.json` in API format automatically. You do not need to import it into the ComfyUI editor. Its model, seed, batch size, reference image, and sampling strength are filled by the API.

For another compatible SDXL checkpoint, set `COMFYUI_CHECKPOINT` to its exact filename. For an identity-conditioned workflow, export an API-format graph and point `COMFYUI_WORKFLOW_PATH` at it. Preserve the tokens documented in the bundled workflow. A different model or identity adapter needs fresh likeness calibration.

## 3. Optional transparent and blurred backgrounds

```bash
python -m pip install -e '.[background]'
python scripts/setup_background_model.py
```

Use your virtual environment's Python (on Windows, `.venv\Scripts\python`). This explicitly downloads the small U2Net portrait-cutout model to `models/background`. Restart the API and press **Check connection**. The extra background buttons then become available. Check hair, glasses, and clothing edges before printing; the mask is model-generated.

PNG and WebP preserve transparency. JPEG uses a white background for transparent pixels.

## Docker alternative

Set up the model files on the host first, then:

```bash
cp .env.example .env
python scripts/setup_identity_models.py
docker compose up --build
```

ComfyUI still runs separately on the host. Docker uses `COMFYUI_DOCKER_BASE_URL=http://host.docker.internal:8188`. Models are mounted read-only, while app session databases use the `portrait-data` volume. Both web and API ports bind to localhost by default.

`docker-compose.prod.yml` builds the optimized website and requires `PORTRAIT_API_KEY`. That key is an API boundary, not a multi-user web login. This remains a local/single-user application; the compose file is not an authenticated public SaaS deployment.

## Real model check

Once the app says **Image engine ready**, use a portrait you have permission to process:

```bash
python scripts/smoke_portrait.py /absolute/path/to/portrait.jpg
```

The script uploads one portrait, waits for evaluated candidates, selects the recommended option for this smoke test, exports each format, and runs one refinement through the same evaluation path. Files are written to `artifacts/smoke` (ignored by Git). Use `--no-refine` for the shorter first check, or `--base-url` for another API address. It reports failure if no candidate passes. API keys can be passed through `PORTRAIT_API_KEY`.

Inspect the generated portraits yourself. An automatic pass is not proof of perfect likeness. The original project requested a consented photo set and human review before a model release; those quality gates still apply.

## Troubleshooting

- **Likeness model missing:** run `scripts/setup_identity_models.py` and check `PORTRAIT_IDENTITY_MODEL_DIR`.
- **Engine unavailable:** verify the ComfyUI port and that it is running. The website calls the API; it never calls ComfyUI directly.
- **Checkpoint missing:** use the exact filename, including its extension, in `COMFYUI_CHECKPOINT`.
- **Out of memory:** try two portraits first. SDXL memory needs vary with resolution and hardware. Use ComfyUI's documented memory options for your device.
- **No portrait passes:** try a sharper, front-facing original, original framing, and a gentler style. Rejected portraits are hidden rather than labeled successful.
- **Session expired:** upload again. Download finished portraits before the configured session timeout.

## Model sources and licenses

- [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet): MIT.
- [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface): Apache-2.0.
- [SDXL base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0): CreativeML Open RAIL++-M; follow the model card and license conditions.
- [U2Net](https://github.com/xuebinqin/U-2-Net): Apache-2.0; rembg installs its `u2netp` weights.
- The optional [InsightFace adapter](https://github.com/deepinsight/insightface#license) is retained for separately licensed models/research. Its commonly distributed pretrained weights are not the default commercial-use route.
