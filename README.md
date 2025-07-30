# 6D Pose Estimation REST API (Flask)

This service provides a REST API for 6-DoF object pose estimation using RGB-D input and 3D object meshes.  
It exposes a single POST endpoint that performs pose inference and returns object-to-camera transforms as 4×4 SE(3) matrices.

The backend currently integrates **FoundationPose** by default, with support for additional models planned.  
Designed for standalone GPU servers, it loads models once and serves lightweight, repeatable pose estimation jobs.

-------------------------------------------------------------------------------

## 0. Overview

This API enables pose estimation using calibrated RGB-D snapshots and a mesh model.

- Input: base64-encoded RGB, depth, mask, and PLY mesh
- Output: 4×4 object-to-camera transformation matrices (SE3)
- Runs directly on a single GPU server
- Models are preloaded and reused between requests

-------------------------------------------------------------------------------

## 1. Environment Setup

| Variable | Description |
|----------|-------------|
| `DIR`    | **Absolute path** to your pose estimation backend (must include `run_demo.py`, `weights/`, `debug/`, etc.) |

Example:

```bash
export DIR=/home/user/pose_backend
python pose_api_server.py
```

Server runs at:

```
http://localhost:5000
```

Models are loaded once and reused. Flask reloader is off.

-------------------------------------------------------------------------------

## 2. API Endpoint

```
POST /foundationpose
Content-Type: application/json
```

> Note: The endpoint path is named `/foundationpose` for legacy compatibility but can be changed in `pose_api_server.py`.

### 2.1 Request JSON

```json
{
  "camera_matrix": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],

  "images": [
    {
      "filename": "scene1",
      "rgb": "<base64 PNG>",
      "depth": "<base64 PNG>"
    }
  ],

  "mask": "<base64 PNG>",
  "mesh": "<base64 PLY>",

  "depthscale": 0.001    // optional, currently ignored
}
```

Notes:
- All base64 fields are raw binary (not escaped).
- Only `.ply` mesh format is supported.
- All images must have matching dimensions.

### 2.2 Response Codes

| Code | Meaning                             | Payload |
|------|-------------------------------------|---------|
| 200  | Success                             | `{ "status": "...", "transformation_matrix": [ [4x4], … ] }` |
| 401  | Empty or invalid JSON               | `{ "error": "Invalid or empty JSON!" }` |
| 402  | Failed to parse JSON (nested str)   | `{ "error": "Invalid JSON format!", "details": "..." }` |
| 400  | Missing keys / bad base64           | `{ "error": "Invalid fields", "details": "..." }` |
| 403  | Pipeline crashed                    | `{ "error": "Pose estimation failed", "details": "..." }` |
| 500  | Matrix sanity check failed          | `{ "error": "Pose estimation error", "details": "..." }` |

Matrices are checked for orthogonality and determinant ≈ 1.

-------------------------------------------------------------------------------

## 3. Example (cURL)

```bash
curl -X POST http://localhost:5000/foundationpose \
     -H "Content-Type: application/json" \
     -d @request.json | jq
```

`request.json` must follow the schema above.  
Base64 fields must already be encoded PNG/PLY content.

-------------------------------------------------------------------------------

## 4. Output Files (Per Request)

```
$DIR/saved_requests/<uuid>/
├── cam_K.txt
├── rgb/       scene1.png
├── depth/     scene1.png
├── masks/     scene1.png
└── mesh/      scene1.ply    (converted mm → m)
```

Pose result:

```
$DIR/debug/ob_in_cam/scene1.txt
```

Each file is a 4×4 transformation matrix (row-major).

-------------------------------------------------------------------------------

## 5. Runtime Behavior / GPU Notes

- Models are loaded once at server startup:
  - Score predictor
  - Refiner
  - Rasterizer
- Approximate GPU memory usage:
  - ~3.3 GB static + ~2.6 GB dynamic = ~5.9 GB
- Mesh scale is auto-converted via `trimesh.apply_scale(0.001)`
- After each request:

```python
torch.cuda.empty_cache()
torch.cuda.ipc_collect()
gc.collect()
```

- Works reliably on 8 GB GPUs with one request at a time.
- Lower memory use possible by reducing image size or batch count.

-------------------------------------------------------------------------------

## 6. Limitations

- Only one object per request (mask + mesh)
- Only `.ply` mesh format supported
- Only tested using FoundationPose backend under `$DIR` layout
- Uses Flask development server — not suitable for production use (consider `gunicorn` or similar)

-------------------------------------------------------------------------------

## 7. License / Attribution

This project integrates the [FoundationPose](https://github.com/NVlabs/FoundationPose) model for 6D pose estimation and tracking.  
If you use this system in research or development, please cite the original paper:

```bibtex
@article{wen2023foundationpose,
  title     = {FoundationPose: Unified 6D Pose Estimation and Tracking of Novel Objects},
  author    = {Bowen Wen and Wei Yang and Jan Kautz and Stan Birchfield},
  journal   = {arXiv preprint arXiv:2312.08344},
  year      = {2023},
  url       = {https://arxiv.org/abs/2312.08344},
  doi       = {10.48550/arXiv.2312.08344}
}
```

FoundationPose supports both model-based and model-free setups and enables pose estimation and tracking for novel objects without fine-tuning.

-------------------------------------------------------------------------------
