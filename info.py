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

# group -> parent company 
GROUP_COMPANIES = {
	# 3rd Gen
	'EXO': 'SM Entertainment',
	'BTS': 'HYBE',
	'GOT7': 'JYPE',
	'MAMAMOO': 'RBW',
	'Red Velvet': 'SM Entertainment',
	'GFRIEND': 'HYBE',
	'Monsta X': 'Starship Entertainment',
	'TWICE': 'JYPE',
	'BLACKPINK': 'YG Entertainment',
	'MOMOLAND': 'MLD Entertainment',

	# 4th Gen
	'fromis_9': 'HYBE',
	'Stray Kids': 'JYPE',
	'i-dle': 'Cube Entertainment',
	'LOONA': 'BlockBerry Creative',
	'ATEEZ': 'KQ Entertainment',
	'IZ*ONE': 'CJ E&M',
	'ITZY': 'JYPE',
	'TXT': 'HYBE',
	'EVERGLOW': 'Yuehua Entertainment',
	'TREASURE': 'YG Entertainment',
	'P1Harmony': 'FNC Entertainment',
	'STAYC': 'High Up Entertainment',
	'aespa': 'SM Entertainment',
	'ENHYPEN': 'HYBE',
	'NiziU': 'JYPE',
	'IVE': 'Starship Entertainment',
	'Kep1er': 'CJ E&M',
	'NMIXX': 'JYPE',
	'LE SSERAFIM': 'HYBE',
	'NewJeans': 'HYBE',

	# 5th Gen
	'tripleS': 'MODHAUS',
	'BOYNEXTDOOR': 'HYBE',
	'KISS OF LIFE': 'S2 Entertainment',
	'ZEROBASEONE': 'CJ E&M',
	'RIIZE': 'SM Entertainment',
	'BABYMONSTER': 'YG Entertainment',
	'TWS': 'HYBE',
	'ARTMS': 'MODHAUS',
	'BADVILLAIN': 'One Hundred',
	'MEOVV': 'THE BLACK LABEL',
	'IZNA': 'CJ E&M',
	'Hearts2Hearts': 'SM Entertainment',
	'IFEYE': 'Hi-Hat Entertainment',
	'ILLIT': 'HYBE'
}

# keep special note of all retired groups
RETIRED_GROUPS = [
	'GFRIEND',  # disbanded officially in 2021, although they did perform a 10th anniversary project in 2025
	'MOMOLAND', # disbanded officially in 2023, although reuniting in 2025 via exclusive contracts
	'IZ*ONE'    # disbanded in 2021
]