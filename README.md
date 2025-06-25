# FoundationPose REST-API (Flask)

This micro-service exposes NVIDIA **FoundationPose** through a single HTTP POST
endpoint.  
It receives a calibrated RGB-D snapshot + object mesh, runs pose estimation,
and returns the 4 × 4 object-in-camera transform.

-------------------------------------------------------------------------------

## 1. Environment

| variable | description |
|----------|-------------|
| DIR      | **Absolute** path to the *root* of your FoundationPose checkout. Must contain `weights/`, `run_demo.py`, `debug/`, … |

export DIR=/home/user/FoundationPose
python pose_api_server.py     # server starts on http://localhost:5000

-------------------------------------------------------------------------------

## 2. Endpoint

POST /foundationpose  
Content-Type: application/json

### 2.1 Request body
```
{
  "camera_matrix": [[fx,0,cx],[0,fy,cy],[0,0,1]],   // 3×3 intrinsics

  "images": [
    {
      "filename": "frame_000",
      "rgb":   "<base-64 PNG>",   // colour image
      "depth": "<base-64 PNG>"    // 16-bit depth (m or mm)
    }
  ],

  "mask": "<base-64 PNG>",        // single-channel object mask
  "mesh": "<base-64 PLY>",        // object mesh in PLY format

  /* optional — ignored right now */
  "depthscale": 0.001             // set if depth is stored in mm
}
```
(All base-64 values are raw binary files, not JSON-escaped.)

### 2.2 Response codes

code | meaning                               | payload
-----|---------------------------------------|---------------------------------------------------------
200  | success                               | <code>{ "status": "...", "transformation_matrix": [[...]] }</code>
401  | empty body / not JSON                 | <code>{ "error": "Invalid or empty JSON!" }</code>
402  | JSON parse failed                     | <code>{ "error": "Invalid JSON format!", "details": "…" }</code>
403  | pose pipeline crashed                 | <code>{ "error": "Pose estimation failed", "details": "…" }</code>
500  | rotation matrix sanity check failed   | <code>{ "error": "Pose estimation error", "details": "…" }</code>

-------------------------------------------------------------------------------

## 3. Example (cURL)
```
curl -X POST http://localhost:5000/foundationpose \
     -H "Content-Type: application/json"          \
     -d @request.json | jq
```
`request.json` must follow the schema above  
(all binary blobs already base-64 encoded).

-------------------------------------------------------------------------------

## 4. Files created per request
```
$DIR/saved_requests/<uuid>/
  ├─ cam_K.txt
  ├─ rgb/    frame_000.png
  ├─ depth/  frame_000.png
  ├─ masks/  frame_000.png
  └─ mesh/   frame_000.ply
```
Pose result (row-major 4 × 4):
```
$DIR/debug/ob_in_cam/frame_000.txt
```
-------------------------------------------------------------------------------

## 5. GPU / memory notes

* FoundationPose allocates ≈ 3 GiB on first use and more during scoring.
* After each request the server frees everything not held by the model:

      torch.cuda.empty_cache()
      torch.cuda.ipc_collect()
      gc.collect()

* If CUDA-OOM persists, lower image resolution / batch size or use a GPU with
  **> 8 GiB** of VRAM.
