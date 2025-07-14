import os, traceback, json
from dotenv import load_dotenv
from time import sleep, perf_counter

from src.library import setup_libraries
from src.functions import (
    logger,
    str_to_bool,
)
from src.users import setup_users
from src.watched import (
    cleanup_watched,
)
from src.black_white import setup_black_white_lists
from src.connection import generate_server_connections
from src.user_sync import sync_plex_users_to_jellyfin
from src.state_tracker import StateTracker
from src.state_helper import extract_item_status_from_watched, create_cross_server_mapping

load_dotenv(override=True)


def should_sync_server(server_1_type, server_2_type):
    sync_from_plex_to_jellyfin = str_to_bool(
        os.getenv("SYNC_FROM_PLEX_TO_JELLYFIN", "True")
    )
    sync_from_plex_to_plex = str_to_bool(os.getenv("SYNC_FROM_PLEX_TO_PLEX", "True"))
    sync_from_plex_to_emby = str_to_bool(os.getenv("SYNC_FROM_PLEX_TO_EMBY", "True"))

    sync_from_jelly_to_plex = str_to_bool(
        os.getenv("SYNC_FROM_JELLYFIN_TO_PLEX", "True")
    )
    sync_from_jelly_to_jellyfin = str_to_bool(
        os.getenv("SYNC_FROM_JELLYFIN_TO_JELLYFIN", "True")
    )
    sync_from_jelly_to_emby = str_to_bool(
        os.getenv("SYNC_FROM_JELLYFIN_TO_EMBY", "True")
    )

    sync_from_emby_to_plex = str_to_bool(os.getenv("SYNC_FROM_EMBY_TO_PLEX", "True"))
    sync_from_emby_to_jellyfin = str_to_bool(
        os.getenv("SYNC_FROM_EMBY_TO_JELLYFIN", "True")
    )
    sync_from_emby_to_emby = str_to_bool(os.getenv("SYNC_FROM_EMBY_TO_EMBY", "True"))

    if server_1_type == "plex":
        if server_2_type == "jellyfin" and not sync_from_plex_to_jellyfin:
            logger("Sync from plex -> jellyfin is disabled", 1)
            return False

        if server_2_type == "emby" and not sync_from_plex_to_emby:
            logger("Sync from plex -> emby is disabled", 1)
            return False

        if server_2_type == "plex" and not sync_from_plex_to_plex:
            logger("Sync from plex -> plex is disabled", 1)
            return False

    if server_1_type == "jellyfin":
        if server_2_type == "plex" and not sync_from_jelly_to_plex:
            logger("Sync from jellyfin -> plex is disabled", 1)
            return False

        if server_2_type == "jellyfin" and not sync_from_jelly_to_jellyfin:
            logger("Sync from jellyfin -> jellyfin is disabled", 1)
            return False

        if server_2_type == "emby" and not sync_from_jelly_to_emby:
            logger("Sync from jellyfin -> emby is disabled", 1)
            return False

    if server_1_type == "emby":
        if server_2_type == "plex" and not sync_from_emby_to_plex:
            logger("Sync from emby -> plex is disabled", 1)
            return False

        if server_2_type == "jellyfin" and not sync_from_emby_to_jellyfin:
            logger("Sync from emby -> jellyfin is disabled", 1)
            return False

        if server_2_type == "emby" and not sync_from_emby_to_emby:
            logger("Sync from emby -> emby is disabled", 1)
            return False

    return True


def main_loop():
    log_file = os.getenv("LOG_FILE", os.getenv("LOGFILE", "log.log"))
    # Delete log_file if it exists
    if os.path.exists(log_file):
        os.remove(log_file)

    dryrun = str_to_bool(os.getenv("DRYRUN", "False"))
    logger(f"Dryrun: {dryrun}", 1)

    user_mapping = os.getenv("USER_MAPPING")
    if user_mapping:
        user_mapping = json.loads(user_mapping.lower())
        logger(f"User Mapping: {user_mapping}", 1)

    library_mapping = os.getenv("LIBRARY_MAPPING")
    if library_mapping:
        library_mapping = json.loads(library_mapping)
        logger(f"Library Mapping: {library_mapping}", 1)

    # Create (black/white)lists
    logger("Creating (black/white)lists", 1)
    blacklist_library = os.getenv("BLACKLIST_LIBRARY", None)
    whitelist_library = os.getenv("WHITELIST_LIBRARY", None)
    blacklist_library_type = os.getenv("BLACKLIST_LIBRARY_TYPE", None)
    whitelist_library_type = os.getenv("WHITELIST_LIBRARY_TYPE", None)
    blacklist_users = os.getenv("BLACKLIST_USERS", None)
    whitelist_users = os.getenv("WHITELIST_USERS", None)

    (
        blacklist_library,
        whitelist_library,
        blacklist_library_type,
        whitelist_library_type,
        blacklist_users,
        whitelist_users,
    ) = setup_black_white_lists(
        blacklist_library,
        whitelist_library,
        blacklist_library_type,
        whitelist_library_type,
        blacklist_users,
        whitelist_users,
        library_mapping,
        user_mapping,
    )
    
    # Initialize state tracker
    config_dir = os.getenv("CONFIG_DIR", "/config")
    state_tracker = StateTracker(config_dir)

    # Create server connections
    logger("Creating server connections", 1)
    servers = generate_server_connections()

    for server_1 in servers:
        # If server is the final server in the list, then we are done with the loop
        if server_1 == servers[-1]:
            break

        # Start server_2 at the next server in the list
        for server_2 in servers[servers.index(server_1) + 1 :]:
            # Check if server 1 and server 2 are going to be synced in either direction, skip if not
            if not should_sync_server(
                server_1[0], server_2[0]
            ) and not should_sync_server(server_2[0], server_1[0]):
                continue

            logger(f"Server 1: {server_1[0].capitalize()}: {server_1[1].info()}", 0)
            logger(f"Server 2: {server_2[0].capitalize()}: {server_2[1].info()}", 0)
            
            # Sync Plex users to Jellyfin
            if all(s[0] in ["plex", "jellyfin"] for s in [server_1, server_2]):
                if server_1[0] == "plex":
                    plex_server = server_1
                    jelly_server = server_2
                else:
                    plex_server = server_2
                    jelly_server = server_1
                sync_plex_users_to_jellyfin(jelly_server)

            # Create users list
            logger("Creating users list", 1)
            server_1_users, server_2_users = setup_users(
                server_1, server_2, blacklist_users, whitelist_users, user_mapping
            )

            server_1_libraries, server_2_libraries = setup_libraries(
                server_1[1],
                server_2[1],
                blacklist_library,
                blacklist_library_type,
                whitelist_library,
                whitelist_library_type,
                library_mapping,
            )

            logger("Creating watched lists", 1)
            server_1_watched = server_1[1].get_watched(
                server_1_users, server_1_libraries
            )
            logger("Finished creating watched list server 1", 1)

            server_2_watched = server_2[1].get_watched(
                server_2_users, server_2_libraries
            )
            logger("Finished creating watched list server 2", 1)

            logger(f"Server 1 watched: {server_1_watched}", 3)
            logger(f"Server 2 watched: {server_2_watched}", 3)
            
            # Track state changes
            logger("Tracking state changes", 1)
            server_1_name = server_1[1].info(name_only=True) if hasattr(server_1[1], 'info') else server_1[0]
            server_2_name = server_2[1].info(name_only=True) if hasattr(server_2[1], 'info') else server_2[0]
            logger(f"Server 1 name: {server_1_name}", 1)
            logger(f"Server 2 name: {server_2_name}", 1)
            
            # Extract current item status from watched data
            all_users = set(list(server_1_watched.keys()) + list(server_2_watched.keys()))
            logger(f"Processing state tracking for {len(all_users)} users: {list(all_users)}", 1)
            
            for user in all_users:
                logger(f"Processing state tracking for user: {user}", 1)
                
                if user in server_1_watched:
                    logger(f"Extracting items from {server_1_name} for user {user}", 1)
                    server_1_items = extract_item_status_from_watched({user: server_1_watched[user]})
                    logger(f"Found {len(server_1_items)} items on {server_1_name} for user {user}", 1)
                    
                    # Update state and detect changes for server 1
                    for item_id, item_info in server_1_items.items():
                        logger(f"Updating state for {server_1_name}: {item_info.get('title', 'Unknown')} ({item_id}) - {item_info['status']}", 3)
                        state_tracker.update_item_state(user, server_1_name, item_id, item_info["status"])
                else:
                    logger(f"User {user} not found in {server_1_name} watched list", 1)
                
                if user in server_2_watched:
                    logger(f"Extracting items from {server_2_name} for user {user}", 1)
                    server_2_items = extract_item_status_from_watched({user: server_2_watched[user]})
                    logger(f"Found {len(server_2_items)} items on {server_2_name} for user {user}", 1)
                    
                    # Update state and detect changes for server 2
                    for item_id, item_info in server_2_items.items():
                        logger(f"Updating state for {server_2_name}: {item_info.get('title', 'Unknown')} ({item_id}) - {item_info['status']}", 3)
                        state_tracker.update_item_state(user, server_2_name, item_id, item_info["status"])
                else:
                    logger(f"User {user} not found in {server_2_name} watched list", 1)
                
                # Create cross-server mapping for items
                if user in server_1_watched and user in server_2_watched:
                    logger(f"Creating cross-server mapping for user {user}", 1)
                    server_1_items = extract_item_status_from_watched({user: server_1_watched[user]})
                    server_2_items = extract_item_status_from_watched({user: server_2_watched[user]})
                    cross_mapping = create_cross_server_mapping(server_1_items, server_2_items)
                    
                    logger(f"Created {len(cross_mapping)} cross-server mappings for user {user}", 1)
                    
                    # Update cross-references in state
                    updated_s1_refs = 0
                    updated_s2_refs = 0
                    
                    for s1_id, s2_id in cross_mapping.items():
                        # Update server 1 item with server 2 reference
                        if state_tracker.get_item_state(user, server_1_name, s1_id):
                            logger(f"Adding cross-reference: {server_1_name} {s1_id} -> {server_2_name} {s2_id}", 3)
                            state_tracker.update_item_state(user, server_1_name, s1_id, 
                                                            server_1_items[s1_id]["status"], s2_id)
                            updated_s1_refs += 1
                        else:
                            logger(f"No state found for {server_1_name} item {s1_id}, skipping cross-reference", 2)
                            
                        # Update server 2 item with server 1 reference  
                        if state_tracker.get_item_state(user, server_2_name, s2_id):
                            logger(f"Adding cross-reference: {server_2_name} {s2_id} -> {server_1_name} {s1_id}", 3)
                            state_tracker.update_item_state(user, server_2_name, s2_id,
                                                            server_2_items[s2_id]["status"], s1_id)
                            updated_s2_refs += 1
                        else:
                            logger(f"No state found for {server_2_name} item {s2_id}, skipping cross-reference", 2)
                    
                    logger(f"Updated cross-references for user {user}: {updated_s1_refs} on {server_1_name}, {updated_s2_refs} on {server_2_name}", 3)
                else:
                    if user not in server_1_watched:
                        logger(f"User {user} not in {server_1_name}, skipping cross-server mapping", 1)
                    if user not in server_2_watched:
                        logger(f"User {user} not in {server_2_name}, skipping cross-server mapping", 1)
            
            # Save state
            logger("Saving state tracker data to disk", 1)
            state_tracker.save()
            logger("State tracking completed successfully", 1)

            logger("Cleaning Server 1 Watched", 1)
            server_1_watched_filtered = cleanup_watched(
                server_1_watched, server_2_watched, user_mapping, library_mapping,
                state_tracker, server_1_name, server_2_name
            )

            logger("Cleaning Server 2 Watched", 1)
            server_2_watched_filtered = cleanup_watched(
                server_2_watched, server_1_watched, user_mapping, library_mapping,
                state_tracker, server_2_name, server_1_name
            )
            
            logger("Finished cleanup_watched", 1)

            logger(
                f"server 1 watched that needs to be synced to server 2:\n{server_1_watched_filtered}",
                3,
            )
            logger(
                f"server 2 watched that needs to be synced to server 1:\n{server_2_watched_filtered}",
                3,
            )

            if should_sync_server(server_2[0], server_1[0]):
                logger(f"Syncing {server_2[1].info()} -> {server_1[1].info()}", 3)
                server_1[1].update_watched(
                    server_2_watched_filtered,
                    user_mapping,
                    library_mapping,
                    dryrun,
                )

            if should_sync_server(server_1[0], server_2[0]):
                logger(f"Syncing {server_1[1].info()} -> {server_2[1].info()}", 3)
                server_2[1].update_watched(
                    server_1_watched_filtered,
                    user_mapping,
                    library_mapping,
                    dryrun,
                )

def main():
    run_only_once = str_to_bool(os.getenv("RUN_ONLY_ONCE", "False"))
    sleep_duration = float(os.getenv("SLEEP_DURATION", "3600"))
    times = []
    while True:
        try:
            start = perf_counter()
            main_loop()
            end = perf_counter()
            times.append(end - start)

            if len(times) > 0:
                logger(f"Average time: {sum(times) / len(times)}", 0)

            if run_only_once:
                break

            logger(f"Looping in {sleep_duration}")
            sleep(sleep_duration)

        except Exception as error:
            if isinstance(error, list):
                for message in error:
                    logger(message, log_type=2)
            else:
                logger(error, log_type=2)

            logger(traceback.format_exc(), 2)

            if run_only_once:
                break

            logger(f"Retrying in {sleep_duration}", log_type=0)
            sleep(sleep_duration)

        except KeyboardInterrupt:
            if len(times) > 0:
                logger(f"Average time: {sum(times) / len(times)}", 0)
            logger("Exiting", log_type=0)
            os._exit(0)
