import os
import argparse
import json
import soundfile as sf
import pyloudnorm as pyln
import numpy as np
import requests
from io import BytesIO
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy import ImageClip, AudioFileClip

# Variables from workflow
#background_path = "1200px-MM_Japas's_Room.png" # https://cdn.wikimg.net/en/zeldawiki/images/thumb/a/af/MM_Japas's_Room.png/1200px-MM_Japas's_Room.png
bold_font = "Montserrat-Bold.ttf"
regular_font = "Montserrat-Regular.ttf"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/141.0.0.0 Safari/537.36"
}

# TODO: ADD COMMAND LINE ARGUMENTS FOR VARIABLES, AND FOR CLEANUP AFTER UPLOAD

def make_video(background_image):
    if not background_image:
        raise Exception('Missing background image: To create a video is necessary to provide a background image')

    # First search the properties file. We expect to execute this script on the z64packer folder
    propertiesPath = 'z64musicpacker.properties' 
    if not os.path.exists(propertiesPath):
        raise Exception('Missing z64musicpacker.properties file: This is not an Z64 repository or the script is not beign executed in the z64packer folder!')
        
    with open(propertiesPath, encoding='ISO-8859-1') as propertiesFile:
        properties = json.load(propertiesFile)

        # Open the games database, for metadata purposes
        with open('z64games.json', 'r+', encoding='ISO-8859-1') as gamesFile:
            games = json.load(gamesFile)

            # Open the database, to find an available song to upload
            with open('z64songs.json', 'r+', encoding='ISO-8859-1') as databaseFile:
                database = json.load(databaseFile)

                # TODO: Make an option to choose the song to upload manually
                # Find any song with a local preview to upload
                song = next((s for s in database if s.get("preview", "").endswith(".mp3")), None)
                if(song == None):
                    print("No song found to upload!")
                    return
                
                # A song was found! Now proceed to create a video...
                print(f"Song found: {song["preview"]} | Creating video...")

                # Find the game metadata
                game = next((g for g in games if g.get("game", "-") == song.get("game")), None)
                if(game == None or game.get("logo") == None):
                    print(f"LOGO NOT FOUND FOR '{song.get("game")}'! Please add it and try again...")
                    return

                # First, find all the necessary assets
                logo_path = game.get("logo")
                audio_path = "../" + properties["previews"] + song["preview"]
                title = song["song"]
                subtitle = song["game"]
                composers = ", ".join(song.get("composers", [])) or "-"
                converters = ", ".join(song.get("converters", [])) or "-"
                format = f"{("Majora's Mask" if song["file"].endswith(".mmrs") else "Ocarina of Time")} soundfont{(" with custom bank" if song["usesCustomBank"] == "true" else "")}{(" and samples" if song["usesCustomSamples"] == "true" else "")}"
                
                # Now let's create the video
                print("Creating video file...")
                create_thumbnail(title, subtitle, background_image, logo_path)
                create_video(audio_path)
                print("Video created succesfully!")

                # Create a file with the song uuid to later identify them for YT link registration
                with open('song.txt', 'w') as s:
                    s.write(song["uuid"])

                # Finally, we need to create a metadata file for YouTube upload process
                # https://github.com/porjo/youtubeuploader?tab=readme-ov-file#metadata
                with open('metadata.json', 'w') as f:
                    json.dump({
                        "title": f"{title} (MM Soundfont) | {subtitle}",
                        "description": f"Song: {title}\n"
                                    f"Game/Source: {subtitle}\n"
                                    f"Composer(s): {composers}\n"
                                    f"Converter(s): {converters}\n"
                                    f"Format: {format}\n"
                                    "\n"
                                    "Created to work in Oot and MM randomizers.\n"
                                    "Song packer: https://cristobalpenaloza.github.io/z64_song_packer.html",
                        "privacyStatus": "public",
                        "madeForKids": False,
                        "embeddable": True,
                        "categoryId": "10", # Music
                        "language": "en"
                    }, f)

# TODO: Given that there could be multiple packers, consider that this should be more dynamic that it is already. At the moment only Japas Jams style support.
def create_thumbnail(title, subtitle, background_image, logo_url):
    # Add the background and blur it
    if background_image.startswith("https://"):
        background_response = requests.get(background_image, headers=headers)
        background_response.raise_for_status()
        img = Image.open(BytesIO(background_response.content)).convert("RGBA")
    else: img = Image.open(background_image).convert("RGBA")
    
    half_w = int(img.width / 2)
    half_h = int(img.height / 2)
    padding = 75

    # Blur the background and darken it, so the text and logo pop more
    img = img.filter(ImageFilter.GaussianBlur(radius=6))
    img = ImageEnhance.Brightness(img).enhance(0.8)

    # Download the game logo
    logo_response = requests.get(logo_url, headers=headers)
    logo_response.raise_for_status()
    logo = Image.open(BytesIO(logo_response.content)).convert("RGBA")
    
    # Resize to half the size of the background, considering the space for the padding on both sides
    logo_max_w = half_w - (padding * 2)
    logo_max_h = half_h - padding # Also limit heigh, for very tall logos...
    ratio = min(logo_max_w / logo.width, logo_max_h / logo.height)
    logo = logo.resize((int(logo.width * ratio), int(logo.height * ratio)))

    # Paste on the left size, centered on the middle
    logo_x = int(half_w / 2) - int(logo.width / 2)
    logo_y = half_h - int(logo.height / 2)
    img.paste(logo, (logo_x, logo_y), logo)

    draw = ImageDraw.Draw(img)
    # Prepare the title
    title_size = (img.height / 13)
    title_font = ImageFont.truetype(bold_font, size=title_size)
    title_lines = textwrap.wrap(title, 16) # 9 ems
    title_total_height = title_size * len(title_lines)

    # Prepare the subtitle
    subtitle_size = title_size / 2
    subtitle_font = ImageFont.truetype(regular_font, size=subtitle_size)
    subtitle_lines = textwrap.wrap(subtitle, 32) # 18 ems
    subtitle_total_height = subtitle_size * len(subtitle_lines)

    # Calculate height and anchor
    text_total_height = title_total_height + subtitle_total_height
    text_half_height = int(text_total_height / 2)
    text_anchor = int((half_h - text_half_height) + subtitle_total_height)

    # Write the title downwards from the middle
    title_height = text_anchor
    for line in title_lines:
        draw.text((half_w + padding, title_height), line, font=title_font)
        title_height += title_size

    # Write the subtitle upwards from the middle
    subtitle_lines.reverse() # Need to reverse to write upwards
    subtitle_height = text_anchor - (subtitle_size)
    for line in subtitle_lines:
        draw.text((half_w + padding, subtitle_height), line, font=subtitle_font)
        subtitle_height -= subtitle_size
    
    # Draw a line in the middle
    #draw.line([half_w, half_h - subtitle_size, half_w, half_h + subtitle_size], width=5)
    draw.line([half_w, half_h - text_half_height, half_w, half_h + text_half_height], width=5)

    img.save("result.png")
    return True

def create_video(audio_path):
    normalized_audio = normalize_youtube_audio(audio_path)
    audio_clip = AudioFileClip(normalized_audio)
    image_clip = ImageClip("result.png")
    image_clip = image_clip.with_duration(audio_clip.duration)
    image_clip = image_clip.with_fps(24)

    video_clip = image_clip.with_audio(audio_clip)
    video_clip.write_videofile("result.mp4", codec="libx264", audio_codec="aac")
    return True

# Directly taken from Candy's Pack lol
def normalize_youtube_audio(path):
    # Load audio
    # Load from bytes
    data, sr = sf.read(path)

    # Ensure float32 array
    if data.dtype != np.float32:
        data = data.astype(np.float32)

    # Convert threshold to amplitude
    silence_thresh_db = -40
    silence_thresh = 10 ** (silence_thresh_db / 20.0)

    # If stereo, average across channels
    if data.ndim > 1:
        rms = np.sqrt(np.mean(data**2, axis=1))
    else:
        rms = np.abs(data)

    # Find first frame above threshold (non-silent start)
    non_silent_idx = np.argmax(rms > silence_thresh)
    if rms[non_silent_idx] <= silence_thresh:
        non_silent_idx = 0  # file may be all silence

    # Trim leading silence
    trimmed = data[non_silent_idx:]

    # Measure loudness
    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(trimmed)

    # Normalize to target LUFS
    normalized = pyln.normalize.loudness(trimmed, loudness, -14)

    # Export back to bytes (WAV)
    buf = BytesIO()
    sf.write(buf, normalized, sr, format='mp3')
    with open("vid_audio.mp3", "wb") as fh:
        fh.write(buf.getvalue())
    return "vid_audio.mp3"


def register_video():
    # Check if we are not missing the necessary files
    properties_path = "z64musicpacker.properties"
    metadata_out_path = "metadata_out.json"
    song_uuid_path = "song.txt"

    if not os.path.exists(properties_path):
        raise Exception('Missing z64musicpacker.properties file: This is not an Z64 repository or the script is not beign executed in the z64packer folder!')
    if not os.path.exists(metadata_out_path) or not os.path.exists(song_uuid_path):
        raise Exception('Missing data files: Run MAKE_VIDEO before trying to register!')

    # First, read if we have a YT link and a UUID to register!
    with open(metadata_out_path, encoding='ISO-8859-1') as meta_out_file:
        meta_out = json.load(meta_out_file)

        with open(song_uuid_path, encoding='ISO-8859-1') as song_uuid_file:
            song_uuid = song_uuid_file.read()
            yt_link = f"https://www.youtube.com/watch?v={meta_out["id"]}"
            print(f"Registering video {yt_link} for song {song_uuid}")

            with open("z64musicpacker.properties", encoding='ISO-8859-1') as propertiesFile:
                properties = json.load(propertiesFile)

                # Now that we have our song ready, open the database
                with open('z64songs.json', 'r+', encoding='ISO-8859-1') as databaseFile:
                    database = json.load(databaseFile)

                    # Find the song by uuid
                    i = [index for index, song in enumerate(database) if song["uuid"] == song_uuid][0]
                    preview_path = database[i]["preview"]

                    # Delete the current preview
                    if not preview_path.startswith("https://"):
                        full_preview_path = "../" + properties["previews"] + preview_path
                        if os.path.exists(full_preview_path):
                            #os.remove(full_preview_path) TODO: <-- REACTIVATE ON FINAL BUILD!!!
                            print(f"File {full_preview_path} deleted successfully!")

                    # Set the new preview
                    print("Setting new preview... " + yt_link)
                    database[i]["preview"] = yt_link

                    # Write changes to database
                    databaseFile.seek(0)
                    json.dump(database, databaseFile, indent=2)
                    databaseFile.truncate()

    print("Video registered successfully!")
    
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Makes and manage preview videos for Z64 repositories."
    )
    parser.add_argument("--mode", choices=["MAKE_VIDEO", "REGISTER_VIDEO"], default="MAKE_VIDEO", help="Defines the mode the script will work.")
    parser.add_argument("--background_image", type=str, help="Path or url to an image to use as a background for the video.")
    args = parser.parse_args()

    mode = args.mode
    background_image = args.background_image

    if mode == "MAKE_VIDEO": make_video(background_image)
    else: register_video()
    
