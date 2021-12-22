import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time

from typing import List


def language_list(x: str) -> List[str]:
    if ":" not in x:
        raise ValueError()

    return x.split(":", maxsplit=2)


def open_keys_file(keys_file: str, args: argparse.Namespace) -> None:
    with open(keys_file, "r") as config_data:
        config = json.load(config_data)
        args.mpd_url = config[0]["mpd_url"]

        for i in range(1, len(config)):
            if "kid" in config[i] and "hex_key" in config[i]:
                args.keys.append(f"{config[i]['kid']}:{config[i]['hex_key']}")


def download_mpd(mpd_url: str, output_dir: str) -> None:
    subprocess.run(["./bin/yt-dlp", "--external-downloader", "./bin/aria2c", "--allow-unplayable-formats", "--no-check-certificate", "--format", "bestvideo", "--fixup", "never", mpd_url, "-o", os.path.join(output_dir, "video_encrypted.mp4")], check=True)
    subprocess.run(["./bin/yt-dlp", "--external-downloader", "./bin/aria2c", "--allow-unplayable-formats", "--no-check-certificate", "--format", "bestaudio", "--fixup", "never", mpd_url, "-o", os.path.join(output_dir, "audio_encrypted.m4a")], check=True)


def decrypt_file(input_file: str, output_file: str, keys: List[str]) -> None:
    mp4decrypt_args = ["./bin/mp4decrypt", "--show-progress"]

    for key in keys:
        mp4decrypt_args += ["--key", key]

    mp4decrypt_args += [input_file, output_file]
    subprocess.run(mp4decrypt_args, check=True)


def merge_mkv(output_file: str, video_file: str, video_language: str, audio_file: str, audio_language: str) -> None:
    subprocess.run([
        "./bin/mkvmerge",
        "--output", output_file,
        "--language", f"0:{video_language}", "--default-track", "0:yes", "--compression", "0:none", video_file,
        "--language", f"0:{audio_language}", "--default-track", "0:yes", "--compression", "0:none", audio_file,
        "--track-order", "0:0,1:0"
    ], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download DRM protected content from MPD manifests")
    parser.add_argument("-f", "--file", metavar="KEYS_FILE", dest="file", help="path to keys.json file", default="keys.json")
    parser.add_argument("-m", "--mpd-url", metavar="MPD_URL", dest="mpd_url", help="url to manifest.mpd file", default=None)
    parser.add_argument("-k", "--key", metavar="KID:HEX", dest="keys", action="append", help="widevine keys to decrypt", default=[])
    parser.add_argument("-o", "--output", metavar="OUTPUT", dest="output", help="output file name with no extension", required=True)
    parser.add_argument("-l", "--language", metavar="VIDEO:AUDIO", dest="language", type=language_list, required=True)
    args = parser.parse_args()

    if not args.mpd_url or not args.keys:
        open_keys_file(args.file, args)

    print("Starting download...")

    tmp_dir = tempfile.mkdtemp(prefix="mpd_")
    start_time = time.time()

    try:
        download_mpd(args.mpd_url, tmp_dir)
        decrypt_file(os.path.join(tmp_dir, "video_encrypted.mp4"), os.path.join(tmp_dir, "video.mp4"), args.keys)
        decrypt_file(os.path.join(tmp_dir, "audio_encrypted.m4a"), os.path.join(tmp_dir, "audio.m4a"), args.keys)
        merge_mkv(args.output, os.path.join(tmp_dir, "video.mp4"), args.language[0], os.path.join(tmp_dir, "audio.m4a"), args.language[1])
    except subprocess.CalledProcessError:
        print("Could not download MPD manifest!")
        exit(1)
    finally:
        shutil.rmtree(tmp_dir)

    print(f"Done! Job finished in {round(time.time() - start_time, 2)} seconds.")


if __name__ == "__main__":
    main()
