import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tangdou, time, requests, re
import video_slice as slicer
from moviepy.editor import *
from headers import headers

from concurrent.futures import ThreadPoolExecutor, as_completed
# 用于显示进度条
from tqdm import tqdm
# 用于发起网络请求
import requests

def calc_divisional_range(filesize, chuck=10):
    step = filesize//chuck
    arr = list(range(0, filesize, step))
    result = []
    for i in range(len(arr)-1):
        s_pos, e_pos = arr[i], arr[i+1]-1
        result.append([s_pos, e_pos])
    result[-1][-1] = filesize-1
    return result

def download_multi_thread(url: str, file_name: str, chunk: int) -> None:
    # 先创建空文件
    with open(file_name, "wb") as f:
        pass

    # header
    header = headers(url).buildHeader()
    response = requests.get(url, headers=header, stream=True)
    content_size = int(response.headers['content-length'])  # Total download file size

    # 下载方法
    def range_download(save_name, s_pos, e_pos):
        _headers = header.copy()
        _headers['Range'] = f"bytes={s_pos}-{e_pos}"
        res = requests.get(url, headers=_headers, stream=True)
        with open(save_name, "rb+") as f:
            f.seek(s_pos)
            for chunk in res.iter_content(chunk_size=64*1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
    
    bar = tqdm(total=content_size, desc=f'下载文件：{file_name}')
    divisional_ranges = calc_divisional_range(content_size, chuck=chunk)
    start = time.time()     
    with ThreadPoolExecutor() as p:
        futures = []
        for s_pos, e_pos in divisional_ranges:
            # print(s_pos, e_pos)
            futures.append(p.submit(range_download, file_name, s_pos, e_pos))
        # 等待所有任务执行完毕
        as_completed(futures)
    end = time.time()
    bar.close()
    print('\r[%.2f s] Download completed, save to %s' % (end - start, os.path.abspath(file_name)))

def download_single_thread(name, url, path):
    start = time.time()                                     # Download start
    header = headers(url).buildHeader()
    response = requests.get(url, headers=header, stream=True)
    size = 0                                                # Downloaded file size
    chunk_size = 1024                                       # data size per download
    content_size = int(response.headers['content-length'])  # Total download file size
    if response.status_code == 200:                         # Download succesful
        filepath = path + '\\' + name + '.mp4'
        with open(filepath, 'wb') as file:                  # Show prograss bar
            for data in response.iter_content(chunk_size = chunk_size):
                print('\rtotal:{size:.2f} MB'.format(
                        size = content_size / chunk_size / 1024
                    ), end='', flush=True)
                file.write(data)
                size += len(data)
                percentage = size / content_size
                print(' |%s%s| %.2f%%' % (
                        '▆' * int(percentage * 100), 
                        ' ' * (100 - int(percentage * 100)),
                        float(size / content_size * 100)
                    ), end='', flush=True)
        end = time.time()                                   # Download completed
        if os.path.exists(filepath):
            print('\r[%.2f s] Download completed, save to %s' % 
                    (end - start, os.path.abspath(filepath)))
        else:
            raise OSError('Download error, {} does not exist'.format(filepath))
    else:
        raise RuntimeError('request error, error code:', response.status_code)

def downloader(name, url, path):
    if not os.path.exists(path):
        raise ValueError("'{}' does not exist".format(path))

    # Download succesful
    filepath = path + '\\' + name + '.mp4'
    download_multi_thread(url, filepath, 10)

def time_check(time_str):
    '''convert time string to tuple and check its format
    :param str: the time string with ' ', '.', ':', '：', ',' and '，' as delimiter
    :param return: return a tuple that looks like (hour, minute, second) if the 
    input format is correct, otherwise return None
    '''
    splitted = re.split(' |\.|:|：|,|，', time_str)
    if len(splitted) > 3:
        return None
    
    time = [0, 0, 0]
    limit = (60, 60, 24)        # Reversed
    splitted.reverse()          # Reverse order traversal
    for i in range(len(splitted)):
        tmp = splitted[i]
        if tmp.isdigit() and int(tmp) < limit[i]:
            time[i] = int(tmp)
        else:
            return None

    time.reverse()
    return tuple(time)

def main():
    while True:
        url = input('请输入视频链接或vid编号:')
        vid = tangdou.get_vid(url)
        if vid is None:
            print("请输入包含vid参数的视频链接或直接输入vid编号！")
        else:
            td = tangdou.VideoAPI()
            try:
                video_info = td.get_video_info(vid)
            except (ValueError, RuntimeError) as e:
                print(e)
                print('请重试！')
                continue
            else:                   # Successfully obtained video information
                break

    path = input('请输入文件储存目录(默认为当前目录):')
    if path == '':
        path = os.path.dirname(os.path.abspath(__file__))
    path += '\\Download'
    if not os.path.exists(path):    # Create the directory if it does not exist
         os.mkdir(path)
    video_info['path'] = path
    filepath = video_info['path'] + '\\' + video_info['name'] + '.mp4'
    if os.path.exists(filepath):
        print(filepath, '已存在！')
    else:
        downloader(**video_info)    # Unfold this dict to pass parameters
    
    video = VideoFileClip(filepath)
    
    slice_info = slicer.analysisVideo(video, video.fps)
    auto_slice = input('自动分p（y/N）：')
    if auto_slice == '' or auto_slice == 'n' or auto_slice == 'N':
        pass
    else:
        slicer.doSlice(video, slice_info)

    while True:
        clip_start = input('剪辑起始时间(默认为不剪辑):')
        if clip_start == '':        # Do not clip
            break

        clip_start = time_check(clip_start)
        if clip_start is not None:
            break
        print('时间格式有误，请重新输入！')

    if (clip_start != ''):
        while True:
            clip_end = time_check(input('剪辑截止时间:'))
            if clip_end is not None:
                break
            print('时间格式有误，请重新输入！')

        print('[%02d:%02d:%02d<--->%02d:%02d:%02d]' % (*clip_start, *clip_end))
        print(clip_start)
        video = video.subclip(clip_start, clip_end)

        while True:
            save = input('是否保存剪辑过的视频（y/n）:')
            if save == 'y' or save == 'n':
                break
            print('输入有误，请重新输入！')
        
        if save == 'y':
            filepath = video_info['path'] + '\\' + video_info['name'] + '_edited.mp4'
            video.write_videofile(filepath)
            if not os.path.exists(filepath):
                raise OSError('video save error, {} does not exist'.format(filepath))
    

    while True:
        convert = input('是否转换为音频（y/N）:')
        if (convert == ''):
            break
        if convert == 'y' or convert == 'n':
            break
        print('输入有误，请重新输入！')
        
    if convert == 'y':
        audio = video.audio
        filepath = video_info['path'] + '\\' + video_info['name'] + '.mp3'
        audio.write_audiofile(filepath)
        if not os.path.exists(filepath):
            raise OSError('audio save error, {} does not exist'.format(filepath))

if __name__ == '__main__':
    print('===================糖豆视频下载器 By CCBP===================')
    print('     使用回车键（Enter）选择默认值，使用Ctrl+C退出程序')
    print('视频剪辑的时间输入以" "、"."、":"、"："、","、"，"作为分隔符')
    print('============================================================')
    while True:
        main()