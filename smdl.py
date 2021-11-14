import argparse
import json
import os
import re
import sys
from functools import partial

import requests
from bs4 import BeautifulSoup
from colored import attr, bg, fg
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map
from diskcache import Cache

cache = Cache("cache")

# Gets the JSON output from an API call
@cache.memoize()
def get_json(url):
    r = requests.get(endpoint + url, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")
    pres = soup.find_all("pre")
    return json.loads(pres[-1].text) if len(pres) > 0 else ""


def format_label(s, width=24):
    return s[:width].ljust(width)


@cache.memoize()
def get_image_url(image) -> str:
    # Grab video URI if the file is video, otherwise, the standard image URI
    largest_media = (
        "LargestVideo" if "LargestVideo" in image["Uris"] else "LargestImage"
    )
    if largest_media in image["Uris"]:
        image_req = get_json(image["Uris"][largest_media]["Uri"])
        download_url = image_req["Response"][largest_media]["Url"]
    else:
        # grab archive link if there's no LargestImage URI
        download_url = image["ArchivedUri"]
    return download_url


@cache.memoize()
def get_images(album):
    images = get_json(album["Uri"] + "!images")

    # Skip if no images are in the album
    if "AlbumImage" not in images["Response"]:
        return []

    # Loop through each page of the album
    next_images = images
    while "NextPage" in next_images["Response"]["Pages"]:
        next_images = get_json(next_images["Response"]["Pages"]["NextPage"])
        images["Response"]["AlbumImage"].extend(next_images["Response"]["AlbumImage"])

    return images["Response"]["AlbumImage"]


def download_image(folder: str, image):
    image_path = folder + "/" + re.sub("[^\w\-_\. ]", "_", image["FileName"])

    # Skip if image has already been saved
    if os.path.isfile(image_path):
        return

    # Download the image
    try:
        r = requests.get(get_image_url(image))
        with open(image_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=128):
                f.write(chunk)
    except:
        print(
            f"{fg(1)}{bg(1)}[!]{attr(0)} Failed to download image: {image_path}{attr(0)}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SmugMug Downloader")
    parser.add_argument(
        "-s",
        "--session",
        help="session ID (required if user is password protected); log in on a web browser and paste the SMSESS cookie",
    )
    parser.add_argument(
        "-u", "--user", help="username (from URL, USERNAME.smugmug.com)", required=True
    )
    parser.add_argument("-o", "--output", default="output/", help="output directory")
    parser.add_argument(
        "--albums",
        help="specific album names to download, split by $. Defaults to all. Wrap in single quotes to avoid shell variable substitutions. (e.g. --albums 'Title 1$Title 2$Title 3')",
    )

    args = parser.parse_args()

    endpoint = "https://www.smugmug.com"

    # Session ID (required if user is password protected)
    # Log in on a web browser and copy the SMSESS cookie
    SMSESS = args.session

    cookies = {"SMSESS": SMSESS}

    if args.output[-1:] != "/" and args.output[-1:] != "\\":
        output_dir = args.output + "/"
    else:
        output_dir = args.output

    if args.albums:
        specificAlbums = [x.strip() for x in args.albums.split("$")]

    # Retrieve the list of albums
    print("Downloading album list...", end="")
    albums = get_json("/api/v2/folder/user/%s!albumlist" % args.user)
    print("done.")

    # Quit if no albums were found
    try:
        albums["Response"]["AlbumList"]
    except KeyError:
        sys.exit(
            "No albums were found for the user %s. The user may not exist or may be password protected."
            % args.user
        )

    bar_format = "{l_bar}{bar:-2}| {n_fmt:>3}/{total_fmt:<3}"

    # Loop through each album
    for album in tqdm(
        albums["Response"]["AlbumList"],
        position=0,
        leave=True,
        bar_format=bar_format,
        desc=f"{fg('yellow')}{attr('bold')}{format_label('All Albums')}{attr('reset')}",
    ):
        if args.albums and album["Name"].strip() not in specificAlbums:
            continue

        directory = output_dir + album["UrlPath"][1:]

        if not os.path.exists(directory):
            os.makedirs(directory)

        download_image_from_this_album = partial(download_image, directory)
        process_map(
            download_image_from_this_album, 
            get_images(album),
            max_workers=8,
            position=0,
            leave=True,
            bar_format=bar_format,
            desc=f"{attr('bold')}{format_label(album['Name'])}{attr('reset')}",
        )
