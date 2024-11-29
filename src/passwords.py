import random
import requests
import string
from src.functions import (
    logger
)

DICEWARE_LIST_URL = "https://gist.githubusercontent.com/mingsai/8075fca3cea1ea8943c1f61db66fed13/raw/86fa664c6abb4d8522ce0ee757bf478985ffdf32/dicewarewordlist.txt"

diceware_list = []
# Function to fetch the diceware word list gist from the specified URL
def fetch_diceware_word_list():
    global diceware_list
    try:
        r = requests.get(DICEWARE_LIST_URL) # Fetch the diceware word list
        if r.status_code == 200:
            # Now only take the lines that start with a 6-digit number separated from a word by a space
            words = [line.split() for line in r.text.splitlines()]
            words = [line[1] for line in words if len(line) == 2 and line[0].isdigit() and line[1].isalpha()]
            logger(f"Successfully fetched {len(words)} words from the diceware word list.", 1)
            diceware_list = words
            return True
        else:
            diceware_list = []
            return False
    except Exception as e:
        logger(f"Failed to fetch the diceware word list: {e}", 2)
        diceware_list = []
        return False
    
def diceware_password(length=4):
    # Create a diceware password using `length` words separated by either numbers or a space.
    # Each word will be lower or UPPER case with a 50% chance.
    p = ""

    # Determine the case for the first character randomly
    is_upper = random.choice([True, False])
    for i in range(length):
        if is_upper:
            p += random.choice(diceware_list).upper()
        else:
            p += random.choice(diceware_list).lower()
        # Alternate the case for the next character
        is_upper = not is_upper
        if i < length - 1:
            p += random.choice([str(random.randint(0, 9)), " "])

    return p.strip()

def password(char_length=16, word_length=4):
    if diceware_list or fetch_diceware_word_list():
        return diceware_password(word_length)
    else:
        # Generate a random password of length `length` using ascii letters and digits
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(char_length))