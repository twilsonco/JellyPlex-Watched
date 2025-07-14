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

def update_state_tracking(state_tracker, server_1_watched: Dict[str, Any], server_2_watched: Dict[str, Any], 
                            server_1_name: str, server_2_name: str):
    """
    Update state tracking for all users across both servers
    """
    logger("Starting state tracking update", 1)
    logger(f"Server 1 name: {server_1_name}", 1)
    logger(f"Server 2 name: {server_2_name}", 1)
    
    # Extract current item status from watched data
    all_users = set(list(server_1_watched.keys()) + list(server_2_watched.keys()))
    logger(f"Processing state tracking for {len(all_users)} users: {list(all_users)}", 1)
    
    for user in all_users:
        logger(f"Processing state tracking for user: {user}", 1)
        
        # Process server 1 items
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
        
        # Process server 2 items
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
            
            logger(f"Updated cross-references for user {user}: {updated_s1_refs} on {server_1_name}, {updated_s2_refs} on {server_2_name}", 1)
        else:
            if user not in server_1_watched:
                logger(f"User {user} not in {server_1_name}, skipping cross-server mapping", 1)
            if user not in server_2_watched:
                logger(f"User {user} not in {server_2_name}, skipping cross-server mapping", 1)
    
    logger("State tracking update completed", 1)