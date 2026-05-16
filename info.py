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
		'ATEEZ',
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
		'LE SSERAFIM'
	],
	
	'5th Gen': [
		'tripleS',
		'BOYNEXTDOOR',
		'KISS OF LIFE',
		'RIIZE',
		'BABYMONSTER',
		'TWS',
		'ARTMS',
		'BADVILLAIN',
		'MEOVV',
		'izna',
		'Hearts2Hearts',
		'IFEYE',
		'ILLIT'
	],
}


# make note of all soloists + subunits that have released music separately from their groups
# I could def miss songs from this :sob:
SOLOISTS = {
	'HUH YUNJIN': 'LE SSERAFIM',
	'3RACHA': 'Stray Kids',
	'Yeji': 'ITZY',
	'YUN (STAYC)': 'STAYC',
	'YEONJUN (TXT)': 'TXT',
	'BEOMGYU': 'TXT',
	'JEON SOYEON': 'i-dle',
	'Miyeon': 'i-dle',
	'Yuqi': 'i-dle',
	'MINNIE (i-dle)': 'i-dle',

	'JENNIE': 'BLACKPINK',
	'ROSE': 'BLACKPINK',
	'LISA (BLACKPINK)': 'BLACKPINK',
	'JISOO': 'BLACKPINK',
	'TZUYU': 'TWICE',
	'NAYEON': 'TWICE',
	'JIHYO': 'TWICE',
	'MISAMO': 'TWICE',
	'Shownu': 'Monsta X',
	'KIHYUN': 'Monsta X',
	'JOOHONEY': 'Monsta X',
	'I.M': 'Monsta X',
	'IRENE (Red Velvet)': 'Red Velvet',
	'SEULGI': 'Red Velvet',
	'WENDY (Red Velvet)': 'Red Velvet',
	'JOY (Red Velvet)': 'Red Velvet',
	'YERI': 'Red Velvet',
	'Moon Byul': 'MAMAMOO',
	'Whee In': 'MAMAMOO',
	'SOLAR (MAMAMOO)': 'MAMAMOO',
	'HWASA': 'MAMAMOO',
	'Mark Tuan': 'GOT7',
	'Jay B': 'GOT7',
	'Jackson Wang': 'GOT7',
	'Youngjae': 'GOT7',
	'BAMBAM': 'GOT7',
	'Yugyeom': 'GOT7',
	'JIN (BTS)': 'BTS',
	'SUGA (BTS)': 'BTS',
	'j-hope': 'BTS',
	'RM': 'BTS',
	'Jimin': 'BTS',
	'V (BTS)': 'BTS',
	'Jung Kook': 'BTS',
	'Xiumin': 'EXO',
	'SUHO': 'EXO',
	'LAY': 'EXO',
	'Baekhyun': 'EXO',
	'Chen': 'EXO',
	'Chanyeol': 'EXO',
	'D.O.': 'EXO',
	'KAI (EXO)': 'EXO',
	'Sehun': 'EXO'
}


# Generation mappings for specific groups (can override automatic detection)
GENERATION_MAPPINGS = {
	# 3rd Generation
	'EXO': 3,
	'BTS': 3,
	'GOT7': 3,
	'MAMAMOO': 3,
	'Red Velvet': 3,
	'GFRIEND': 3,
	'Monsta X': 3,
	'TWICE': 3,
	'BLACKPINK': 3,
	'MOMOLAND': 3,
	
	# 4th Generation
	'fromis_9': 4,
	'Stray Kids': 4,
	'i-dle': 4,
	'ATEEZ': 4,
	'ITZY': 4,
	'TXT': 4,
	'EVERGLOW': 4,
	'TREASURE': 4,
	'P1Harmony': 4,
	'STAYC': 4,
	'aespa': 4,
	'ENHYPEN': 4,
	'NiziU': 4,
	'IVE': 4,
	'Kep1er': 4,
	'NMIXX': 4,
	'LE SSERAFIM': 4,
	
	# 5th Generation
	'tripleS': 5,
	'BOYNEXTDOOR': 5,
	'KISS OF LIFE': 5,
	'RIIZE': 5,
	'BABYMONSTER': 5,
	'TWS': 5,
	'ARTMS': 5,
	'BADVILLAIN': 5,
	'MEOVV': 5,
	'izna': 5,
	'Hearts2Hearts': 5,
	'IFEYE': 5,
	'ILLIT': 5
}


# Military service records: group -> list of (member, enlist_date, discharge_date)
# discharge_date is None if still serving. Non-Korean members are excluded (exempt).
# Sources: jazminemedia.com, koreaboo.com, allkpop.com
MILITARY_SERVICE = {
	'BTS': [
		('Jin',       '2022-12-13', '2024-06-12'),
		('j-hope',    '2023-04-18', '2024-10-16'),
		('Suga',      '2023-09-22', '2025-06-21'),
		('RM',        '2023-12-11', '2025-06-10'),
		('V',         '2023-12-11', '2025-06-10'),
		('Jimin',     '2023-12-12', '2025-06-11'),
		('Jung Kook', '2023-12-12', '2025-06-11'),
	],
	'EXO': [
		# Lay (Chinese) is exempt
		('Xiumin',   '2019-05-07', '2020-12-06'),
		('D.O.',     '2019-07-01', '2021-01-25'),
		('Suho',     '2020-05-14', '2022-02-13'),
		('Chen',     '2020-10-26', '2022-04-25'),
		('Chanyeol', '2021-03-29', '2022-09-28'),
		('Baekhyun', '2021-05-06', '2023-02-05'),
		('Kai',      '2023-05-11', '2025-02-10'),
		('Sehun',    '2023-12-21', '2025-09-20'),
	],
	'GOT7': [
		# Mark (US), Jackson (HK), BamBam (Thai) are exempt
		('Jay B',    '2023-02-02', '2024-11-01'),
		('Jinyoung', '2023-05-08', '2024-11-07'),
		('Yugyeom',  '2025-09-01', None),
		('Youngjae', '2025-11-27', None),
	],
	'Monsta X': [
		('Shownu',   '2021-07-22', '2023-04-21'),
		('Minhyuk',  '2023-04-04', '2024-10-03'),
		('Joohoney', '2023-07-24', '2025-01-23'),
		('Kihyun',   '2023-08-22', '2025-02-21'),
		('Hyungwon', '2023-11-14', '2026-05-13'),
		# I.M has not enlisted
	],
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
	'ATEEZ': 'KQ Entertainment',
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

	# 5th Gen
	'tripleS': 'MODHAUS',
	'BOYNEXTDOOR': 'HYBE',
	'KISS OF LIFE': 'S2 Entertainment',
	'RIIZE': 'SM Entertainment',
	'BABYMONSTER': 'YG Entertainment',
	'TWS': 'HYBE',
	'ARTMS': 'MODHAUS',
	'BADVILLAIN': 'One Hundred',
	'MEOVV': 'THE BLACK LABEL',
	'izna': 'CJ E&M',
	'Hearts2Hearts': 'SM Entertainment',
	'IFEYE': 'Hi-Hat Entertainment',
	'ILLIT': 'HYBE'
}


