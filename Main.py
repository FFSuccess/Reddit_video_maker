print("Loading in AI model and liberaries...")
from sys import exception
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from random import choice
import edge_tts
import asyncio
from copy import deepcopy
import ffmpeg
import os
import subprocess
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
import whisper
import textwrap
import warnings
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle
import undetected_chromedriver
from selenium.webdriver.chrome.options import Options
from random import uniform

warnings.filterwarnings('ignore', module='whisper')
current_directory = os.getcwd()
FFMPEG_PATH = r"C:\Users\sdawk\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin"
FONT_PATH = os.path.join(current_directory, "Poppins-Black.ttf")
LETTERS_COUNTED = set("zxcvbnmasdfghjklqwertyuiop1234567890ZXCVBNMASDFGHJKLQWERTYUIOP.,")
OUTPUT_FOLDER = os.path.join(current_directory, "Output")
AUDIO_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, "temp.mp3")
MINECRAFT_PARCORE_VIDS_FOLDER = os.path.join(current_directory, "split_videos")
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]
VIDEO_LENGTH_MINS = 1
MIN_NUM_OF_COMMENTS = 10
SUBREDDIT_NAME = "AskReddit"
SUBREDDIT_LINK = f"https://www.reddit.com/r/{SUBREDDIT_NAME}/"
MAX_AUDIO_DURATION_SECONDS = 60
MIN_AUDIO_DURATION_SECONDS = 20
CROP_TO_VERTICLE = True

def get_authenticated_service(token_file='token.pickle', secrets_file='client_secrets.json'):
    creds = None

    #check if token file exists
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    #if credentials are invalid or don't exist, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)

            #show which account was authenticated
            youtube_temp = build('youtube', 'v3', credentials=creds)
            channel_response = youtube_temp.channels().list(
                part='snippet',
                mine=True
            ).execute()

            channel_title = channel_response['items'][0]['snippet']['title']
            print(f"\n Authenticated as: {channel_title}")
            print(f"  Credentials saved to: {token_file}\n")

        #save credentials for future use
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def verify_account(youtube):
    try:
        channel_response = youtube.channels().list(
            part='snippet',
            mine=True
        ).execute()

        if channel_response['items']:
            channel = channel_response['items'][0]
            print(f"Current YouTube Channel: {channel['snippet']['title']}")
            print(f"Channel ID: {channel['id']}")
            return True
        else:
            print("No YouTube channel found for this account")
            return False
    except Exception as e:
        print(f"Error verifying account: {e}")
        return False

def upload_video(youtube, video_file, title, description, category='22',
                 privacy_status='private', tags=None):
    if not title:
        title = "Reddit story"
    if len(title) > 100:
        title = title[:100]
    if tags is None:
        tags = []
    body = {
        'snippet': {
            'title': title.strip(),
            'description': description.strip(),
            'tags': tags,
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False
        }
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)

    #create the upload request
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    #execute the request
    response = None
    print(f"Uploading video: {title}")

    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    print(f"Upload complete! Video ID: {response['id']}")
    return response

def add_subtitles(video_path, subtitles_data, output_path, font_path=FONT_PATH, font_size=80,
                  font_color="yellow", stroke_color="black", stroke_width=10):
    video = VideoFileClip(video_path)
    w, h = video.size

    subtitle_clips = []
    y_pos = "center"

    for sub in subtitles_data:
        wrapped_text = textwrap.shorten(sub['text'], width=25, placeholder="...")

        txt_clip = (
            TextClip(
                text=wrapped_text,
                font=font_path,
                color=font_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                method="caption",
                size=(int(w * 0.9), int(h * 0.3)),
                font_size=font_size,
                text_align='center',
            )
            .with_position(("center", y_pos))
            .with_start(sub['start'])
            .with_duration(sub['end'] - sub['start'])
        )

        subtitle_clips.append(txt_clip)

    final_video = CompositeVideoClip([video] + subtitle_clips)
    final_video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=video.fps,
        preset='medium'
    )

    video.close()
    final_video.close()

def auto_generate_subtitles(video_path, output_path, font_path):
    model = whisper.load_model("small")

    result = model.transcribe(video_path, word_timestamps=True)
    subtitles = []
    max_words = 3
    max_duration = 0.25
    temp_words = []
    start_time = None

    for segment in result["segments"]:
        for word in segment["words"]:
            if start_time is None:
                start_time = word["start"]

            temp_words.append(word["word"])

            #split subtitles frequently
            if len(temp_words) >= max_words or (word["end"] - start_time) > max_duration:
                subtitles.append({
                    "start": start_time,
                    "end": word["end"],
                    "text": " ".join(temp_words).strip()
                })
                temp_words = []
                start_time = None

    if temp_words and start_time is not None:
        subtitles.append({
            "start": start_time,
            "end": segment["end"],
            "text": " ".join(temp_words).strip()
        })

    add_subtitles(video_path, subtitles, output_path, font_path=font_path)
    return subtitles

def TTS_string(text, file_path):
    async def generate_speech():
        voice = "en-US-GuyNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(file_path)
        print(f"Edge TTS saved to {file_path}")
    asyncio.run(generate_speech())

def get_media_duration(file_path: str) -> float:
    ffprobe_path = os.path.join(FFMPEG_PATH, "ffprobe.exe")
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        duration_str = result.stdout.strip()
        return float(duration_str) if duration_str else None
    except Exception as e:
        print(f"Error reading duration: {e}")
        return None

def combine_audio_video_crop(video_path: str, audio_path: str, output_path: str):
    print("Combining audio and video...")
    print()
    ffmpeg_exe = os.path.join(FFMPEG_PATH, "ffmpeg.exe")

    #validate input files
    for path in (video_path, audio_path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

    #make ffmpeg command
    cmd = [ffmpeg_exe, "-y", "-i", video_path]
    cmd += ["-i", audio_path]

    #crop the video to a centered 9:16 aspect ratio
    crop_filter = "crop=ih*9/16:ih:(in_w-out_w)/2:0"

    cmd += [
        "-filter:v", crop_filter,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-g", "30",
        "-keyint_min", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-preset", "fast",
        output_path
    ]

    # Run ffmpeg command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Combined + cropped video saved as: {output_path}")
    except subprocess.CalledProcessError as e:
        print("FFmpeg failed:\n", e.stderr)
        raise
    
def combine_audio_video(video_path: str, audio_path: str, output_path: str):
    print("Combining audio and video...")
    print()
    ffmpeg_exe = os.path.join(FFMPEG_PATH, "ffmpeg.exe")

    #validate input files
    for path in (video_path, audio_path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

    #make ffmpeg command
    cmd = [ffmpeg_exe, "-y", "-i", video_path]
    cmd += ["-i", audio_path]

    cmd += [
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-g", "30",
        "-keyint_min", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-preset", "fast",
        output_path
    ]

    # Run ffmpeg command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Combined video saved as: {output_path}")
    except subprocess.CalledProcessError as e:
        print("FFmpeg failed:\n", e.stderr)
        raise

def randomised_sleep(low_bound, high_bound):
    sleep(uniform(low_bound, high_bound))

def setup_chrome_driver():
    #randomize browser flags
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/16.4 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ]

    driver = undetected_chromedriver.Chrome(
        headless=False,
        use_subprocess=True,
        version_main=None,
        driver_executable_path=None
    )
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": choice(user_agents)
    })
    randomised_sleep(2.0, 5.0)
    return driver

def main():
    #read in cache of previously viewed stories
    if os.path.exists("Videos_seen.pkl"):
        with open("Videos_seen.pkl", "rb") as videos_seen_file:
            videos_seen = pickle.load(videos_seen_file)
    else:
        videos_seen = []
    print(f"videos we have seen: {videos_seen}")
    try:
        #setup Chrome driver
        driver = setup_chrome_driver()
        driver.get(SUBREDDIT_LINK)
        randomised_sleep(2.0, 5.0)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        randomised_sleep(1.0, 2.0)
        reddit_links_xpath = driver.find_elements(
            By.XPATH,
            f"//a[starts-with(@href, '/r/{SUBREDDIT_NAME}/comments/')]"
        )

        #filter for only posts with enought replies
        filtered_reddit_links_xpath = []
        for link in reddit_links_xpath:
            parent_post = link.find_element(By.XPATH, "./ancestor::shreddit-post")
            comment_count = parent_post.get_attribute("comment-count")
            if int(comment_count) > MIN_NUM_OF_COMMENTS:
                filtered_reddit_links_xpath.append(link)
        reddit_links_xpath = filtered_reddit_links_xpath

        #choose story
        found_video = False
        for random_link in reddit_links_xpath:
            Title_text = random_link.text.strip() or "[No text]"
            if Title_text == "[No text]":
                pass
            if not Title_text in videos_seen:
                found_video = True
                break
        if not found_video:
            raise Exception("Have seen all stories possible.")
        link_href = random_link.get_attribute("href")

        print(f"Randomly selected link: {Title_text}")
        print("Clicking random reddit link...")

        #go to link for Question
        driver.get(str(link_href))
        randomised_sleep(4.0, 5.0)

        #find and extract responces
        responces = driver.find_elements(
            By.XPATH,
            "//*[starts-with(@id, 't1_')]"
        )
        Responces_text = ""
        for index, element in enumerate(responces):
            if index % 2 == 0:
                extracted_text = element.text.replace("track me","")
                Responces_text = f"{Responces_text}{extracted_text} \n"

        #trim down responces to under 1 min
        temp_count = 0
        Last_stop = 0
        Responces_text = f"{Title_text}? \n{Responces_text}"
        for index, charecter in enumerate(Responces_text):
            if temp_count >= (160 * 4 * VIDEO_LENGTH_MINS - 20):
                break
            if charecter in LETTERS_COUNTED:
                temp_count += 1
            if charecter == ".":
                Last_stop = deepcopy(index)
        Responces_text = "Reddit. " + Responces_text[:Last_stop] + "."
        print(f"Responces = {Responces_text}")

        #Turn responce into mp3
        TTS_string(Responces_text, AUDIO_OUTPUT_PATH)
        audio_duration = get_media_duration(AUDIO_OUTPUT_PATH)
        audio_duration = audio_duration.__floor__() + 1

        #make sure video legth is acceptable
        if audio_duration > MAX_AUDIO_DURATION_SECONDS:
            raise Exception(f"Too long, video length of {audio_duration}s")
        elif audio_duration < MIN_AUDIO_DURATION_SECONDS:
            raise Exception(f"Too short, video length of {audio_duration}s")

        #choose random parcore video
        parcore_videos = os.listdir(MINECRAFT_PARCORE_VIDS_FOLDER)
        parcore_video_random = choice(parcore_videos)
        parcore_video_random = os.path.join(MINECRAFT_PARCORE_VIDS_FOLDER, parcore_video_random)

        #combine with reddit story with minecraft parcore
        Output_file_name = f"{Title_text[:20]}.mp4"
        no_sub_output_path = os.path.join(OUTPUT_FOLDER, Output_file_name)
        if CROP_TO_VERTICLE:
            combine_audio_video_crop(parcore_video_random, AUDIO_OUTPUT_PATH, no_sub_output_path)
        else:
            combine_audio_video(parcore_video_random, AUDIO_OUTPUT_PATH, no_sub_output_path)

        #add subtitles
        Subbed_file_name = f"{Title_text[:20]} (subtitles).mp4"
        subbed_output_path = os.path.join(OUTPUT_FOLDER, Subbed_file_name)
        auto_generate_subtitles(no_sub_output_path, subbed_output_path, FONT_PATH)

        #upload to yt
        youtube_service = get_authenticated_service()
        if verify_account(youtube_service):
            pass
        video_response = upload_video(
            youtube=youtube_service,
            video_file=subbed_output_path,
            title=Title_text,
            description=Responces_text,
            category='22',
            privacy_status='public',
            tags=['reddit', 'story', 'fyp']
        )
        #add video to list of videos seen
        with open("Videos_seen.pkl", "wb") as videos_seen_file:
            videos_seen.append(Title_text)
            pickle.dump(videos_seen, videos_seen_file)
        print(f"\nVideo uploaded successfully!")
        print(f"Watch at: https://www.youtube.com/watch?v={video_response['id']}")
    finally:
        if driver:
            try:
                driver.quit()
            except OSError as e:
                if e.winerror == 6:
                    pass
                else:
                    raise
        driver = None
        print("Browser closed")
        #remove temp files
        print(f"waiting for tempory files to no be in use to delete...")
        sleep(5)
        try:
            for file in os.listdir(OUTPUT_FOLDER):
                os.remove(os.path.join(OUTPUT_FOLDER, file))
                print("Removed temp file: " + file)
        except Exception as e:
            print(f"Error removing file {e}")

if __name__ == '__main__':
    main()
