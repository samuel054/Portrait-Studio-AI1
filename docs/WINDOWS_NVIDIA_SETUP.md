# Windows 11 setup with an NVIDIA RTX GPU

This walkthrough is a starting configuration for an RTX GPU with 8 GB of dedicated VRAM and about 32 GB of system RAM. It keeps the existing SDXL workflow. Actual speed, memory use, and likeness must be checked on the target PC.

Windows Task Manager shows both current usage and capacity: "1.3/8.0 GB dedicated GPU memory" means 8 GB capacity. Shared GPU memory is system RAM, not additional memory on the graphics card.

## 1. Start ComfyUI

1. Open the [official ComfyUI Portable for Windows page](https://docs.comfy.org/installation/comfyui_portable_windows).
2. Choose the NVIDIA RTX package. At the time this guide was checked, the RTX package uses CUDA 13.0 and Python 3.13.
3. Extract the archive completely using 7-Zip, for example into a folder under C:\AI. Open the extracted ComfyUI_windows_portable folder.
4. Double-click **run_nvidia_gpu.bat**. Leave its terminal open.
5. Open **http://127.0.0.1:8188** in your browser. The ComfyUI interface should appear.

If a terminal error appears, keep it open and copy the error text. Launching the interface confirms startup, but a model generation is still needed to verify inference.

ComfyUI Portable includes its own Python environment. The separate Portrait Studio API below uses its own virtual environment.

## 2. Add the portrait model

Open [Stability AI's SDXL files](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main) and download **sd_xl_base_1.0.safetensors** (about 6.94 GB). Put that exact file inside:

~~~text
ComfyUI_windows_portable\ComfyUI\models\checkpoints\
~~~

Restart ComfyUI. The bundled Portrait Studio workflow needs the base checkpoint only. Additional refiner models and custom nodes are unnecessary for this first test.

## 3. Install Portrait Studio

Install the Python 3.12, Node.js 22, and Git prerequisites described in [Local setup](LOCAL_SETUP.md), then reopen PowerShell.

For a new checkout, run these commands in the folder where you want to keep the project:

~~~powershell
git clone --branch codex/finish-portrait-studio-mvp --single-branch https://github.com/samuel054/Portrait-Studio-AI1.git
cd Portrait-Studio-AI1
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe scripts/setup_identity_models.py
npm --prefix frontend ci
.\.venv\Scripts\python.exe scripts/run_local.py
~~~

This explicitly downloads app dependencies and about 39 MB of face-checking model files. The commands preserve an existing .env file. For an existing checkout, update the review branch while preserving any local edits rather than cloning over it.

Open **http://127.0.0.1:3000**. Keep both the app terminal and ComfyUI terminal open.

The example configuration connects to ComfyUI at port 8188 and uses the checkpoint filename above. If your existing configuration uses another address or model, check those settings in .env.

## 4. First portrait

Press **Check connection** and wait for **Image engine ready**. Then use:

| Option | First test |
| --- | --- |
| Photo | One clear, front-facing person |
| Style | Soft Lifestyle Illustration |
| Framing | Keep photo framing |
| Background | Keep background |
| Use | Social profile |
| Candidates | 2 portraits |

Press **Generate portraits**. The bundled workflow processes about one megapixel while preserving aspect ratio; it does not send the full camera resolution to the sampler.

Inspect the passing options and confirm one explicitly. Prepare and download a PNG. Then try one finishing touch and inspect the face again. Use three or four candidates only after this first test succeeds.

If no portrait passes, save the visible error text and try a clearer original. Keep the likeness checks enabled: a completed generation alone is not a successful portrait.

## If graphics memory runs out

Close other applications that are using substantial GPU memory and keep the candidate count at two. If the problem persists, stop ComfyUI and open PowerShell in the ComfyUI_windows_portable folder. Run:

~~~powershell
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --lowvram --preview-method none
~~~

These are ComfyUI's documented [memory-saving options](https://docs.comfy.org/troubleshooting/overview). They can trade speed for memory. If errors remain, share the terminal error before changing model or dependency versions.

## Repeatable acceptance check

Once the first portrait succeeds, use the app's virtual environment from the project folder:

~~~powershell
.\.venv\Scripts\python.exe scripts/smoke_portrait.py "C:\Photos\portrait.jpg" --no-refine
~~~

Replace the example photo path with your own. Remove the final --no-refine flag to include refinement in the next test. The script chooses the recommended candidate automatically for this test and writes PNG, JPEG, and WebP files under artifacts\smoke.

Review those images yourself. GPU compatibility does not establish portrait likeness. Read [Privacy and limits](PRIVACY_AND_LIMITS.md) for session expiry and ComfyUI's separate saved input/output files.
