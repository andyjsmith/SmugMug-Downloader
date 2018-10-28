# SmugMug Downloader
Download all of the pictures from a SmugMug user, including password-protected users (you must know the password). This method is slightly inefficient, but works without requiring a SmugMug API key or any other information.

## Installation
* Install Python 3
* Clone this repository or download it as a zip
* Install the requirements:  `pip install -r requirements.txt`

## Usage
* Run `python smdl.py -u USERNAME` and it will begin downloading your pictures into separate folders in the default output directory. The username is what is found in the URL, i.e. USERNAME.smugmug.com
* To specify the output directory, use the `-o` flag: `python smdl.py -u USERNAME -o output`
* If the user requires an unlock password, you must sign in using the password in your web browser, then copy over the SMSESS cookie. In Google Chrome, you can view your cookies by pressing `Ctrl-Shift-I`, then go to the Application tab, go to the  Cookies dropdown, and click on https://USERNAME.smugmug.com. Then copy the value of the SMSESS cookie. You can then paste this cookie as an argument: `python smdl.py -u USERNAME -s 
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

###### NOTICE: SmugMug is a registered trademark of SmugMug Inc. This repository is not affiliated with SmugMug, Inc.