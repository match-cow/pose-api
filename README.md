# 6D Pose Estimation REST API (Flask + Docker)

This backend provides a REST API for 6-DoF object pose estimation using RGB-D input and a 3D object mesh. It runs inference on a GPU server and returns object-to-camera transformations as 4×4 SE(3) matrices. The backend is general-purpose and modular, with **FoundationPose** currently integrated by default. Additional models can be added with minimal changes.

---

## 1. Overview

- Input: RGB images, depth maps, a binary segmentation mask, camera intrinsics, and a 3D mesh — all base64-encoded
- Output: 4×4 object-to-camera transformation matrices (SE3), one per image frame
- Interface: JSON-over-HTTP via REST
- Runtime: Docker container on a single-GPU machine
- Job unit: One object (mesh + mask) per request; multiple frames allowed

The server loads the model once and processes jobs one at a time. All job data and results are saved for reproducibility.

---

## 2. Repository Structure

```
pose-api/
├── FoundationPose/                 # Modified FoundationPose for backend use
│   ├── docker/
│   │   └── run_container.sh        # Starts container and API server
│   ├── run_demo.py                 # Entrypoint used by server
│   ├── weights/                    # Preloaded FoundationPose model weights
│   ├── debug/                      # Output SE(3) matrices go here
│   └── ...
├── pose_api_server.py              # Flask API implementation
└── README.md
```

> A modified copy of [FoundationPose](https://github.com/NVlabs/FoundationPose) is included under `FoundationPose/`, with pretrained weights in `FoundationPose/weights/`.

---

## 3. Setup Instructions

### 3.1 Clone This Repository

```bash
git clone https://github.com/match-now/pose-api.git
cd pose-api
```

Everything you need is already included (no external downloads required).

---

### 3.2 Build the Docker Image

Make sure you are in the **`pose-api/` root** when running this:

```bash
docker build -t foundationpose:latest .
```

This creates a Docker image with all dependencies for running the server and FoundationPose inside.

---

### 3.3 Run the Server Inside Docker

Now switch into the folder where the run script lives:

```bash
cd FoundationPose
bash docker/run_container.sh
```

This:
- Starts a Docker container with GPU access
- Mounts the current folder inside the container
- Sets the environment variable `DIR` (used by the backend code)
- Runs the Flask API server in the background

You should now see the server running at:

```
http://localhost:5000
```

If successful, it will respond to:

```bash
curl http://localhost:5000
```

And print:

```
it is running!
```

---

## 4. API Usage

### 4.1 Endpoint

```
POST /foundationpose
Content-Type: application/json
```

This endpoint processes one job (one object across multiple frames) and returns 4×4 pose matrices.

---

### 4.2 Input Format

```json
{
  "camera_matrix": [
    ["fx", 0, "cx"],
    [0, "fy", "cy"],
    [0, 0, 1]
  ],
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
- All fields must be base64-encoded raw binary
- `.ply` mesh format only
- Image size must match across RGB, depth, and mask
- Currently assumes one object per request (mask + mesh apply to all frames)

Optional field:

```json
"depthscale": 0.001
```

*(Not currently used but included for future scaling support.)*

---

### 4.3 Example Request (cURL)

Prepare a `request.json` following the format above, and run:

```bash
curl -X POST http://localhost:5000/foundationpose \
     -H "Content-Type: application/json" \
     -d @request.json | jq
```

Tip: If you don’t want to handcraft a test file, modify one of the saved request folders from a previous run and re-encode the files using Python.

---

## 5. Output Format

### 5.1 JSON Response

```json
{
  "status": "Pose estimation complete",
  "transformation_matrix": [
    [
      ["r11", "r12", "r13", "tx"],
      ["r21", "r22", "r23", "ty"],
      ["r31", "r32", "r33", "tz"],
      [0, 0, 0, 1]
    ],
    ...
  ]
}

```

Each matrix corresponds to a frame. This matrix maps the object coordinates to the camera frame — it’s an SE(3) transform in row-major order.

Pose validity is checked before returning:
- Rotation block must be orthogonal (RᵀR ≈ I)
- Determinant of rotation ≈ 1

---

### 5.2 Output Directory Structure

Each job is saved in:

```
pose-api/
├── FoundationPose/
│   └── saved_requests/
│       └── <uuid>/
│           ├── cam_K.txt
│           ├── rgb/scene1.png
│           ├── depth/scene1.png
│           ├── masks/scene1.png
│           └── mesh/scene1.ply
```

Estimated poses (one per frame):

```
pose-api/FoundationPose/debug/ob_in_cam/scene1.txt
```

---

## 6. Runtime and GPU Behavior

- Models are loaded once at server startup:
  - Score predictor
  - Pose refiner
  - CUDA rasterizer
- Meshes are automatically scaled from mm → meters:
  ```python
  trimesh.apply_scale(0.001)
  ```
- After each job:
  ```python
  torch.cuda.empty_cache()
  torch.cuda.ipc_collect()
  gc.collect()
  ```

### GPU Memory Use

| Component         | Approx Usage |
|------------------|--------------|
| Static models     | ~3.3 GB      |
| Per job (dynamic) | ~2.6 GB      |
| Total typical     | ~5.9 GB      |

Runs comfortably on 8 GB GPUs (single request at a time).

---

## 7. Error Handling

| Code | Meaning                             | Payload |
|------|-------------------------------------|---------|
| 200  | Success                             | `{ "status": "...", "transformation_matrix": [...] }` |
| 400  | Malformed or incomplete fields      | `{ "error": "Invalid fields", "details": "..." }` |
| 401  | Missing or invalid JSON             | `{ "error": "Invalid or empty JSON!" }` |
| 402  | Failed to parse nested JSON strings | `{ "error": "Invalid JSON format!", "details": "..." }` |
| 403  | Inference error                     | `{ "error": "Pose estimation failed", "details": "..." }` |
| 500  | Matrix validation failed            | `{ "error": "Pose estimation error", "details": "..." }` |

---

## 8. Limitations

- Only one object (mask + mesh) per request
- `.ply` mesh format only
- No CPU support — GPU required
- Flask dev server is not production-ready (use `gunicorn` for deployment)
- Only FoundationPose is integrated so far

---

## 9. Extending to Other Models

The backend is structured to support other 6D pose estimators. To add a model:
- Wrap your inference logic in a function like `run_pose_estimation()`
- Replace or branch from the call inside `pose_api_server.py`
- Keep the I/O interface (base64 input, matrix output) consistent

This structure allows adding lightweight wrappers for other model families (e.g., GDR-Net, CosyPose) without major refactoring.

---

## 10. Attribution

This backend integrates [FoundationPose](https://github.com/NVlabs/FoundationPose) by NVIDIA:

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

If using this backend in research, please cite their work.
