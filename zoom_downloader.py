#!/usr/bin/env python3

import asyncio
import requests
import argparse
import os
from playwright.async_api import async_playwright

video_urls = []


async def download_zoom_video_with_playwright(
    zoom_url, output_basename="zoom_recording"
):
    global video_urls
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        async def handle_response(response):
            url = response.url
            if any(ext in url for ext in [".mp4", ".m3u8"]) and "zoom" in url:
                print(f"Found video stream: {url}")
                video_urls.append(url)

        page.on("response", handle_response)

        print(f"Opening Zoom URL: {zoom_url}")
        await page.goto(zoom_url, wait_until="networkidle", timeout=90000)

        print("Waiting 15 seconds to allow streams to load...")
        await asyncio.sleep(15)

        if not video_urls:
            print("No video streams found.")
            return False

        print(f"Found {len(video_urls)} video stream(s). Downloading...")

        cookies = await context.cookies()
        cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Referer": zoom_url,
            "Range": "bytes=0-",
            "Connection": "keep-alive",
        }

        os.makedirs("downloads", exist_ok=True)
        output_files = []

        for i, url in enumerate(video_urls):
            file_type = "m3u8" if ".m3u8" in url else "mp4"
            filename = f"downloads/{output_basename}_stream{i}.{file_type}"
            print(f"Downloading stream {i+1}: {filename}")
            r = requests.get(url, headers=headers, cookies=cookies_dict, stream=True)

            if r.status_code in [200, 206]:
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"Downloaded: {filename}")
                output_files.append(filename)
            else:
                print(f"Failed to download stream {i+1}: {r.status_code}")

        return output_files


def merge_videos_side_by_side(video1, video2, output="merged_output.mp4"):
    print("Merging streams with ffmpeg...")
    cmd = f'ffmpeg -i "{video1}" -i "{video2}" -filter_complex "[0:v][1:v]hstack=inputs=2" -c:v libx264 -preset fast -crf 23 -y "{output}"'
    result = os.system(cmd)
    if result == 0:
        print(f"Merged video saved as {output}")
    else:
        print("ffmpeg merge failed.")


def main():
    parser = argparse.ArgumentParser(
        description="Download Zoom recordings (multi-stream)"
    )
    parser.add_argument("url", type=str, help="Zoom recording URL")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="zoom_recording",
        help="Base output filename",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Try to merge streams with ffmpeg (side-by-side)",
    )

    args = parser.parse_args()

    files = asyncio.run(download_zoom_video_with_playwright(args.url, args.output))

    if args.merge and files and len(files) >= 2:
        merge_videos_side_by_side(files[0], files[1])

    return 0 if files else 1


if __name__ == "__main__":
    exit(main())
