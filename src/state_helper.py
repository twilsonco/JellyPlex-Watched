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
    """Extract a unique identifier for an item"""
    # Try common GUID sources in order of preference
    guid_sources = ["imdb", "tmdb", "tvdb", "guid"]
    
    for source in guid_sources:
        if source in item and item[source]:
            item_id = f"{source}://{item[source]}"
            logger(f"Generated ID from {source}: {item_id}", 3)
            return item_id
    
    # Fall back to title + location if no GUID
    if "title" in item and "locations" in item and item["locations"]:
        location = item["locations"][0] if item["locations"] else ""
        item_id = f"title://{item['title']}::{location}"
        logger(f"Generated ID from title+location: {item_id}", 3)
        return item_id
    
    # Last resort: just title
    if "title" in item:
        item_id = f"title://{item['title']}"
        logger(f"Generated ID from title only: {item_id}", 3)
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

def create_cross_server_mapping(server1_items: Dict[str, Any], 
                               server2_items: Dict[str, Any]) -> Dict[str, str]:
    """
    Create mapping between items on two servers
    Returns: {server1_item_id: server2_item_id}
    """
    logger(f"Creating cross-server mapping between {len(server1_items)} and {len(server2_items)} items", 1)
    mapping = {}
    matched_count = 0
    
    for id1, item1 in server1_items.items():
        logger(f"Looking for match for server1 item: {item1.get('title', 'Unknown')} ({id1})", 3)
        
        for id2, item2 in server2_items.items():
            if _items_match(item1, id1, item2, id2):
                mapping[id1] = id2
                matched_count += 1
                logger(f"Matched: {item1.get('title', 'Unknown')} -> {item2.get('title', 'Unknown')}", 1)
                break
        else:
            logger(f"No match found for: {item1.get('title', 'Unknown')} ({id1})", 3)
    
    logger(f"Created cross-server mapping: {matched_count} matches out of {len(server1_items)} items", 1)
    return mapping

def _items_match(item1: Dict[str, Any], id1: str, item2: Dict[str, Any], id2: str) -> bool:
    """Check if two items from different servers represent the same content"""
    logger(f"Comparing items: {id1} vs {id2}", 3)
    
    # If both have GUIDs, try to match on those
    if not id1.startswith("title://") and not id2.startswith("title://"):
        # Extract GUID parts
        source1, guid1 = id1.split("://", 1)
        source2, guid2 = id2.split("://", 1)
        
        # Same GUID source and ID = match
        if source1 == source2 and guid1 == guid2:
            logger(f"GUID match found: {source1}://{guid1}", 3)
            return True
    
    # Fall back to title matching
    title1 = item1.get("title", "").lower().strip()
    title2 = item2.get("title", "").lower().strip()
    
    if title1 and title2 and title1 == title2:
        # For episodes, also check show title
        if item1.get("type") == "episode" and item2.get("type") == "episode":
            show1 = item1.get("show_title", "").lower().strip()
            show2 = item2.get("show_title", "").lower().strip()
            match = show1 == show2
            if match:
                logger(f"Episode title match: {show1} - {title1}", 3)
            else:
                logger(f"Episode title mismatch: show '{show1}' vs '{show2}'", 3)
            return match
        else:
            logger(f"Title match found: {title1}", 3)
            return True
    
    logger(f"No match: '{title1}' vs '{title2}'", 3)
    return False