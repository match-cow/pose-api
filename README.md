# 6D Pose Estimation REST API (Flask)

This service provides a REST API for 6-DoF object pose estimation using RGB-D input and 3D object meshes.  
It exposes a single POST endpoint that performs pose inference and returns object-to-camera transforms as 4×4 SE(3) matrices.

The backend currently integrates **FoundationPose** by default.
Designed for standalone GPU servers, it loads models once and serves lightweight, repeatable pose estimation jobs.

-------------------------------------------------------------------------------

## 1. Environment

| Variable | Description |
|----------|-------------|
| DIR      | **Absolute path** to your FoundationPose **root** checkout. Must contain `weights/`, `run_demo.py`, `debug/`, etc. |

Example:
```
export DIR=/home/user/FoundationPose
python pose_api_server.py
```
Server runs at:
```
http://localhost:5000
```
Models are loaded once and reused. Flask reloader is off.

-------------------------------------------------------------------------------

## 2. Endpoint
```
POST /foundationpose  
Content-Type: application/json
```
### 2.1 Request body
```
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
- Only .ply mesh format supported.
- All images must have matching dimensions.

### 2.2 Response codes

| Code | Meaning                             | Payload |
|------|-------------------------------------|---------|
| 200  | Success                             | <code>{ "status": "...", "transformation_matrix": [ [4x4], … ] }</code> |
| 401  | Empty or invalid JSON               | <code>{ "error": "Invalid or empty JSON!" }</code> |
| 402  | Failed to parse JSON (nested str)   | <code>{ "error": "Invalid JSON format!", "details": "..." }</code> |
| 400  | Missing keys / bad base64           | <code>{ "error": "Invalid fields", "details": "..." }</code> |
| 403  | Pipeline crashed                    | <code>{ "error": "Pose estimation failed", "details": "..." }</code> |
| 500  | Matrix sanity check failed          | <code>{ "error": "Pose estimation error", "details": "..." }</code> |

Matrices are checked for orthogonality and determinant ≈ 1.

-------------------------------------------------------------------------------

## 3. Example (cURL)
```
curl -X POST http://localhost:5000/foundationpose \
     -H "Content-Type: application/json" \
     -d @request.json | jq
```
<code>request.json</code> must follow the schema above.  
Base64 fields must already be encoded PNG/PLY content.

-------------------------------------------------------------------------------

## 4. Per-request output
```
$DIR/saved_requests/<uuid>/
├── cam_K.txt
├── rgb/       scene1.png
├── depth/     scene1.png
├── masks/     scene1.png
└── mesh/      scene1.ply    (converted mm → m)
```
Pose result:

<code>$DIR/debug/ob_in_cam/scene1.txt</code>

Each file is a 4 × 4 transformation matrix, row-major.

-------------------------------------------------------------------------------

## 5. Runtime / GPU notes

- Models are loaded once (scorer, refiner, rasterizer).
- Approximate peak VRAM usage:
    3.3 GB (static) + 2.6 GB (temp) = ~5.9 GB
- Mesh scale is auto-converted using trimesh.apply_scale(0.001)
- After each request:
```
torch.cuda.empty_cache()
torch.cuda.ipc_collect()
gc.collect()
```
- Server works on 8 GB GPU (1 job at a time).
- For lower memory use, reduce image size or batch count.

-------------------------------------------------------------------------------

## 6. Known limitations

- Only one object per request (mask + mesh).
- Mesh must be .ply format.
- Only tested with FoundationPose under $DIR layout.
- Flask dev server used, switch to gunicorn for production.

-------------------------------------------------------------------------------
