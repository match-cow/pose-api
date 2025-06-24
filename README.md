# FoundationPose REST-API (Flask)

This micro-service exposes NVIDIA **FoundationPose** as a single HTTP POST
endpoint.  
It receives a calibrated RGB-D snapshot + object mesh, runs pose estimation
and returns the 4 × 4 object-in-camera transform.

---

## 1. Environment

| variable | description                                                                 |
|----------|------------------------------------------------------------------------------|
| `DIR`    | **Absolute** path to the *root* of your local FoundationPose checkout. Must contain<br>`weights/`, `run_demo.py`, `debug/`, etc. |

```bash
export DIR=/home/user/FoundationPose
python pose_api_server.py   # launches on port 5000

2. Endpoint

POST /foundationpose
Content-Type: application/json

2.1 Request body

{
  "camera_matrix": [[fx,0,cx],[0,fy,cy],[0,0,1]],   // 3×3 intrinsics
  "images": [
    {
      "filename": "frame_000",
      "rgb":   "<base-64 PNG>",    // encoded 3-channel colour image
      "depth": "<base-64 PNG>"     // encoded 16-bit depth (metres or mm, same as demo data)
    }
  ],
  "mask": "<base-64 PNG>",        // single-channel object mask, same res as RGB
  "mesh": "<base-64 PLY>",        // object mesh in PLY format
  /* optional, ignored by the server right now
  "depthscale": 0.001            // if depth is stored in mm instead of m
  */
}

All base-64 values are raw binary PNG files, not JSON-escaped data.
2.2 Response
code	meaning	payload
200	success	{ "status": "...", "transformation_matrix": [[...16 numbers...]] }
401	empty body / not JSON	{ "error": "Invalid or empty JSON!" }
402	JSON could not be parsed	{ "error": "Invalid JSON format!", "details": ... }
403	pose pipeline crashed (see details)	{ "error": "Pose estimation failed", "details": ... }
500	rotation matrix sanity-check failed	{ "error": "Pose estimation error", "details": ... }
3. Example (cURL)

curl -X POST http://localhost:5000/foundationpose \
     -H "Content-Type: application/json"            \
     -d @request.json | jq

Where request.json is a file that follows the structure above
(all binary blobs base-64 encoded).
4. Filesystem layout per request

For every call a unique folder is spawned under:

$DIR/saved_requests/<uuid>/
  ├─ cam_K.txt
  ├─ rgb/    frame_000.png
  ├─ depth/  frame_000.png
  ├─ masks/  frame_000.png
  └─ mesh/   frame_000.ply

Results are emitted to
$DIR/debug/ob_in_cam/frame_000.txt (16 floats, row-major 4×4).
5. GPU / Memory notes

    FoundationPose allocates ~3 GiB on first use and more during scoring.

    After every request the server executes

torch.cuda.empty_cache()
torch.cuda.ipc_collect()
gc.collect()

to release everything not held by the model.
If you still see CUDA out of memory, lower the input resolution,
batch size, or use a GPU with >8 GiB.