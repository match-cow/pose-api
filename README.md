# 6D Pose Estimation REST API (Flask + Docker)

This backend provides a REST API for 6-DoF object pose estimation using RGB-D input and a 3D object mesh. It runs inference on a GPU server and returns object-to-camera transformations as 4×4 SE(3) matrices. The backend is general-purpose and modular, with **FoundationPose** currently integrated by default. Additional models can be added with minimal changes.

---

## 1. Overview

- Input: RGB images, depth maps, a binary segmentation mask, camera intrinsics, and a 3D mesh — all base64-encoded
- Output: 4×4 object-to-camera transformation matrices, one per image frame
- Interface: JSON-over-HTTP via REST
- Runtime: Docker container on a single-GPU machine
- Jobs: One object per request; multiple frames supported

The backend loads the model once at server start and processes one job at a time. Outputs are stored in structured directories for reproducibility.

---

## 2. Repository Structure

```
pose-api/
├── FoundationPose/                 # Modified version of FoundationPose
│   ├── docker/
│   │   └── run_container.sh        # Docker runner script
│   ├── run_demo.py                 # Integration entry point
│   ├── weights/                    # Pre-downloaded FoundationPose weights
│   ├── debug/                      # Output pose matrices saved here
│   └── ...
├── pose_api_server.py              # Flask API wrapper
└── README.md
```

> A modified copy of [FoundationPose](https://github.com/NVlabs/FoundationPose) is included under `FoundationPose/`, with pretrained weights in `FoundationPose/weights/`.

---

## 3. Clone This Repository

```bash
git clone https://github.com/match-now/pose-api.git
```

---

## 4. Build and Run (Docker)

### 4.1 Build Docker Image

```bash
docker build -t foundationpose:latest .
```

### 4.2 Start the Server

```bash
cd pose-api/FoundationPose
bash docker/run_container.sh
```

This:
- Starts the Flask API server inside a GPU-enabled Docker container
- Mounts the project directory
- Sets the environment variable `DIR`
- Runs the server in the background

Server will be available at:

```
http://localhost:5000
```

Logs will be written to:

```
pose-api/
└── pose_api.log
```

---

## 5. API Usage

### 5.1 Endpoint

```
POST /foundationpose
Content-Type: application/json
```

### 5.2 Input Format

```json
{
  "camera_matrix": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
  "images": [
    {
      "filename": "scene1",
      "rgb": "<base64 encoded PNG>",
      "depth": "<base64 encoded PNG>"
    }
  ],
  "mask": "<base64 encoded PNG>",
  "mesh": "<base64 encoded PLY>"
}
```

Notes:
- All base64 fields must contain raw binary (not escaped)
- Only `.ply` mesh format is currently supported
- All images must match in resolution
- Supports multiple frames per request (single object assumed)

---

### 5.3 Example Request (cURL)

```bash
curl -X POST http://localhost:5000/foundationpose \
     -H "Content-Type: application/json" \
     -d @request.json | jq
```

---

## 6. Output

### 6.1 JSON Response

```json
{
  "status": "Pose estimation complete",
  "transformation_matrix": [
    [[...4x4 values...]],
    ...
  ]
}
```

Each 4×4 matrix corresponds to one image frame.

Matrices are checked for:
- Orthogonality (RᵀR ≈ I)
- Determinant ≈ 1

---

### 6.2 Saved Output Files

Saved under:

```
$DIR/saved_requests/<uuid>/
├── cam_K.txt
├── rgb/scene1.png
├── depth/scene1.png
├── masks/scene1.png
└── mesh/scene1.ply
```

Pose matrix per frame:

```
$DIR/debug/ob_in_cam/scene1.txt
```

---

## 7. Runtime Behavior

- Models are loaded once at server startup:
  - Score predictor
  - Pose refiner
  - CUDA rasterizer
- Meshes are automatically scaled from mm to meters:
  ```python
  trimesh.apply_scale(0.001)
  ```
- After each request:
  ```python
  torch.cuda.empty_cache()
  torch.cuda.ipc_collect()
  gc.collect()
  ```

### Approximate GPU usage:
- ~3.3 GB static (model and renderer)
- ~2.6 GB dynamic (per request)
- Stable on 8 GB GPUs (single job at a time)

---

## 8. Error Handling

| Code | Meaning                             | Payload |
|------|-------------------------------------|---------|
| 200  | Success                             | `{ "status": "...", "transformation_matrix": [...] }` |
| 400  | Malformed or incomplete fields      | `{ "error": "Invalid fields", "details": "..." }` |
| 401  | Invalid or missing JSON             | `{ "error": "Invalid or empty JSON!" }` |
| 402  | Failed to parse nested JSON strings | `{ "error": "Invalid JSON format!", "details": "..." }` |
| 403  | Inference failure                   | `{ "error": "Pose estimation failed", "details": "..." }` |
| 500  | Matrix validation failed            | `{ "error": "Pose estimation error", "details": "..." }` |

---

## 9. Limitations

- One object per request (mask and mesh shared across all frames)
- Only `.ply` mesh format supported
- No CPU fallback — GPU is required
- Flask development server is not production-grade (use `gunicorn` if needed)
- Currently integrated with FoundationPose; architecture allows for plugging in others

---

## 10. Attribution

This backend integrates a modified version of [FoundationPose](https://github.com/NVlabs/FoundationPose):

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

If using this system in research, please cite the original work.

---
