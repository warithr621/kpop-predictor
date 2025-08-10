from info import KPOP_GROUPS
import musicbrainzngs as mb
from dotenv import load_dotenv
import os
import json
from time import sleep
import pandas as pd

ARTIST_ID_CACHE = "artist_ids.json"

def scrape_artist_ids():
	if os.path.exists(ARTIST_ID_CACHE):
		with open(ARTIST_ID_CACHE, "r") as f:
			artist_ids = json.load(f)
	else:
		artist_ids = {}

	groups = [group for gen in KPOP_GROUPS.values() for group in gen]
	for group in groups:
		if group not in artist_ids:
			result = mb.search_artists(artist=group, limit=5)
			artist_ids[group] = result['artist-list'][0]['id']
			print(f"Updated {group}")
	with open(ARTIST_ID_CACHE, "w") as f:
		json.dump(artist_ids, f, indent=4)

	print("All artist IDs have been retrieved")

def main():
	# set up permissions
	load_dotenv()
	mb.auth(os.getenv("USERNAME"), os.getenv("PASSWORD"))
	mb.set_useragent("walrus_release_predictor", "1.0", os.getenv("EMAIL"))
	# find the ID of all artists, making updates as necessary
	scrape_artist_ids()

if __name__ == "__main__":
	main()