# SmugMug Downloader
Download all of the pictures from a SmugMug user, including password-protected users (you must know the password). This method is slightly inefficient, but works without requiring a SmugMug API key or any other information.

## Installation
* Install Python 3
* Clone this repository or download it as a zip
* Install the requirements:  `pip install -r requirements.txt`
* NOTE: If you are on Linux, you will probably need to type `pip3` and `python3` instead

## Usage
* Run `python smdl.py -u USERNAME` and it will begin downloading your pictures into separate folders in the default output directory. The username is what is found in the URL, i.e. USERNAME.smugmug.com.
* Some SmugMug sites are organized with [folders and hierarchy](https://www.smugmughelp.com/hc/en-us/articles/18212469747604-Organize-with-folders-and-hierarchy); if you would like to restrict your download to certain folders, you can directly put the relevant path into the username (USERNAME.smugmug.com/a/b/c would become `-u USERNAME/a/b/c`).
* To specify the output directory, use the `-o` flag: `python smdl.py -u USERNAME -o output`
* If the user requires an unlock password, you must sign in using the password in your web browser, then copy over the SMSESS cookie. In Google Chrome, you can view your cookies by pressing `Ctrl-Shift-I`, then go to the Application tab, go to the  Cookies dropdown, and click on https://USERNAME.smugmug.com. Then copy the value of the SMSESS cookie. You can then paste this cookie as an argument: `python smdl.py -u USERNAME -s 
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
* For a full list of command-line options, run `python smdl.py -h`, or see below:
```
usage: smdl.py [-h] [-s SESSION] -u USER [-o OUTPUT] [--albums ALBUMS]

SmugMug Downloader

optional arguments:
  -h, --help            show this help message and exit
  -s SESSION, --session SESSION
                        session ID (required if user is password protected); log
                        in on a web browser and paste the SMSESS cookie
  -u USER, --user USER  username (from URL, USERNAME.smugmug.com)
  -o OUTPUT, --output OUTPUT
                        output directory
  --albums ALBUMS       specific album names to download, split by $. Defaults
                        to all. Wrap in single quotes to avoid shell variable
                        substitutions. (e.g. --albums 'Title 1$Title 2$Title 3')
```


###### NOTICE: SmugMug is a registered trademark of SmugMug Inc. This repository is not affiliated with SmugMug, Inc.
