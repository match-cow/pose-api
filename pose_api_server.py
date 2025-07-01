from flask import Flask, request, jsonify
import numpy as np
import os, uuid, base64, json, sys, traceback, trimesh, io
import gc
import torch

# make FoundationPose importable, assume under same parent directory, change as needed\
sys.path.append(os.path.join(".", "FoundationPose"))
from run_demo import run_pose_estimation

app = Flask(__name__)

# root FoundatoinPose folder that holds weights, debug/, run_demo, etc.
FOUNDATION_POSE_DIR = os.environ["DIR"]


@app.route("/")
def index():
    return "it is running!"


@app.route("/foundationpose", methods=["POST"])
def foundationpose():
    # Stage 1: read and sanity-check input
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or empty JSON!"}), 401

    try:
        # handle the case where the body was sent as a JSON-encoded string
        if isinstance(data, str):
            data = json.loads(data)

        # auto-parse nested JSON strings (often happens with form posts)
        for key in ["camera_matrix", "images", "mesh"]:
            if (
                key in data
                and isinstance(data[key], str)
                and data[key].lstrip()[:1] in ("{", "[")
            ):
                data[key] = json.loads(data[key])
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Invalid JSON format!", "details": str(e)}), 402

    os.makedirs(os.path.join(FOUNDATION_POSE_DIR, "saved_requests"), exist_ok=True)

    # Stage 2: save files on disk
    request_id = str(uuid.uuid4())
    base = os.path.join(FOUNDATION_POSE_DIR, "saved_requests", request_id)
    os.makedirs(os.path.join(base, "rgb"), exist_ok=True)
    os.makedirs(os.path.join(base, "depth"), exist_ok=True)
    os.makedirs(os.path.join(base, "masks"), exist_ok=True)
    os.makedirs(os.path.join(base, "mesh"), exist_ok=True)

    # save intrinsics
    came_k_path = os.path.join(base, "cam_K.txt")
    with open(came_k_path, "w") as f:
        for row in data["camera_matrix"]:
            f.write(f"{row[0]} {row[1]} {row[2]}\n")

    # save images and depth
    for img in data["images"]:
        filename = img["filename"]
        rgb_data = base64.b64decode(img["rgb"])
        depth_data = base64.b64decode(img["depth"])

        with open(os.path.join(base, "rgb", filename + ".png"), "wb") as f:
            f.write(rgb_data)
        with open(os.path.join(base, "depth", filename + ".png"), "wb") as f:
            f.write(depth_data)

    # save mask
    mask_data = base64.b64decode(data["mask"])
    with open(os.path.join(base, "masks", filename + ".png"), "wb") as f:
        f.write(mask_data)

    # save mesh along converting milimeter to meter
    mesh_bytes = base64.b64decode(data["mesh"])
    tm = trimesh.load(io.BytesIO(mesh_bytes), file_type='ply')
    tm.apply_scale(0.001)
    scaled_bytes = tm.export(file_type='ply')

    with open(os.path.join(base, "mesh", filename + ".ply"), "wb") as f:
        f.write(scaled_bytes)

    # Stage 3: call FoundationPose
    try:
        run_pose_estimation(
            test_scene_dir=base,
            mesh_file=os.path.join(base, "mesh", filename + ".ply"),
            debug_dir=os.path.join(FOUNDATION_POSE_DIR, "debug"),
        )
    except Exception as e:
        # print error in terminal and return error json on failure
        traceback.print_exc()
        return jsonify({"error": "Pose estimation failed", "details": str(e)}), 403
    finally:
        # free GPU memory for the next request
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        gc.collect()

    # Stage 4: read result matrix
    matrix_path = os.path.join(
        FOUNDATION_POSE_DIR, "debug", "ob_in_cam", filename + ".txt"
    )

    with open(matrix_path, "r") as f:
        matrix_lines = f.readlines()

    matrix = []
    for line in matrix_lines:
        stripped_line = line.strip()
        row_values = stripped_line.split()
        float_values = list(map(float, row_values))
        matrix.append(float_values)

    # validity check on rotation block
    rotation_matrix = np.array(matrix)[:3, :3]
    identity_matrix = np.eye(3)

    is_orthogonal = np.allclose(
        rotation_matrix.T @ rotation_matrix, identity_matrix, atol=1e-5
    )
    has_valid_determinant = np.isclose(np.linalg.det(rotation_matrix), 1.0, atol=1e-3)

    if not (is_orthogonal and has_valid_determinant):
        # return error for invalid transformation matrix
        return (
            jsonify(
                {
                    "error": "Pose estimation error",
                    "details": "Pose estimation returned an invalid rotation matrix",
                }
            ),
            500,
        )

    # return success transformation matrix json
    return (
        jsonify(
            {"status": "Pose estimation complete", "transformation_matrix": matrix}
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

