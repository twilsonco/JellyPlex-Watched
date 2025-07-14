import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(override=True)

log_file = os.getenv("LOG_FILE", os.getenv("LOGFILE", "log.log"))
mark_file = os.getenv("MARK_FILE", os.getenv("MARKFILE", "mark.log"))


def rotate_log_file(file_path: str, max_size_mb: int = 10, max_files: int = 5):
    """
    Rotate log file if it exceeds max_size_mb.
    Keeps max_files number of rotated files.
    """
    if not os.path.exists(file_path):
        return
    
    # Check if file size exceeds limit
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb < max_size_mb:
        return
    
    # Rotate existing files
    for i in range(max_files - 1, 0, -1):
        old_file = f"{file_path}.{i}"
        new_file = f"{file_path}.{i + 1}"
        
        if os.path.exists(old_file):
            if i == max_files - 1:
                # Remove the oldest file
                os.remove(old_file)
            else:
                os.rename(old_file, new_file)
    
    # Move current file to .1
    if os.path.exists(file_path):
        os.rename(file_path, f"{file_path}.1")


def write_to_log_file(file_path: str, content: str, max_size_mb: int = 10, max_files: int = 5):
    """
    Write content to log file with optional rotation.
    """
    if file_path is None:
        return
    
    # Get rotation settings from environment variables or use defaults
    max_size_mb = int(os.getenv("LOG_MAX_SIZE_MB", str(max_size_mb)))
    max_files = int(os.getenv("LOG_MAX_FILES", str(max_files)))

    # Rotate if necessary
    rotate_log_file(file_path, max_size_mb, max_files)
    
    # Write content
    with open(file_path, "a", encoding="utf-8") as file:
        file.write(content + "\n")


def logger(message: str, log_type=0):
    debug = str_to_bool(os.getenv("DEBUG", "False"))
    debug_level = os.getenv("DEBUG_LEVEL", "info").lower()
    
    output = str(message)
    if log_type == 0:
        pass
    elif log_type == 1 and (debug_level in ("info", "debug")):
        output = f"[INFO]: {output}"
    elif log_type == 2:
        output = f"[ERROR]: {output}"
    elif log_type == 3 and (debug and debug_level == "debug"):
        output = f"[DEBUG]: {output}"
    elif log_type == 4:
        output = f"[WARNING]: {output}"
    elif log_type == 5:
        output = f"[MARK]: {output}"
    elif log_type == 6:
        output = f"[DRYRUN]: {output}"
    else:
        output = None

    if output is not None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamped_output = f"{timestamp} {output}"
        print(timestamped_output)
        write_to_log_file(log_file, timestamped_output)


def log_marked(
    server_type: str,
    server_name: str,
    username: str,
    library: str,
    movie_show: str,
    episode: str = None,
    duration=None,
):
    if mark_file is None:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = f"{server_type}/{server_name}/{username}/{library}/{movie_show}"

    if episode:
        output += f"/{episode}"

    if duration:
        output += f"/{duration}"

    timestamped_output = f"{timestamp} {output}"
    write_to_log_file(mark_file, timestamped_output)


# Reimplementation of distutils.util.strtobool due to it being deprecated
# Source: https://github.com/PostHog/posthog/blob/01e184c29d2c10c43166f1d40a334abbc3f99d8a/posthog/utils.py#L668
def str_to_bool(value: any) -> bool:
    if not value:
        return False
    return str(value).lower() in ("y", "yes", "t", "true", "on", "1")


# Search for nested element in list
def contains_nested(element, lst):
    if lst is None:
        return None

    for i, item in enumerate(lst):
        if item is None:
            continue
        if element in item:
            return i
        elif element == item:
            return i
    return None


# Get mapped value
def search_mapping(dictionary: dict, key_value: str):
    if key_value in dictionary.keys():
        return dictionary[key_value]
    elif key_value.lower() in dictionary.keys():
        return dictionary[key_value.lower()]
    elif key_value in dictionary.values():
        return list(dictionary.keys())[list(dictionary.values()).index(key_value)]
    elif key_value.lower() in dictionary.values():
        return list(dictionary.keys())[
            list(dictionary.values()).index(key_value.lower())
        ]
    else:
        return None


# Return list of objects that exist in both lists including mappings
def match_list(list1, list2, list_mapping=None):
    output = []
    for element in list1:
        if element in list2:
            output.append(element)
        elif list_mapping:
            element_other = search_mapping(list_mapping, element)
            if element_other in list2:
                output.append(element)

    return output


def future_thread_executor(
    args: list, threads: int = None, override_threads: bool = False
):
    futures_list = []
    results = []

    workers = min(int(os.getenv("MAX_THREADS", 32)), os.cpu_count() * 2)
    if threads:
        workers = min(threads, workers)

    if override_threads:
        workers = threads

    # If only one worker, run in main thread to avoid overhead
    if workers == 1:
        results = []
        for arg in args:
            results.append(arg[0](*arg[1:]))
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for arg in args:
            # * arg unpacks the list into actual arguments
            futures_list.append(executor.submit(*arg))

        for future in futures_list:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                raise Exception(e)

    return results
