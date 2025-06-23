from flask import Flask, request, jsonify
import os
import uuid
import base64
import numpy as np

import subprocess

app = Flask(__name__)

FOUNDATION_POSE_DIR = os.environ["DIR"]


@app.route("/")
def index():
    return "it is running!"


@app.route("/pose/estimate", methods=["POST"])
def pose_estimate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or empty JSON!"}), 400

    request_id = str(uuid.uuid4())
    base = os.path.join("saved_requests", request_id)
    os.makedirs(os.path.join(base, "rgb"), exist_ok=True)
    os.makedirs(os.path.join(base, "depth"), exist_ok=True)
    os.makedirs(os.path.join(base, "masks"), exist_ok=True)
    os.makedirs(os.path.join(base, "mesh"), exist_ok=True)

    came_k_path = os.path.join(base, "cam_K.txt")
    with open(came_k_path, "w") as f:
        for row in data["camera_matrix"]:
            f.write(f"{row[0]} {row[1]} {row[2]}\n")

    for img in data["images"]:
        filename = img["filename"]
        rgb_data = base64.b64decode(img["rgb"])
        depth_data = base64.b64decode(img["depth"])

        with open(os.path.join(base, "rgb", filename + ".png"), "wb") as f:
            f.write(rgb_data)
        with open(os.path.join(base, "depth", filename + ".png"), "wb") as f:
            f.write(depth_data)

    mask_data = base64.b64decode(data["mask"])
    with open(os.path.join(base, "masks", filename + ".png"), "wb") as f:
        f.write(mask_data)

    mesh = data["mesh"]
    with open(os.path.join(base, "mesh", "model.obj"), "wb") as f:
        f.write(base64.b64decode(mesh["obj"]))
    with open(os.path.join(base, "mesh", "model.mtl"), "wb") as f:
        f.write(base64.b64decode(mesh["mtl"]))
    with open(os.path.join(base, "mesh", "texture.png"), "wb") as f:
        f.write(base64.b64decode(mesh["texture"]))

    mesh_file_path = os.path.join(base, "mesh", "model.obj")

    run_pose_command = [
        "python",
        os.path.join(FOUNDATION_POSE_DIR, "run_demo.py"),
        "--test_scene_dir",
        base,
        "--mesh_file",
        mesh_file_path,
    ]

    try:
        # result = subprocess.run(run_pose_command, capture_output = True, text = True, check = True)

        run_pose_estimation(
            test_scene_dir=base,
            mesh_file=os.path.join(base, "mesh", "model.obj"),
            debug_dir=os.path.join(FOUNDATION_POSE_DIR, "debug"),
        )
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Pose estimation failed", "details": e.stderr}), 500

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

    print(matrix)

    rotation_matrix = np.array(matrix)[:3, :3]
    identity_matrix = np.eye(3)

    is_orthogonal = np.allclose(
        rotation_matrix.T @ rotation_matrix, identity_matrix, rtol=1e-6
    )
    has_valid_determinant = np.isclose(np.linalg.det(rotation_matrix), 1.0, rtol=1e-4)

    if not (is_orthogonal and has_valid_determinant):
        return (
            jsonify(
                {
                    "error": "Pose estimation error",
                    "details": "Pose estimation returned an invalid rotation matrix",
                }
            ),
            500,
        )

    return jsonify(
        {"status": "Pose estimation complete", "transformation_matrix": matrix}
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=30823, debug=True)