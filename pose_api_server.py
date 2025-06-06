from flask import Flask, request, jsonify
import os
import uuid
import base64
import json

app = Flask(__name__)

@app.route("/")
def index():
    return "it is running!"

@app.route("/pose/estimate", methods = ['POST'])
def pose_estimate():
    data = request.get_json()
    if not data:
        return jsonify({"error":"Invalid or empty JSON!"}), 400
    
    request_id = str(uuid.uuid4())
    base = os.path.join("saved_requests", request_id)
    os.makedirs(os.path.join(base, "rgb"), exist_ok = True)
    os.makedirs(os.path.join(base, "depth"), exist_ok = True)
    os.makedirs(os.path.join(base, "mask"), exist_ok = True)
    os.makedirs(os.path.join(base, "mesh"), exist_ok = True)

    came_k_path = os.path.join(base, "came_K.txt")
    with open(came_k_path, "w") as f:
        for row in data['camera_matrix']:
            f.write(f"{row[0]} {row[1]} {row[2]}\n")
    
    for img in data['images']:
        filename = img['filename']
        rgb_data = base64.b64decode(img['rgb'])
        depth_data = base64.b64decode(img['depth'])

        with open(os.path.join(base, "rgb", filename + ".png"), "wb") as f:
            f.write(rgb_data)
        with open(os.path.join(base, "depth", filename + ".png"), "wb") as f:
            f.write(depth_data)
    
    mask_data = base64.b64decode(data['mask'])
    with open(os.path.join(base, "mask", "masks.png"), "wb") as f:
        f.write(mask_data)

    mesh = data['mesh']
    with open(os.path.join(base, "mesh", "model.obj"), "wb") as f:
        f.write(base64.b64decode(mesh['obj']))
    with open(os.path.join(base, "mesh", "model.mtl"), "wb") as f:
        f.write(base64.b64decode(mesh['mtl']))
    with open(os.path.join(base, "mesh", "texture.png"), "wb") as f:
        f.write(base64.b64decode(mesh['texture']))
        
if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 30823, debug = True)