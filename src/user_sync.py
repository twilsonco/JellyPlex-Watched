from dotenv import load_dotenv
from plexapi.server import PlexServer
import argparse
import os
from src.functions import (
    logger,
    str_to_bool
)

parser = argparse.ArgumentParser(description="Move Plex users to Jellyfin")
load_dotenv(override=True)

DO_SYNC_PLEX_USERS_TO_JELLYFIN = str_to_bool(os.getenv("SYNC_PLEX_USERS_TO_JELLYFIN", "False"))
DRY_RUN = str_to_bool(os.getenv("DRYRUN", "True"))

'''Credentials'''
PLEX_URL = os.getenv("PLEX_BASEURL", "")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
PLEX_SERVER_NAME = os.getenv("PLEX_SERVERNAME", "")
GENERATE_USER_PASSWORDS = str_to_bool(os.getenv("SYNC_PLEX_USERS_GENERATE_USER_PASSWORDS", "False"))

plex = PlexServer(PLEX_URL, PLEX_TOKEN)

user_list = {}

def convert_plex_to_jellyfin(username, server):
    logger("Adding " + username + " to Jellyfin...", 1)
    # succeeded, uid, pwd = make_jellyfin_user(username)
    succeeded, uid, pwd = server[1].create_user(username, pwd=GENERATE_USER_PASSWORDS)
    if succeeded:
        user_list[username] = [uid, pwd]
    if succeeded:
        return True, None
    else:
        if uid:
            return False, uid
        else:
            return False, None

def sync_plex_users_to_jellyfin(jelly_server):
    logger("Beginning user migration...", 0)
    logger(f"Dry run: {DRY_RUN}", 0)
    if "" in [PLEX_URL, PLEX_TOKEN, PLEX_SERVER_NAME]:
        logger(f"Cannot sync users because Plex environment variables not set: {PLEX_URL = }, {PLEX_TOKEN = }, {PLEX_SERVER_NAME = }", 2)
        return
    for user in plex.myPlexAccount().users():
        if not user.username.strip():
            logger("Skipping blank username...", 0)
            continue
        if user.username not in jelly_server[1].users.keys():
            logger(f"Adding {user.username} to Jellyfin...", 0)
            for s in user.servers:
                if s.name == PLEX_SERVER_NAME:
                    if DRY_RUN:
                        logger("DRY RUN: " + user.username + " would be added to Jellyfin.", 0)
                        break
                    success, failure_reason = convert_plex_to_jellyfin(user.username, jelly_server)
                    if success:
                        logger(user.username + " added to Jellyfin with default permissions. (https://api.jellyfin.org/#tag/User/operation/UpdateUserPolicy)", 0)
                    else:
                        logger(user.username + " was not added to Jellyfin. Reason: " + str(failure_reason), 2)
                    #time.sleep(5)
                    break
        else:
            logger(user.username + " already exists in Jellyfin.", 1)
    logger("User migration complete.", 0)
    if user_list:
        logger("Username | Password", 0)
        for k, v in user_list.items():
            logger(str(k) + "  |  " + str(v[1]), 0)