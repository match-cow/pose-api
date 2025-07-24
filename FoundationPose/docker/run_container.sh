docker rm -f foundationpose
DIR=$(pwd)/../
docker run --gpus all --env NVIDIA_DISABLE_REQUIRE=1 -it --network=host --name foundationpose --cap-add=SYS_PTRACE --security-opt seccomp=unconfined -v $DIR:$DIR -v /home:/home -v /mnt:/mnt -v /tmp:/tmp --ipc=host foundationpose:latest bash -c "cd $DIR && export DIR=$(pwd) && nohup /opt/conda/envs/my/bin/python3 /home/meng/6d_pose_estimation_with_api/pose_api_server.py > pose_api.log 2>&1 & bash"
