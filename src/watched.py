import copy

from src.functions import logger, search_mapping, contains_nested
from src.library import generate_library_guids_dict
from src.state_helper import _get_item_id


def check_remove_entry(video, library, video_index, library_watched_list_2, state_tracker=None, 
                      user=None, server_1_name=None, server_2_name=None):
    """
    Enhanced check_remove_entry that considers state tracking for unwatched sync
    """
    if video_index is None:
        return False
    
    # Get current status from both servers
    completed_1 = video["status"]["completed"]
    time_1 = video["status"]["time"]
    completed_2 = library_watched_list_2["completed"][video_index]
    time_2 = library_watched_list_2["time"][video_index]
    
    # If state tracking is available, check for recent unwatched changes
    if state_tracker and user and server_1_name and server_2_name:
        
        # Generate proper item ID using the same logic as state tracking
        video_id = _get_item_id(video)
        
        if video_id:
            # Check if this item was recently marked as unwatched on either server
            recent_unwatched_s1 = state_tracker.get_recent_unwatched_items(user, server_1_name, 60)
            recent_unwatched_s2 = state_tracker.get_recent_unwatched_items(user, server_2_name, 60)
            
            # If item was recently unwatched on server 1, don't remove it (let it sync to server 2)
            if video_id in recent_unwatched_s1:
                logger(f"Not removing {video['title']} - recently marked unwatched on {server_1_name}", 1)
                return False
                
            # If item was recently unwatched on server 2, remove it (server 2 takes precedence)
            if video_id in recent_unwatched_s2:
                logger(f"Removing {video['title']} - recently marked unwatched on {server_2_name}", 1)
                return True
        else:
            logger(f"Could not generate item ID for {video.get('title', 'Unknown')}, using fallback logic", 3)
    
    # Original logic for standard cases
    if (completed_2 == completed_1) and (time_2 == time_1):
        logger(f"Removing {video['title']} from {library} due to exact match", 3)
        return True
    elif (completed_2 == True and completed_1 == False):
        logger(f"Removing {video['title']} from {library} due to being complete in one library and not the other", 3)
        return True
    elif (completed_2 == False and completed_1 == False) and (time_1 < time_2):
        logger(f"Removing {video['title']} from {library} due to more time watched in one library than the other", 3)
        return True
    elif (completed_2 == True and completed_1 == True):
        logger(f"Removing {video['title']} from {library} due to being complete in both libraries", 3)
        return True

    return False


def cleanup_watched(watched_list_1, watched_list_2, user_mapping=None, library_mapping=None, 
                    state_tracker=None, server_1_name=None, server_2_name=None):
    """
    Enhanced cleanup_watched that considers state tracking for bidirectional sync
    """
    logger(f"Starting cleanup_watched with state tracking: {state_tracker is not None}", 1)
    logger(f"Server names: {server_1_name} -> {server_2_name}", 1)
    
    modified_watched_list_1 = copy.deepcopy(watched_list_1)
    items_removed_for_unwatched = 0
    items_removed_standard = 0

    # remove entries from watched_list_1 that are in watched_list_2
    for user_1 in watched_list_1:
        logger(f"Processing cleanup for user: {user_1}", 1)
        
        user_other = None
        if user_mapping:
            user_other = search_mapping(user_mapping, user_1)
            logger(f"User mapping: {user_1} -> {user_other}", 3)
        user_2 = get_other(watched_list_2, user_1, user_other)
        if user_2 is None:
            logger(f"User {user_1} not found in watched_list_2, skipping", 1)
            continue

        logger(f"Processing libraries for user {user_1} -> {user_2}", 1)
        for library_1 in watched_list_1[user_1]:
            library_other = None
            if library_mapping:
                library_other = search_mapping(library_mapping, library_1)
                logger(f"Library mapping: {library_1} -> {library_other}", 3)
            library_2 = get_other(watched_list_2[user_2], library_1, library_other)
            if library_2 is None:
                logger(f"Library {library_1} not found in watched_list_2 for user {user_2}, skipping", 1)
                continue

            logger(f"Processing library: {library_1} -> {library_2}", 1)
            (
                _,
                episode_watched_list_2_keys_dict,
                movies_watched_list_2_keys_dict,
            ) = generate_library_guids_dict(watched_list_2[user_2][library_2])

            # Movies
            if isinstance(watched_list_1[user_1][library_1], list):
                logger(f"Processing {len(watched_list_1[user_1][library_1])} movies in {library_1}", 1)
                movies_to_remove = []
                
                for movie in watched_list_1[user_1][library_1]:
                    movie_index = get_movie_index_in_dict(movie, movies_watched_list_2_keys_dict)
                    if movie_index is not None:
                        logger(f"Found match for movie: {movie['title']}", 3)
                        should_remove = check_remove_entry(
                            movie, library_1, movie_index, movies_watched_list_2_keys_dict,
                            state_tracker, user_1, server_1_name, server_2_name
                        )
                        if should_remove:
                            movies_to_remove.append(movie)
                            if state_tracker:
                                # Check if this was removed due to unwatched sync
                                recent_unwatched = state_tracker.get_recent_unwatched_items(user_1, server_2_name, 60)
                                if any(movie['title'] in str(item_id) for item_id in recent_unwatched.keys()):
                                    items_removed_for_unwatched += 1
                                else:
                                    items_removed_standard += 1
                            else:
                                items_removed_standard += 1
                    else:
                        logger(f"No match found for movie: {movie['title']}", 3)
                
                # Remove movies outside the iteration loop
                for movie in movies_to_remove:
                    logger(f"Removing movie: {movie['title']} from {library_1}", 1)
                    modified_watched_list_1[user_1][library_1].remove(movie)

            # TV Shows
            elif isinstance(watched_list_1[user_1][library_1], dict):
                logger(f"Processing {len(watched_list_1[user_1][library_1])} shows in {library_1}", 1)
                shows_to_remove = []
                
                for show_key_1 in watched_list_1[user_1][library_1].keys():
                    show_key_dict = dict(show_key_1)
                    logger(f"Processing show: {show_key_dict.get('title', 'Unknown')}", 3)

                    # Filter the episode_watched_list_2_keys_dict dictionary to handle cases
                    # where episode location names are not unique such as S01E01.mkv
                    filtered_episode_watched_list_2_keys_dict = (
                        filter_episode_watched_list_2_keys_dict(
                            episode_watched_list_2_keys_dict, show_key_dict
                        )
                    )
                    
                    episodes_to_remove = []
                    for episode in watched_list_1[user_1][library_1][show_key_1]:
                        episode_index = get_episode_index_in_dict(
                            episode, filtered_episode_watched_list_2_keys_dict
                        )
                        if episode_index is not None:
                            logger(f"Found match for episode: {episode['title']}", 3)
                            should_remove = check_remove_entry(
                                episode, library_1, episode_index, episode_watched_list_2_keys_dict,
                                state_tracker, user_1, server_1_name, server_2_name
                            )
                            if should_remove:
                                episodes_to_remove.append(episode)
                                if state_tracker:
                                    recent_unwatched = state_tracker.get_recent_unwatched_items(user_1, server_2_name, 60)
                                    if any(episode['title'] in str(item_id) for item_id in recent_unwatched.keys()):
                                        items_removed_for_unwatched += 1
                                    else:
                                        items_removed_standard += 1
                                else:
                                    items_removed_standard += 1
                        else:
                            logger(f"No match found for episode: {episode['title']}", 3)
                    
                    # Remove episodes outside the iteration loop
                    for episode in episodes_to_remove:
                        logger(f"Removing episode: {episode['title']} from show {show_key_dict.get('title', 'Unknown')}", 1)
                        modified_watched_list_1[user_1][library_1][show_key_1].remove(episode)

                    # Remove empty shows
                    if len(modified_watched_list_1[user_1][library_1][show_key_1]) == 0:
                        logger(f"Marking show for removal: {show_key_dict['title']} (no episodes left)", 1)
                        shows_to_remove.append(show_key_1)
                
                # Remove empty shows outside the iteration loop
                for show_key in shows_to_remove:
                    show_dict = dict(show_key)
                    logger(f"Removing empty show: {show_dict['title']}", 1)
                    del modified_watched_list_1[user_1][library_1][show_key]

    # Clean up empty libraries and users
    users_to_remove = []
    for user_1 in watched_list_1:
        if user_1 in modified_watched_list_1:
            libraries_to_remove = []
            for library_1 in watched_list_1[user_1]:
                if library_1 in modified_watched_list_1[user_1]:
                    # If library is empty then remove it
                    if len(modified_watched_list_1[user_1][library_1]) == 0:
                        logger(f"Marking library for removal: {library_1} from {user_1} (empty)", 1)
                        libraries_to_remove.append(library_1)
            
            # Remove empty libraries
            for library in libraries_to_remove:
                del modified_watched_list_1[user_1][library]

            # If user is empty delete user
            if len(modified_watched_list_1[user_1]) == 0:
                logger(f"Marking user for removal: {user_1} (no libraries left)", 1)
                users_to_remove.append(user_1)
    
    # Remove empty users
    for user in users_to_remove:
        del modified_watched_list_1[user]

    # Log summary
    total_removed = items_removed_standard + items_removed_for_unwatched
    logger(f"Cleanup complete: {total_removed} items removed ({items_removed_standard} standard, {items_removed_for_unwatched} unwatched sync)", 1)
    
    return modified_watched_list_1


def get_other(watched_list, object_1, object_2):
    if object_1 in watched_list:
        return object_1
    elif object_2 in watched_list:
        return object_2
    else:
        logger(f"{object_1} and {object_2} not found in watched list 2", 1)
        return None


def get_movie_index_in_dict(movie, movies_watched_list_2_keys_dict):
    # Iterate through the keys and values of the movie dictionary
    for movie_key, movie_value in movie.items():
        # If the key is "locations", check if the "locations" key is present in the movies_watched_list_2_keys_dict dictionary
        if movie_key == "locations":
            if "locations" in movies_watched_list_2_keys_dict.keys():
                # Iterate through the locations in the movie dictionary
                for location in movie_value:
                    # If the location is in the movies_watched_list_2_keys_dict dictionary, return index of the key
                    return contains_nested(
                        location, movies_watched_list_2_keys_dict["locations"]
                    )

        # If the key is not "locations", check if the movie_key is present in the movies_watched_list_2_keys_dict dictionary
        else:
            if movie_key in movies_watched_list_2_keys_dict.keys():
                # If the movie_value is in the movies_watched_list_2_keys_dict dictionary, return True
                if movie_value in movies_watched_list_2_keys_dict[movie_key]:
                    return movies_watched_list_2_keys_dict[movie_key].index(movie_value)

    # If the loop completes without finding a match, return False
    return None


def filter_episode_watched_list_2_keys_dict(
    episode_watched_list_2_keys_dict, show_key_dict
):
    # If the episode_watched_list_2_keys_dict dictionary is empty, missing show then return an empty dictionary
    if (
        len(episode_watched_list_2_keys_dict) == 0
        or "show" not in episode_watched_list_2_keys_dict.keys()
    ):
        return {}

    # Filter the episode_watched_list_2_keys_dict dictionary to only include values for the correct show
    filtered_episode_watched_list_2_keys_dict = {}
    show_indecies = []

    # Iterate through episode_watched_list_2_keys_dict["show"] and find the indecies that match show_key_dict
    for show_index, show_value in enumerate(episode_watched_list_2_keys_dict["show"]):
        # Iterate through the keys and values of the show_value dictionary and check if they match show_key_dict
        for show_key, show_key_value in show_value.items():
            if show_key == "locations":
                # Iterate through the locations in the show_value dictionary
                for location in show_key_value:
                    # If the location is in the episode_watched_list_2_keys_dict dictionary, return index of the key
                    if (
                        contains_nested(location, show_key_dict["locations"])
                        is not None
                    ):
                        show_indecies.append(show_index)
                        break
            else:
                if show_key in show_key_dict.keys():
                    if show_key_value == show_key_dict[show_key]:
                        show_indecies.append(show_index)
                        break

    # lists
    indecies = list(set(show_indecies))

    # If there are no indecies that match the show, return an empty dictionary
    if len(indecies) == 0:
        return {}

    # Create a copy of the dictionary with indecies that match the show and none that don't
    for key, value in episode_watched_list_2_keys_dict.items():
        if key not in filtered_episode_watched_list_2_keys_dict:
            filtered_episode_watched_list_2_keys_dict[key] = []

        for index, _ in enumerate(value):
            if index in indecies:
                filtered_episode_watched_list_2_keys_dict[key].append(value[index])
            else:
                filtered_episode_watched_list_2_keys_dict[key].append(None)

    return filtered_episode_watched_list_2_keys_dict


def get_episode_index_in_dict(episode, episode_watched_list_2_keys_dict):
    # Iterate through the keys and values of the episode dictionary
    for episode_key, episode_value in episode.items():
        if episode_key in episode_watched_list_2_keys_dict.keys():
            if episode_key == "locations":
                # Iterate through the locations in the episode dictionary
                for location in episode_value:
                    # If the location is in the episode_watched_list_2_keys_dict dictionary, return index of the key
                    return contains_nested(
                        location, episode_watched_list_2_keys_dict["locations"]
                    )

            else:
                # If the episode_value is in the episode_watched_list_2_keys_dict dictionary, return True
                if episode_value in episode_watched_list_2_keys_dict[episode_key]:
                    return episode_watched_list_2_keys_dict[episode_key].index(
                        episode_value
                    )

    # If the loop completes without finding a match, return False
    return None
