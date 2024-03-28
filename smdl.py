import argparse
import json
import logging
import os
import re
import sys
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from colored import attr, fg
from retrying import retry
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("smugmug_downloader.log"),
        logging.StreamHandler(sys.stdout),
    ],
)


class SmugMugDownloader:
    def __init__(self, username: str, password: Optional[str], output_dir: str):
        self.username = username
        self.password = password
        self.output_dir = output_dir
        self.session = requests.Session()

    def login(self):
        response = self.session.get(f"https://{self.username}.smugmug.com/")

        node_id_match = re.search(r'"rootNodeId":"(\w+)"', response.text)
        node_id = node_id_match.group(1) if node_id_match else ""
        csrf_token_match = re.search(r'"csrfToken":"(\w+)"', response.text)
        csrf_token = csrf_token_match.group(1) if csrf_token_match else ""

        logging.info(f"node_id: {node_id}")
        logging.info(f"csrf_token: {csrf_token}")

        response = self.session.post(
            f"https://{self.username}.smugmug.com/services/api/json/1.4.0/",
            cookies=self.session.cookies,
            data={
                "method": "rpc.node.auth",
                "Remember": "0",
                "Password": self.password,
                "NodeID": node_id,
                "_token": csrf_token,
            },
        )

        logging.info(f"login response text: {response.text}")

    @retry(
        stop_max_attempt_number=5,
        wait_exponential_multiplier=1000,
        wait_exponential_max=30000,
        retry_on_exception=lambda e: isinstance(
            e, (requests.RequestException, IndexError)
        ),
    )
    def get_json(self, url: str):
        try:
            r = self.session.get(
                f"https://www.smugmug.com{url}", cookies=self.session.cookies
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            pres = soup.find_all("pre")
            return json.loads(pres[-1].text)
        except (IndexError, requests.RequestException) as e:
            logging.error(f"Failed to get JSON data from URL: {url}. Error: {e}")
            raise

    def prepare_album_list(
        self, selected_albums: Optional[List[str]], selected_folder: Optional[str]
    ):
        logging.info("Downloading album list...")
        albums = self.get_json(f"/api/v2/folder/user/{self.username}!albumlist")
        if albums is None:
            logging.error("Failed to retrieve album list.")
            sys.exit(1)
        logging.info("Album list downloaded.")

        try:
            albums["Response"]["AlbumList"]
        except KeyError:
            logging.error(
                f"No albums were found for the user {self.username}. The user may not exist or may be password protected."
            )
            sys.exit(1)

        logging.info("Preparing album list to download:")
        album_list = []
        for album in albums["Response"]["AlbumList"]:
            if (selected_albums and album["Name"].strip() in selected_albums) or (
                selected_folder and selected_folder in album["UrlPath"]
            ):
                logging.info(f"- {album['UrlPath']}")
                album_list.append(album)
        return album_list

    def create_album_folders(self, album_list: List[dict]):
        for album in album_list:
            directory = self.output_dir + album["UrlPath"][1:]
            if not os.path.exists(directory):
                os.makedirs(directory)
                logging.info(f"Created directory: {directory}")

    def download_albums(self, album_list: List[dict]):
        bar_format = "{l_bar}{bar:-2}| {n_fmt:>3}/{total_fmt:<3}"

        for album in tqdm(
            album_list,
            position=0,
            leave=True,
            bar_format=bar_format,
            desc=f"{fg('yellow')}{attr('bold')}{self.format_label('All Albums')}{attr('reset')}",
        ):
            album_path = self.output_dir + album["UrlPath"][1:]
            images = self.get_json(album["Uri"] + "!images")
            if images is None:
                logging.error(
                    f"Failed to retrieve images for album {album['Name']} ({album['Uri']})"
                )
                continue

            if "AlbumImage" in images["Response"]:
                next_images = images
                while "NextPage" in next_images["Response"]["Pages"]:
                    next_images = self.get_json(
                        next_images["Response"]["Pages"]["NextPage"]
                    )
                    if next_images is None:
                        logging.error(
                            f"Failed to retrieve images page for album {album['Name']} ({album['Uri']})"
                        )
                        break
                    images["Response"]["AlbumImage"].extend(
                        next_images["Response"]["AlbumImage"]
                    )

                for image in tqdm(
                    images["Response"]["AlbumImage"],
                    position=1,
                    leave=True,
                    bar_format=bar_format,
                    desc=f"{attr('bold')}{self.format_label(album['Name'])}{attr('reset')}",
                ):
                    self.download_image(image, album_path)

        logging.info("Download completed.")

    @staticmethod
    def format_label(s, width=24):
        return s[:width].ljust(width)

    def download_image(self, image: dict, album_path: str):
        image_path = album_path + "/" + re.sub(r"[^\w\-_\. ]", "_", image["FileName"])

        if os.path.isfile(image_path):
            return

        largest_media = (
            "LargestVideo"
            if "LargestVideo" in image["Uris"]
            else (
                "ImageDownload" if "ImageDownload" in image["Uris"] else "LargestImage"
            )
        )
        if largest_media in image["Uris"]:
            image_req = self.get_json(image["Uris"][largest_media]["Uri"])
            if image_req is None:
                logging.error(
                    f"Failed to retrieve image for {image['Uris'][largest_media]['Uri']}"
                )
                return
            download_url = image_req["Response"][largest_media]["Url"]
        else:
            download_url = image["ArchivedUri"]

        try:
            r = self.session.get(download_url, cookies=self.session.cookies)
            with open(image_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=128):
                    f.write(chunk)
            logging.info(f"Downloaded image: {image_path}")
        except UnicodeEncodeError as ex:
            logging.error(f"Unicode Error: {ex}")
            return
        except Exception as ex:
            logging.error(f"Failed to download image {image_path}: {ex}")

    def run(self, selected_albums: Optional[List[str]], selected_folder: Optional[str]):
        if self.password:
            logging.info("Logging in...")
            self.login()

        logging.info("Preparing album list...")
        album_list = self.prepare_album_list(selected_albums, selected_folder)

        logging.info("Creating album folders...")
        self.create_album_folders(album_list)

        logging.info("Starting download...")
        self.download_albums(album_list)


def parse_args():
    parser = argparse.ArgumentParser(description="SmugMug Downloader")
    parser.add_argument(
        "-u",
        "--username",
        help="username (from URL, USERNAME.smugmug.com)",
        required=True,
    )
    parser.add_argument("-p", "--password", help="password for the user to login")
    parser.add_argument("-o", "--output", default="output/", help="output directory")
    parser.add_argument(
        "--albums",
        help="specific album names to download, split by $. Defaults to all. Wrap in single quotes to avoid shell variable substitutions. (e.g. --albums 'Title 1$Title 2$Title 3')",
    )
    parser.add_argument(
        "--folder",
        help="download all the albums under the specific folder",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    if args.output[-1:] != "/" and args.output[-1:] != "\\":
        output_dir = args.output + "/"
    else:
        output_dir = args.output
    if args.albums:
        selected_albums = [x.strip() for x in args.albums.split("$")]
    else:
        selected_albums = None

    downloader = SmugMugDownloader(args.username, args.password, output_dir)
    downloader.run(selected_albums, args.folder)


if __name__ == "__main__":
    main()
