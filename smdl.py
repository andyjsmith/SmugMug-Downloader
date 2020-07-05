import os
import sys
import requests
import json
import re
import argparse
from bs4 import BeautifulSoup
from tqdm import tqdm
from colored import fg, bg, attr

parser = argparse.ArgumentParser(description="SmugMug Downloader")
parser.add_argument(
		"-s", "--session", help="session ID (required if user is password protected); log in on a web browser and paste the SMSESS cookie")
parser.add_argument(
		"-u", "--user", help="username (from URL, USERNAME.smugmug.com)", required=True)
parser.add_argument("-o", "--output", default="output/",
		help="output directory")
parser.add_argument(
		"--albums", help='specific album names to download, split by $. Defaults to all. (e.g. --albums "Title 1$Title 2$Title 3")')

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
	specificAlbums = [x.strip() for x in args.albums.split('$')]


# Gets the JSON output from an API call
def get_json(url):
	r = requests.get(endpoint + url, cookies=cookies)
	soup = BeautifulSoup(r.text, "html.parser")
	pres = soup.find_all("pre")
	return json.loads(pres[-1].text)


# Retrieve the list of albums
print("Downloading album list...", end="")
albums = get_json("/api/v2/folder/user/%s!albumlist" % args.user)
print("done.")

# Quit if no albums were found
try:
	albums["Response"]["AlbumList"]
except KeyError:
	sys.exit("No albums were found for the user %s. The user may not exist or may be password protected." % args.user)

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

bar_format = '{l_bar}{bar:-2}| {n_fmt:>3}/{total_fmt:<3}'

# Loop through each album
for album in tqdm(albums["Response"]["AlbumList"], position=0, leave=True, bar_format=bar_format,
		desc=f"{fg('yellow')}{attr('bold')}{format_label('All Albums')}{attr('reset')}"):
	if args.albums:
		if album["Name"].strip() not in specificAlbums:
			continue

	album_path = output_dir + album["UrlPath"][1:]
	images = get_json(album["Uri"] + "!images")

	# Loop through each page
	while True:
		# Skip if no images are in the album
		if "AlbumImage" not in images["Response"]:
			break

		# Loop through each image in the album
		for image in tqdm(images["Response"]["AlbumImage"], position=1, leave=True, bar_format=bar_format,
				desc=f"{attr('bold')}{format_label(album['Name'])}{attr('reset')}"):
			image_path = album_path + "/" + \
					re.sub('[^\w\-_\. ]', '_', image["FileName"])

			# Skip if image has already been saved
			if os.path.isfile(image_path):
				continue

			# Grab video URI if the file is video, otherwise, the standard image URI
			largest_media = "LargestVideo" if "LargestVideo" in image["Uris"] else "LargestImage"
			if largest_media in image["Uris"]:
				image_req = get_json(image["Uris"][largest_media]["Uri"])
				download_url = image_req["Response"][largest_media]["Url"]
			else:
				# grab archive link if there's no LargestImage URI
				download_url = image["ArchivedUri"]

			try:
				r = requests.get(download_url)
				with open(image_path, 'wb') as f:
					for chunk in r.iter_content(chunk_size=128):
						f.write(chunk)
			except UnicodeEncodeError as ex:
				print("Unicode Error: " + str(ex))
				continue
			except urllib.error.HTTPError as ex:
				print("HTTP Error: " + str(ex))

		# Loop through each page of the album
		if "NextPage" in images["Response"]["Pages"]:
			images = get_json(images["Response"]["Pages"]["NextPage"])
		else:
			break

print("Completed.")
