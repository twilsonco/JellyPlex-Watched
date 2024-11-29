from dotenv import load_dotenv
import requests
from plexapi.server import PlexServer
import argparse
import json
import random
import string
import os
import time
from src.functions import (
    logger,
    str_to_bool,
)

parser = argparse.ArgumentParser(description="Move Plex users to Jellyfin")
load_dotenv(override=True)

DO_SYNC_PLEX_USERS_TO_JELLYFIN = str_to_bool(os.getenv("SYNC_PLEX_USERS_TO_JELLYFIN", "False"))
DRY_RUN = str_to_bool(os.getenv("DRYRUN", "True"))

'''Credentials'''
PLEX_URL = os.getenv("PLEX_BASEURL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
PLEX_SERVER_NAME = 'Plex server'

plex = PlexServer(PLEX_URL, PLEX_TOKEN)

JELLYFIN_URL = os.getenv("JELLYFIN_BASEURL")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_TOKEN")

user_list = {}

diceware_list = []
# Function to fetch the diceware word list gist from https://gist.githubusercontent.com/mingsai/8075fca3cea1ea8943c1f61db66fed13/raw/86fa664c6abb4d8522ce0ee757bf478985ffdf32/dicewarewordlist.txt
def fetch_diceware_word_list():
    global diceware_list
    try:
        r = requests.get("https://gist.githubusercontent.com/mingsai/8075fca3cea1ea8943c1f61db66fed13/raw/86fa664c6abb4d8522ce0ee757bf478985ffdf32/dicewarewordlist.txt") # Fetch the diceware word list
        if r.status_code == 200:
            # Now only take the lines that start with a 6-digit number separated from a word by a space
            words = [line.split() for line in r.text.splitlines()]
            words = [line[1] for line in words if len(line) == 2 and line[0].isdigit() and line[1].isalpha()]
            logger(f"Successfully fetched {len(words)} words from the diceware word list.", 1)
            diceware_list = words
        else:
            diceware_list = []
    except Exception as e:
        logger(e, 2)
        diceware_list = []

def j_get(cmd, params):
    return json.loads(requests.get(
        JELLYFIN_URL + "/jellyfin/" + cmd + "?api_key=" + JELLYFIN_API_KEY +
        ("&" + params if params is not None else "")).text)


def j_post(cmd, params, payload):
    return requests.post(JELLYFIN_URL + "/jellyfin/" + cmd + "?api_key=" + JELLYFIN_API_KEY +
                        ("&" + params if params is not None else ""), json=payload)

def diceware_password(length=4):
    # Create a diceware password using `length` words separated by either numbers or a space.
    # Each word will be lower or UPPER case with a 50% chance.
    p = ""
    for i in range(length):
        # flip coin
        is_upper = random.choice([True, False])
        if is_upper:
            p += random.choice(diceware_list).upper()
        else:
            p += random.choice(diceware_list).lower()
        if i < length - 1:
            p += random.choice([str(random.randint(0, 9)), " "])
    return p.strip()

def password(length=10):
    if diceware_list:
        return diceware_password(length)
    else:
        # Generate a random password of length `length` using ascii letters and digits
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def add_password(uid):
    p = password(length=10)
    payload = {
        "Id": uid,
        "CurrentPw": '',
        "NewPw": p,
        "ResetPassword": 'false'
    }
    r = requests.post(JELLYFIN_URL + "/Users/" + str(uid) + "/Password?api_key=" +
                    JELLYFIN_API_KEY, json=payload)
    if not str(r.status_code).startswith('2'):
        return False
    else:
        logger(p, 1)
        return p


def update_policy(uid):
    policy = {
        "IsAdministrator": "false",
        "IsHidden": "true",
        "IsHiddenRemotely": "true",
        "IsDisabled": "false",
        "EnableRemoteControlOfOtherUsers": "false",
        "EnableSharedDeviceControl": "false",
        "EnableRemoteAccess": "true",
        "EnableLiveTvManagement": "false",
        "EnableLiveTvAccess": "false",
        "EnableContentDeletion": "false",
        "EnableContentDownloading": "false",
        "EnableSyncTranscoding": "false",
        "EnableSubtitleManagement": "false",
        "EnableAllDevices": "true",
        "EnableAllChannels": "false",
        "EnablePublicSharing": "false",
        "InvalidLoginAttemptCount": 5,
        "BlockedChannels": [
            "IPTV",
            "TVHeadEnd Recordings"
        ]
    }
    if not str(j_post("Users/" + str(uid) + "/Policy", None, policy).status_code).startswith('2'):
        return False
    else:
        return True

def make_jellyfin_user(username):
    try:
        p = None
        payload = {
            "Name": username
        }
        r = j_post("Users/New", None, payload)
        if not str(r.status_code).startswith('2'):
            return False, r.content.decode("utf-8"), p
        else:
            r = json.loads(r.text)
            uid = r['Id']
            p = add_password(uid)
            if not p:
                p = None
            if update_policy(uid):
                return True, uid, p
            else:
                return False, uid, p
    except Exception as e:
        logger(e, 2)
        return False, None, None


def convert_plex_to_jellyfin(username):
    logger("Adding " + username + " to Jellyfin...", 1)
    succeeded, uid, pwd = make_jellyfin_user(username)
    if succeeded:
        user_list[username] = [uid, pwd]
        return True, None
    else:
        if uid:
            return False, uid
        else:
            return False, None

    return True, None

def sync_plex_users_to_jellyfin():
    logger("Beginning user migration...", 1)
    logger(f"Dry run: {DRY_RUN}", 1)
    fetch_diceware_word_list()
    for user in plex.myPlexAccount().users():
        for s in user.servers:
            if s.name == PLEX_SERVER_NAME:
                if DRY_RUN:
                    logger("DRY RUN: " + user.username + " would be added to Jellyfin.", 1)
                    break
                success, failure_reason = convert_plex_to_jellyfin(user.username)
                if success:
                    logger(user.username + " added to Jellyfin.", 1)
                else:
                    logger(user.username + " was not added to Jellyfin. Reason: " + str(failure_reason), 2)
                #time.sleep(5)
                break
    logger("User migration complete.", 1)
    if user_list:
        logger("Username ---- Password", 1)
        for k, v in user_list.items():
            logger(str(k) + "  |  " + str(v[1]), 1)