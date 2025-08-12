import json
import os
import re
from time import sleep
from typing import Dict, List, Optional, Tuple

import musicbrainzngs as mb
import pandas as pd
from dotenv import load_dotenv

from info import KPOP_GROUPS

ARTIST_ID_CACHE = "artist_ids.json"
groups = [group for gen in KPOP_GROUPS.values() for group in gen]



def permissions_setup():
	load_dotenv()
	mb.auth(os.getenv("USERNAME"), os.getenv("PASSWORD"))
	mb.set_useragent("walrus_release_predictor", "1.0", os.getenv("EMAIL"))


def scrape_artist_ids():
	if os.path.exists(ARTIST_ID_CACHE):
		with open(ARTIST_ID_CACHE, "r") as f:
			artist_ids = json.load(f)
	else:
		artist_ids = {}

	for group in groups:
		if group not in artist_ids:
			result = mb.search_artists(artist=group, limit=5)
			artist_ids[group] = result['artist-list'][0]['id']
			print(f"Updated {group}")
			# TODO: there is a slight error with this, as it failed to correctly fetch izna (another artist appeared before it... oops)

	with open(ARTIST_ID_CACHE, "w") as f:
		json.dump(artist_ids, f, indent=4)
	print("All artist IDs have been retrieved")


def sanitize(name: str) -> str:
	name = name.strip()
	name = re.sub(r"[\/\\\:\*\?\"<>\|]+", "_", name)
	name = re.sub(r"\s+", "_", name)
	return name


def artist_album_fetch(id: str, pause: float=1.0, limit: int=100) -> List[Dict]:
	rows = []
	offset = 0
	while True:
		response = mb.browse_release_groups(artist=id, limit=limit, offset=offset)
		release_groups = response.get('release-group-list', [])
		total = int(response.get('release-group-count', 0) or 0)
		if not release_groups:
			break
		for release in release_groups:
			r_type = (release.get('type') or '').lower()
			if r_type not in ('album', 'ep', 'single'): continue
			r_type = r_type.upper() if r_type == 'ep' else r_type.capitalize()
			title, date = release.get('title'), release.get('first-release-date')
			if any(word in title.lower() for word in ('remix', 'ver.', 'version', 'edit')):
				continue 
				# many remixes tend to be released on the same day or very close to the original, so this could be an easy skew
			rows.append({
				'title': title,
				'type': r_type,
				'release_date': date
			})
		offset += len(release_groups)
		if offset >= total:
			break
		sleep(pause)

	if rows:
		kept = {}
		for r in rows:
			title_norm = (r.get('title') or '').strip().lower()
			type_val = r.get('type')
			key = (title_norm, type_val)

			dt = pd.to_datetime(r.get('release_date'), errors='coerce')
			cmp_dt = dt if not pd.isna(dt) else pd.Timestamp.max
			if key not in kept or cmp_dt < kept[key][0]:
				kept[key] = (cmp_dt, r)

		# remove all duplicates (e.g. an artist releasing a song and then not too long later releases a jpn ver of same song/album)
		def _sort_key(item):
			d = pd.to_datetime(item.get('release_date'), errors='coerce')
			return d if not pd.isna(d) else pd.Timestamp.max

		rows = [v[1] for v in kept.values()]
		rows.sort(key=_sort_key)
	return rows


def scrape_albums():
	artist_cache = {} if not os.path.exists(ARTIST_ID_CACHE) else json.load(open(ARTIST_ID_CACHE, 'r', encoding='utf-8'))
	for group in groups:
		path = os.path.join("albums", sanitize(group) + '.csv')
		if os.path.exists(path): continue
		id = artist_cache[group]
		if not id: continue
		
		rows = artist_album_fetch(id)
		with open(path, 'w', encoding='utf-8') as f:
			f.write('title,type,release_date\n')
			for r in rows:
				title = r['title'].replace('"', '""')
				type = r['type']
				date = r['release_date']
				f.write(f'"{title}",{type},{date}\n')

		# make sure to sort the CSV by release date
		pd.read_csv(path).sort_values(by='release_date').to_csv(path, index=False)
		print(f"Finished processing {group}")
	print("All artist albums have been retrieved")


def main():
	permissions_setup()
	scrape_artist_ids()
	scrape_albums()


if __name__ == "__main__":
	main()