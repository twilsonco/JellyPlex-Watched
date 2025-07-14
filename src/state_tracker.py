import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.functions import logger

class StateTracker:
    def __init__(self, config_dir: str = "/config"):
        self.config_dir = config_dir
        default_state_file = os.path.join(config_dir, "watched_state.json")
        self.state_file = os.getenv("WATCHED_STATE_FILE", default_state_file)
        
        logger(f"Initializing StateTracker with config dir: {config_dir}", 1)
        logger(f"State file path: {self.state_file}", 1)
        self.state = self._load_state()
        
    def _load_state(self) -> Dict[str, Any]:
        """Load state from JSON file"""
        try:
            if os.path.exists(self.state_file):
                logger(f"Loading existing state file: {self.state_file}", 1)
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                logger(f"Loaded state with {len(state)} users", 1)
                return state
            else:
                logger("State file not found, creating new state", 1)
                return {}
        except Exception as e:
            logger(f"Error loading state file: {e}, creating new state", 2)
            return {}
    
    def _save_state(self):
        """Save state to JSON file"""
        try:
            # Ensure config directory exists
            os.makedirs(self.config_dir, exist_ok=True)
            logger(f"Saving state to: {self.state_file}", 1)
            
            # Write to temp file first, then rename for atomicity
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, separators=(',', ':'))
            os.rename(temp_file, self.state_file)
            
            # Log state summary
            total_users = len(self.state)
            total_items = sum(
                len(servers.get(server, {})) 
                for servers in self.state.values() 
                for server in servers
            )
            logger(f"State saved successfully: {total_users} users, {total_items} total items", 1)
            
        except Exception as e:
            logger(f"Error saving state file: {e}", 2)
            raise Exception(e)
    
    def get_item_state(self, user: str, server_name: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Get current state for an item"""
        state = self.state.get(user, {}).get(server_name, {}).get(item_id)
        if state:
            logger(f"Found state for {user}/{server_name}/{item_id}: {state['status']}", 3)
        else:
            logger(f"No state found for {user}/{server_name}/{item_id}", 3)
        return state
    
    def update_item_state(self, user: str, server_name: str, item_id: str, 
                            status: str, other_server_id: str = None):
        """Update state for an item"""
        logger(f"Updating state for {user}/{server_name}/{item_id}: {status}", 3)
        
        if user not in self.state:
            self.state[user] = {}
            logger(f"Created new user entry: {user}", 1)
        if server_name not in self.state[user]:
            self.state[user][server_name] = {}
            logger(f"Created new server entry for {user}: {server_name}", 1)
            
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Check if this is a status change
        old_state = self.state[user][server_name].get(item_id)
        if old_state and old_state.get("status") != status:
            logger(f"Status change detected for {user}/{server_name}/{item_id}: {old_state['status']} -> {status}", 1)
        
        item_state = {
            "status": status,
            "last_checked": current_time
        }
        
        if other_server_id:
            item_state["other_server_id"] = other_server_id
            logger(f"Set cross-server reference: {item_id} -> {other_server_id}", 3)
            
        self.state[user][server_name][item_id] = item_state
    
    def save(self):
        """Save current state to file"""
        logger("Saving state tracker data", 1)
        self._save_state()
        
    def get_recent_unwatched_items(self, user: str, server_name: str, 
                                since_minutes: int = 60) -> Dict[str, Any]:
        """Get items that were recently marked as unwatched"""
        logger(f"Getting recent unwatched items for {user}/{server_name} (last {since_minutes} minutes)", 1)
        recent_unwatched = {}
        cutoff_time = datetime.now(timezone.utc).timestamp() - (since_minutes * 60)
        
        if user in self.state and server_name in self.state[user]:
            for item_id, item_state in self.state[user][server_name].items():
                if item_state["status"] == "unwatched":
                    last_checked = datetime.fromisoformat(item_state["last_checked"]).timestamp()
                    if last_checked > cutoff_time:
                        recent_unwatched[item_id] = item_state
                        logger(f"Found recent unwatched item: {item_id}", 1)
        
        logger(f"Found {len(recent_unwatched)} recently unwatched items", 1)
        return recent_unwatched