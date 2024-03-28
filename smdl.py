import argparse
import json
import os
import re
import sys
import urllib.error

import requests
from bs4 import BeautifulSoup
from colored import attr, bg, fg
from tqdm import tqdm

parser = argparse.ArgumentParser(description="SmugMug Downloader")
parser.add_argument(
    "-s",
    "--session",
    help="session ID (required if user is password protected); log in on a web browser and paste the SMSESS cookie",
)
parser.add_argument(
    "-u", "--user", help="username (from URL, USERNAME.smugmug.com)", required=True
)
parser.add_argument("-p", "--password", help="password for the user to log in")
parser.add_argument("-o", "--output", default="output/", help="output directory")
parser.add_argument(
    "--albums",
    help="specific album names to download, split by $. Defaults to all. Wrap in single quotes to avoid shell variable substitutions. (e.g. --albums 'Title 1$Title 2$Title 3')",
)

args = parser.parse_args()

endpoint = "https://www.smugmug.com"


def login(session: requests.Session, username: str, password: str):
    # get node_id and csrf_token from login page
    response = session.get(f"https://{username}.smugmug.com/")

    node_id_match = re.search(r'"rootNodeId":"(\w+)"', response.text)
    node_id = node_id_match.group(1) if node_id_match else ""
    csrf_token_match = re.search(r'"csrfToken":"(\w+)"', response.text)
    csrf_token = csrf_token_match.group(1) if csrf_token_match else ""

    print(f"node_id: {node_id}")
    print(f"csrf_token: {csrf_token}")

    # authenticate SMSESS cookie through the auth api
    print(f"auth session headers: {json.dumps(dict(session.headers))}")
    print(f"auth session cookies: {session.cookies}")

    response = session.post(
        f"https://{username}.smugmug.com/services/api/json/1.4.0/",
        cookies=session.cookies,
        data={
            "method": "rpc.node.auth",
            "Remember": "0",
            "Password": password,
            "NodeID": node_id,
            "_token": csrf_token,
        },
    )

    print(f"login response text: {response.text}")


session = requests.Session()

# Session ID (required if user is password protected)

if args.user and args.password:
    login(session, args.user, args.password)
elif args.session:
    # Log in on a web browser and copy the SMSESS cookie
    session.cookies.set("SMSESS", args.session)

if args.output[-1:] != "/" and args.output[-1:] != "\\":
    output_dir = args.output + "/"
else:
    output_dir = args.output

if args.albums:
    specificAlbums = [x.strip() for x in args.albums.split("$")]


# Gets the JSON output from an API call
def get_json(session, url):
    num_retries = 5
    for i in range(num_retries):
        try:
            r = session.get(endpoint + url, cookies=session.cookies)
            soup = BeautifulSoup(r.text, "html.parser")
            pres = soup.find_all("pre")
            return json.loads(pres[-1].text)
        except IndexError:
            print("ERROR: JSON output not found for URL: %s" % url)
            if i + 1 < num_retries:
                print("Retrying...")
            else:
                print("ERROR: Retries unsuccessful. Skipping this request.")
            continue
    return None


# Retrieve the list of albums
print("Downloading album list...", end="")
albums = get_json(session, "/api/v2/folder/user/%s!albumlist" % args.user)
if albums is None:
    print("ERROR: Could not retrieve album list.")
    sys.exit(1)
print("done.")

# Quit if no albums were found
try:
    albums["Response"]["AlbumList"]
except KeyError:
    sys.exit(
        "No albums were found for the user %s. The user may not exist or may be password protected."
        % args.user
    )

# Create output directories
print("Creating output directories...", end="")
for album in albums["Response"]["AlbumList"]:
    if args.albums:
        if album["Name"].strip() not in specificAlbums:
            continue

    directory = output_dir + album["UrlPath"][1:]
    if not os.path.exists(directory):
        os.makedirs(directory)
print("done.")


def format_label(s, width=24):
    return s[:width].ljust(width)


bar_format = "{l_bar}{bar:-2}| {n_fmt:>3}/{total_fmt:<3}"

# Loop through each album
for album in tqdm(
    albums["Response"]["AlbumList"],
    position=0,
    leave=True,
    bar_format=bar_format,
    desc=f"{fg('yellow')}{attr('bold')}{format_label('All Albums')}{attr('reset')}",
):
    if args.albums:
        if album["Name"].strip() not in specificAlbums:
            continue

    album_path = output_dir + album["UrlPath"][1:]
    images = get_json(session, album["Uri"] + "!images")
    if images is None:
        print(
            "ERROR: Could not retrieve images for album %s (%s)"
            % (album["Name"], album["Uri"])
        )
        continue

    # Skip if no images are in the album
    if "AlbumImage" in images["Response"]:

        # Loop through each page of the album
        next_images = images
        while "NextPage" in next_images["Response"]["Pages"]:
            next_images = get_json(
                session, next_images["Response"]["Pages"]["NextPage"]
            )
            if next_images is None:
                print(
                    "ERROR: Could not retrieve images page for album %s (%s)"
                    % (album["Name"], album["Uri"])
                )
                continue
            images["Response"]["AlbumImage"].extend(
                next_images["Response"]["AlbumImage"]
            )

        # Loop through each image in the album
        for image in tqdm(
            images["Response"]["AlbumImage"],
            position=1,
            leave=True,
            bar_format=bar_format,
            desc=f"{attr('bold')}{format_label(album['Name'])}{attr('reset')}",
        ):
            image_path = (
                album_path + "/" + re.sub(r"[^\w\-_\. ]", "_", image["FileName"])
            )

            # Skip if image has already been saved
            if os.path.isfile(image_path):
                continue

            # Grab video URI if the file is video, otherwise, the standard image URI
            largest_media = (
                "LargestVideo"
                if "LargestVideo" in image["Uris"]
                else (
                    "ImageDownload"
                    if "ImageDownload" in image["Uris"]
                    else "LargestImage"
                )
            )
            if largest_media in image["Uris"]:
                image_req = get_json(session, image["Uris"][largest_media]["Uri"])
                if image_req is None:
                    print(
                        "ERROR: Could not retrieve image for %s"
                        % image["Uris"][largest_media]["Uri"]
                    )
                    continue
                download_url = image_req["Response"][largest_media]["Url"]
            else:
                # grab archive link if there's no LargestImage URI
                download_url = image["ArchivedUri"]

            try:
                r = session.get(download_url, cookies=session.cookies)
                with open(image_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=128):
                        f.write(chunk)
            except UnicodeEncodeError as ex:
                print("Unicode Error: " + str(ex))
                continue
            except urllib.error.HTTPError as ex:
                print("HTTP Error: " + str(ex))

print("Completed.")
