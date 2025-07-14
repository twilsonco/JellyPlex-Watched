from typing import Dict, Any
from src.functions import logger

def extract_item_status_from_watched(watched_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Extract item IDs and their status from watched data structure
    Returns: {item_id: {"status": "watched|unwatched|in_progress", "title": str}}
    """
    logger(f"Extracting item status from watched data for {len(watched_data)} users", 1)
    items = {}
    total_movies = 0
    total_episodes = 0
    
    for user, libraries in watched_data.items():
        logger(f"Processing user: {user} with {len(libraries)} libraries", 3)
        
        for library, content in libraries.items():
            logger(f"Processing library: {library}", 3)
            
            # Movies (list structure)
            if isinstance(content, list):
                logger(f"Processing {len(content)} movies in library: {library}", 3)
                for movie in content:
                    item_id = _get_item_id(movie)
                    if item_id:
                        status = _determine_status(movie.get("status", {}))
                        items[item_id] = {
                            "status": status,
                            "title": movie.get("title", "Unknown"),
                            "type": "movie"
                        }
                        total_movies += 1
                        logger(f"Added movie: {movie.get('title', 'Unknown')} ({item_id}) - {status}", 3)
                    else:
                        logger(f"Could not generate ID for movie: {movie.get('title', 'Unknown')}", 2)
            
            # TV Shows (dict structure) 
            elif isinstance(content, dict):
                logger(f"Processing {len(content)} shows in library: {library}", 3)
                for show_key, episodes in content.items():
                    show_dict = dict(show_key) if isinstance(show_key, frozenset) else show_key
                    show_title = show_dict.get("title", "Unknown")
                    logger(f"Processing show: {show_title} with {len(episodes)} episodes", 3)
                    
                    for episode in episodes:
                        item_id = _get_item_id(episode)
                        if item_id:
                            status = _determine_status(episode.get("status", {}))
                            items[item_id] = {
                                "status": status,
                                "title": episode.get("title", "Unknown"),
                                "show_title": show_title,
                                "type": "episode"
                            }
                            total_episodes += 1
                            logger(f"Added episode: {show_title} - {episode.get('title', 'Unknown')} ({item_id}) - {status}", 3)
                        else:
                            logger(f"Could not generate ID for episode: {show_title} - {episode.get('title', 'Unknown')}", 2)
    
    logger(f"Extracted {len(items)} total items: {total_movies} movies, {total_episodes} episodes", 1)
    return items

def _get_item_id(item: Dict[str, Any]) -> str:
    """Extract a unique identifier for an item using server-specific IDs"""
    
    # Priority 1: Use server-specific unique identifiers
    # Plex uses 'guid' field (e.g., "plex://movie/5d776b59ad5437001f79c6f8")
    if "guid" in item and item["guid"]:
        item_id = f"plex://{item['guid']}"
        logger(f"Generated ID from Plex GUID: {item_id}", 3)
        return item_id
    
    # Jellyfin/Emby uses 'Id' field (e.g., "123e4567-e89b-12d3-a456-426614174000")
    if "Id" in item and item["Id"]:
        item_id = f"jellyfin://{item['Id']}"  # Could also be emby:// but they're compatible
        logger(f"Generated ID from Jellyfin/Emby ID: {item_id}", 3)
        return item_id
    
    # Priority 2: Fall back to public catalog IDs (for compatibility)
    guid_sources = ["imdb", "tmdb", "tvdb"]
    for source in guid_sources:
        if source in item and item[source]:
            item_id = f"{source}://{item[source]}"
            logger(f"Generated ID from {source} (fallback): {item_id}", 3)
            return item_id
    
    # Priority 3: Fall back to title + location if no IDs available
    if "title" in item and "locations" in item and item["locations"]:
        location = item["locations"][0] if item["locations"] else ""
        item_id = f"title://{item['title']}::{location}"
        logger(f"Generated ID from title+location (fallback): {item_id}", 3)
        return item_id
    
    # Last resort: just title
    if "title" in item:
        item_id = f"title://{item['title']}"
        logger(f"Generated ID from title only (last resort): {item_id}", 3)
        return item_id
    
    logger(f"Could not generate ID for item: {item}", 2)
    return None

def _determine_status(status_dict: Dict[str, Any]) -> str:
    """Determine watch status from status dictionary"""
    if not status_dict:
        logger("No status dict, returning unwatched", 3)
        return "unwatched"
    
    completed = status_dict.get("completed", False)
    time_watched = status_dict.get("time", 0)
    
    if completed:
        logger(f"Item completed, returning watched", 3)
        return "watched"
    elif time_watched > 60000:  # More than 1 minute watched
        logger(f"Item partially watched ({time_watched}ms), returning in_progress", 3)
        return "in_progress"
    else:
        logger(f"Item not completed and minimal time ({time_watched}ms), returning unwatched", 3)
        return "unwatched"

def update_state_tracking(state_tracker, server_1_watched: Dict[str, Any], server_2_watched: Dict[str, Any], 
                                server_1_name: str, server_2_name: str):
    """
    Update state tracking for all users (without cross-server mapping)
    Cross-server linking will happen during cleanup when items are already matched
    """
    logger("Starting simplified state tracking update", 1)
    
    all_users = set(list(server_1_watched.keys()) + list(server_2_watched.keys()))
    logger(f"Processing state tracking for {len(all_users)} users", 1)
    
    for user in all_users:
        # Process server 1 items
        if user in server_1_watched:
            server_1_items = extract_item_status_from_watched({user: server_1_watched[user]})
            for item_id, item_info in server_1_items.items():
                state_tracker.update_item_state(user, server_1_name, item_id, item_info["status"])
        
        # Process server 2 items  
        if user in server_2_watched:
            server_2_items = extract_item_status_from_watched({user: server_2_watched[user]})
            for item_id, item_info in server_2_items.items():
                state_tracker.update_item_state(user, server_2_name, item_id, item_info["status"])
    
    logger("Simplified state tracking update completed", 1)