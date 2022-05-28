from cv2 import cv2 as cv2
from PIL import Image
import imagehash
import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def isSimilar(frame1, frame2):
    # OpenCV图片转换为PIL image
    frame1 = Image.fromarray(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))  
    frame2 = Image.fromarray(cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)) 

    # 通过imagehash获取两个图片的平均hash值
    n0 = imagehash.average_hash(frame1) 
    n1 = imagehash.average_hash(frame2) 

    # 阈值
    cutoff = 8

    return abs(n0 - n1) < cutoff

def analysisVideo(clip, fps):
    im0 = ""            # 目标帧
    success_durations = []  # 成功片段时间列表
    slice_points = [ 0 ]
    frame_count = int(clip.duration * clip.fps)
    bar = tqdm(total=frame_count, desc=f'正在分析视频：')

    def analysis(img0, img1, time):
        result = isSimilar(img0, img1)
        if not result:  # 结果为不相似
            slice_points.append(time)
        bar.update(1)

    with ThreadPoolExecutor() as p:
        futures = []
        for i,img in enumerate(clip.iter_frames(fps)):
            if i == 0: im0 = img
            time = (i) / fps
            futures.append(p.submit(analysis, im0, img, time))
            im0 = img
        as_completed(futures)
    bar.close()

    curr = 0
    prev = 0
    start = 0
    for time in slice_points:
        prev = curr
        curr = time
        if curr - prev < 5:
            continue
        s = str(datetime.timedelta(seconds=start)).zfill(8)
        e = str(datetime.timedelta(seconds=time)).zfill(8)
        print(s, e)
        success_durations.append([start, time])
        start = time
    return success_durations

def doSlice(clip, success_durations):
    for [s, e] in success_durations:
        filename = clip.filename.replace(".mp4", f"_{s}_{e}.mp4")
        clip.subclip(s, e).write_videofile(filename)
