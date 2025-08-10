# K-pop groups organized by generation
KPOP_GROUPS = {
	'3rd Gen': [
		'EXO',
		'BTS',
		'GOT7',
		'MAMAMOO',
		'Red Velvet',
		'GFRIEND',
		'Monsta X',
		'TWICE',
		'BLACKPINK',
		'MOMOLAND'
	],
	
	'4th Gen': [
		'fromis_9',
		'Stray Kids',
		'i-dle',
		'LOONA',
		'ATEEZ',
		'IZ*ONE',
		'ITZY',
		'TXT',
		'EVERGLOW',
		'TREASURE',
		'P1Harmony',
		'STAYC',
		'aespa',
		'ENHYPEN',
		'NiziU',
		'IVE',
		'Kep1er',
		'NMIXX',
		'LE SSERAFIM',
		'NewJeans'
	],
	
	'5th Gen': [
		'tripleS',
		'BOYNEXTDOOR',
		'KISS OF LIFE',
		'ZEROBASEONE',
		'RIIZE',
		'BABYMONSTER',
		'TWS',
		'ARTMS',
		'BADVILLAIN',
		'MEOVV',
		'IZNA',
		'Hearts2Hearts',
		'IFEYE',
		'ILLIT'
	]
}

# Company name mappings (MusicBrainz label names -> standardized names)
COMPANY_MAPPINGS = {
	# Major companies
	'JYP': 'JYPE',
	'JYP Entertainment': 'JYPE',
	'JYP Entertainment Co., Ltd.': 'JYPE',
	
	'SM': 'SM Entertainment',
	'SM Entertainment': 'SM Entertainment',
	'SM Entertainment Co., Ltd.': 'SM Entertainment',
	
	'HYBE': 'HYBE',
	'Big Hit': 'HYBE',
	'BigHit': 'HYBE',
	'Big Hit Entertainment': 'HYBE',
	'BigHit Entertainment': 'HYBE',
	'HYBE Labels': 'HYBE',
	
	'YG': 'YG Entertainment',
	'YG Entertainment': 'YG Entertainment',
	'YG Entertainment Inc.': 'YG Entertainment',
	
	# Other companies
	'Cube': 'Cube Entertainment',
	'Cube Entertainment': 'Cube Entertainment',
	'Cube Entertainment Inc.': 'Cube Entertainment',
	
	'Starship': 'Starship Entertainment',
	'Starship Entertainment': 'Starship Entertainment',
	
	'FNC': 'FNC Entertainment',
	'FNC Entertainment': 'FNC Entertainment',
	
	'Pledis': 'Pledis Entertainment',
	'Pledis Entertainment': 'Pledis Entertainment',
	
	'Source': 'Source Music',
	'Source Music': 'Source Music',
	
	'ADOR': 'ADOR',
	'ADOR Entertainment': 'ADOR',
	
	'Kakao': 'Kakao Entertainment',
	'Kakao Entertainment': 'Kakao Entertainment',
	
	'RBW': 'RBW',
	'RBW Entertainment': 'RBW',
	
	'WM': 'WM Entertainment',
	'WM Entertainment': 'WM Entertainment',
	
	'Plan A': 'Plan A Entertainment',
	'Plan A Entertainment': 'Plan A Entertainment',
	
	'MBK': 'MBK Entertainment',
	'MBK Entertainment': 'MBK Entertainment',
	
	'TS': 'TS Entertainment',
	'TS Entertainment': 'TS Entertainment',
	
	'DSP': 'DSP Media',
	'DSP Media': 'DSP Media',
	
	'Jellyfish': 'Jellyfish Entertainment',
	'Jellyfish Entertainment': 'Jellyfish Entertainment',
	
	'Fantagio': 'Fantagio',
	'Fantagio Entertainment': 'Fantagio',
	
	'Happy Face': 'Happy Face Entertainment',
	'Happy Face Entertainment': 'Happy Face Entertainment',
	
	'Maroo': 'Maroo Entertainment',
	'Maroo Entertainment': 'Maroo Entertainment',
	
	'Chrome': 'Chrome Entertainment',
	'Chrome Entertainment': 'Chrome Entertainment',
	
	'B2M': 'B2M Entertainment',
	'B2M Entertainment': 'B2M Entertainment',
	
	'LOEN': 'LOEN Entertainment',
	'LOEN Entertainment': 'LOEN Entertainment',
	
	'CJ E&M': 'CJ E&M',
	'CJ Entertainment': 'CJ E&M',
	
	'Kakao M': 'Kakao Entertainment',
	'Kakao Music': 'Kakao Entertainment'
}

# Generation mappings for specific groups (can override automatic detection)
GENERATION_MAPPINGS = {
	# 3rd Generation
	'EXO': '3rd Gen',
	'BTS': '3rd Gen',
	'GOT7': '3rd Gen',
	'MAMAMOO': '3rd Gen',
	'Red Velvet': '3rd Gen',
	'GFRIEND': '3rd Gen',
	'Monsta X': '3rd Gen',
	'TWICE': '3rd Gen',
	'BLACKPINK': '3rd Gen',
	'MOMOLAND': '3rd Gen',
	
	# 4th Generation
	'fromis_9': '4th Gen',
	'Stray Kids': '4th Gen',
	'(G)I-DLE': '4th Gen',
	'LOONA': '4th Gen',
	'ATEEZ': '4th Gen',
	'IZ*ONE': '4th Gen',
	'ITZY': '4th Gen',
	'TXT': '4th Gen',
	'EVERGLOW': '4th Gen',
	'TREASURE': '4th Gen',
	'P1Harmony': '4th Gen',
	'STAYC': '4th Gen',
	'aespa': '4th Gen',
	'ENHYPEN': '4th Gen',
	'NiziU': '4th Gen',
	'IVE': '4th Gen',
	'Kep1er': '4th Gen',
	'NMIXX': '4th Gen',
	'LE SSERAFIM': '4th Gen',
	'NewJeans': '4th Gen',
	
	# 5th Generation
	'tripleS': '5th Gen',
	'BOYNEXTDOOR': '5th Gen',
	'KISS OF LIFE': '5th Gen',
	'ZEROBASEONE': '5th Gen',
	'RIIZE': '5th Gen',
	'BABYMONSTER': '5th Gen',
	'TWS': '5th Gen',
	'ARTMS': '5th Gen',
	'BADVILLAIN': '5th Gen',
	'MEOVV': '5th Gen',
	'IZNA': '5th Gen',
	'Hearts2Hearts': '5th Gen',
	'IFEYE': '5th Gen',
	'ILLIT': '5th Gen'
}