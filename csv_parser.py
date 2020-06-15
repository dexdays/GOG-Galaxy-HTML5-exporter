#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from ast import literal_eval
from html import escape
from html.parser import HTMLParser
import json
from math import floor
from operator import itemgetter
from os import getcwd, makedirs, rename
from os.path import join, exists
import re
from string import Formatter

from csv import DictReader
from natsort import natsorted
from unidecode import unidecode

__maintainer__ = "Bruno “Varstahl” Passeri"

class Arguments():
	""" argparse wrapper, to reduce code verbosity """
	__parser = None
	__args = None

	def __init__(self, args, **kwargs):
		self.__parser = argparse.ArgumentParser(**kwargs)
		for arg in args:
			self.__parser.add_argument(*arg[0], **arg[1])
		self.__args = self.__parser.parse_args()

	def help(self):
		self.__parser.print_help()

	def anyOption(self, exceptions):
		for k,v in self.__args.__dict__.items():
			if (k not in exceptions) and v:
				return True
		return False

	def __getattr__(self, name):
		ret = getattr(self.__args, name)
		if isinstance(ret, list) and (1 == len(ret)) and (int != type(ret[0])):
			ret = ret[0]
		return ret

class AttributesParser(HTMLParser):
    """ Custom HTML parser that stores [tagName, [attributes]] """
    __whitespace = re.compile(r'\s+')

    def feed(self, data):
        self.attrs = []
        super().feed(data)
        return self.attrs

    def handle_starttag(self, tag, attrs):
        self.inLink = False
        self.attrs.append([tag])
        index = len(self.attrs) - 1
        for attr in attrs:
            attr = list(attr)
            if 'class' == attr[0]:
                attr[1] = self.__whitespace.split(attr[1])
            self.attrs[index].append(attr)

class CustomStringFormatter(str):
	""" Custom template formatters, allows non used parameters to be left alone
	    instead of raising a Key/Index exception
	"""
	class CustomFormatter(Formatter):
		_usedArgs = set()

		def __init__(self, default='{{{0}}}'):
			self.default=default

		def get_value(self, key, args, kwargs):
			try:
				ret = super().get_value(key, args, kwargs)
				self._usedArgs.add(key)
				return ret
			except (IndexError, KeyError):
				return self.default.format(key)

	_formatter = CustomFormatter()

	def used_keys(self):
		""" All the keys used while formatting """
		return self._formatter._usedArgs

	def format(self, *args, **kwargs):
		self._formatter._usedArgs = set()
		return self._formatter.format(self, *args, **kwargs)

def roman_numeral(s):
	""" Returns a roman numeral converted to an integer if valid, or the source string """
	def roman_to_int(s):
		d = {'m': 1000, 'd': 500, 'c': 100, 'l': 50, 'x': 10, 'v': 5, 'i': 1}
		n = [d[i] for i in s if i in d]
		return str(sum([i if i>=n[min(j+1, len(n)-1)] else -i for j,i in enumerate(n)]))

	if not re.match(r'^(?=[mdclxvi])m*(c[md]|d?c{0,3})(x[cl]|l?x{0,3})(i[xv]|v?i{0,3})$', s):
		return s

	return roman_to_int(s)

def repeatable_fields(mo):
	""" Repeats '{rep}…{/rep}' template partial to format a list
		of name:values generated from the static variable `params`.
		Uses `0` and `1` from the matching group for the whitespace and
		repeatable content.
	"""
	rf = ''
	for k,v in repeatable_fields.params.items():
		if v:
			rf += mo.group(1) + mo.group(2).format(k, v)
	return rf

def duration(t):
	""" Converts minutes into a "Xd Yh Zm" format """
	try:
		t = int(t)
	except:
		t = 0
	m = floor(t % 60)
	h = floor((t / 60) % 24)
	d = floor(t / 1440)
	t = ''
	if m: t = str(m) + 'm'
	if h: t = str(h) + 'h ' + t
	if d: t = str(d) + 'd ' + t
	return t.strip()

def clean(s, bPurge=True):
	s = s.strip()
	for rx in clean.rx:
		s = rx[0].sub(rx[1], s)
	return escape(s) if bPurge else s
clean.rx = [
	(re.compile(r'\.\.\.'), '…'),
	(re.compile(r'\s+-\s+'), ' – '),
	(re.compile(r'\u0092'), '’'),  # PU2
	(re.compile(r'\u0093'), '“'),  # STS
	(re.compile(r'\u0094'), '”'),  # CCH
	(re.compile(r'\s*\u0097\s*'), ' – '),  # CCH
]

def description(s):
	# Fix a bit of mess and split by line break
	s = clean(s, False)
	if (2 == description.quotes.subn('', s)[1]) and ('"' == s[0]) and ('"' == s[-1]):
		s = s[1:-1].strip()
	s = s.replace('\\n', '\n')
	s = description.paragraphs['replaceClosed'].sub('\n', s)
	s = description.paragraphs['replaceOpen'].sub('\n', s)
	s = description.paragraphs['clear'].sub(r'\n\1', s)
	s = s.strip().split('\n')

	# Analyse the strings by row
	for i in range(0, len(s)):
		s[i] = s[i].strip()  # Trim whitespace

		# Calculate the number of blank lines before the element and create a CSS class accordingly
		breaks = 0
		while True:
			if (0 > (i-1-breaks)) or len(s[i-1-breaks]):
				break
			breaks += 1
		breaks = 'spaced-{}'.format(max(0, min(1, breaks))) if (0 < breaks) and (0 < i) else ''

		# Ignore empty paragraphs
		if s[i]:
			if description.list.match(s[i]):
				# Convert into a list instead of a string to prepare for the possibility
				# of implementing sub-lists
				s[i] = ['<li{}>'.format(' class="{}"'.format(breaks) if breaks else ''), description.list.sub('', s[i]), '</li>']
			else:
				# Transform the paragraph(?) tag
				startTag = description.paragraphs['exists'].match(s[i])
				if startTag:
					startTag = description.parser.feed(startTag.group(1))
					s[i] = description.paragraphs['exists'].sub('', s[i])
				else:
					startTag = [['p', ['class', []]]]

				# Inject spacer class
				if breaks:
					try:
						index = next(startTag[0].index(x) for x in startTag[0] if x[0] == 'class')
						startTag[0][index][1].append(breaks)
					except StopIteration:
						startTag[0].append(['class', [breaks]])

				# Reassemble the startTag
				tag = startTag[0].pop(0)
				for attr in startTag[0]:
					if attr and attr[1]:
						if list == type(attr[1]):
							attr[1] = ' '.join(set(attr[1]))
						tag += ' {0}={2}{1}{2}'.format(*attr, "'" if '"' in attr[1] else '"')
				s[i] = '<' + tag + '>' + s[i] + '</p>'

	# Rebuild the description
	ret = ''
	bInsideList = False
	for i in range(0, len(s)):
		if s[i]:
			# Paragraphs
			if str == type(s[i]):
				if bInsideList:
					ret += '</ul>'
					bInsideList = False
				ret += s[i]
			else:
				if not bInsideList:
					ret += '<ul>'
					bInsideList = True
				ret += ''.join(s[i])
	if bInsideList:
		ret += '</ul>'
	return ret
description.parser = AttributesParser()
description.quotes = re.compile('"')
description.list = re.compile(r'^[*-]\s*')
description.paragraphs = {
	'open': re.compile(r'<p[^>]*>'),
	'replaceClosed': re.compile(r'\s*</p>\s*'),
	'replaceOpen': re.compile(r'\s*<p>\s*'),
	'clear': re.compile(r'\s*(<p[^>]*>)\s*'),
	'exists': re.compile(r'^\s*(<p[^>]*>)\s*'),
}

def delist(s, bConvertToString=True):
	""" Explodes a list into a nicely spaced list """
	if not s:
		return s
	s = literal_eval(s)
	return s if not bConvertToString else ', '.join(s)

def pathFromURL(imageURL):
	""" Transforms an image URL into a list of relative image paths """
	image = list(pathFromURL.namefinder.search(imageURL).groups())

	# Transform query parameters into wget-like paths
	if not image[1]:
		image.pop(1)
	else:
		image[1] = '{}@{}'.format(image[0], image[1])

	# Relative path transformation
	for i in range(0, len(image)):
		image[i] = 'images/' + image[i]

	return image
pathFromURL.namefinder = re.compile(r'/([^/]+?)(?:\?([^/]+))?$')  # Compiled for better efficiency

def Main(args):
	games = []
	articles = '(' + '|'.join([
		r'an?\s+', r'the\s+',  # English
		r'il?\s+', r'l[oiae]\s+', r'gli\s+', r'un[oa]?\s+', r'(?:l|un)\''  # Italian
	]) + ')'
	titleReplaceList = [
		(r'\.\.\.', '…'),
	]  # Cleans the title
	transliteratedTitleReplaceList = [
		(r', ' + articles + r'$', ''),
		(r'\(tm\)', ''),
		(r'\(r\)', ''),
	]  # Cleans the transliterated title, and removes useless things
	searchReplaceList = [
		[
			(r'[,.…]', ''),
		], [
			(r'[;:\'-]', ''),
			(r'[|\\/()]', ' '),
			(r'\s{2,}', ' '),
		], [
			(r'([0-9])0{12}(\s|$)', r'\1t\2'),
			(r'([0-9])0{9}(\s|$)', r'\1g\2'),
			(r'([0-9])0{6}(\s|$)', r'\1m\2'),
			(r'([0-9])0{3}(\s|$)', r'\1k\2'),
		]
	]  # Each list group creates a new permutation of the search string

	# Build the game data list
	with open(args.fileCSV, 'r', encoding='utf-8', newline='') as csvfile:
		for row in DictReader(csvfile, delimiter=args.delimiter):
			try:
				# Set the default image
				for t in ['verticalCover', 'backgroundImage', 'squareIcon']:
					if row[t]:
						row['_defaultImage'] = row[t]
						break
			except KeyError:
				print('Unable to find images: forgot to select a delimiter or to export them?')
				return

			if '_defaultImage' not in row:
				continue
			row['_defaultImagePaths'] = pathFromURL(row['_defaultImage'])

			# Fix common problems with titles
			for i in titleReplaceList:
				row['title'] = re.sub(i[0], i[1], row['title'])

			# Transliterate and transform the title in a sortable/searchable ascii format
			row['_titleTL'] = re.sub(r'^' + articles + r'(.+?)$', r'\2, \1', unidecode(row['title']).lower()).strip()
			for i in transliteratedTitleReplaceList:
				row['_titleTL'] = re.sub(i[0], i[1], row['_titleTL'])

			# Facilitate searches
			row['_searchable'] = list(set([row['title'].lower(), row['_titleTL']]))
			searchItem = row['_titleTL']
			for srl in searchReplaceList:
				for i in srl:
					searchItem = re.sub(i[0], i[1], searchItem).strip()
				if searchItem not in row['_searchable']:
					row['_searchable'].append(searchItem)

			# Try a roman numerals to digits conversion
			searchItem = ' '.join([roman_numeral(x) for x in searchItem.split(' ')])
			if searchItem not in row['_searchable']:
				row['_searchable'].append(searchItem)

			games.append(row)

	games = natsorted(games, key=itemgetter('_titleTL'))

	# Export list of images
	if args.imageList:
		try:
			makedirs(join(getcwd(), 'images'))
		except: pass

		# Find the best match for the image
		images = []
		for game in games:
			bFound = False
			for image in game['_defaultImagePaths']:
				if exists(image):
					bFound = True
					break
			if not bFound:
				images.append(game['_defaultImage'])

		if not images:
			print('No new images to download')
		else:
			try:
				with open(args.fileImageList, "w", encoding='utf-8') as ll:
					ll.write('\n'.join(images))
				print('Image list exported, it\'s suggested to download with `wget -nc -P images -i "{}"`'.format(args.fileImageList))
			except FileNotFoundError:
				print('Unable to write to “{}”, make sure that the path exists and that you have the write permissions'.format(args.fileImageList))

	# Export HTML5
	if args.htmlExport:
		# Load the templates
		templates = {}
		for k,l in {
			'index': ['index', '.html'],
			'game': ['game', '.html'],
			'script': ['script', '.js'],
			'style': ['style', '.css'],
		}.items():
			fn = 'templates/{0}{2}{1}'.format(l[0], l[1], '.custom' if exists('templates/{0}.custom{1}'.format(l[0], l[1])) else '')
			if args.embed or (k not in ['script', 'style']):
				with open(fn, 'r', encoding='utf-8') as f:
					templates[k] = CustomStringFormatter(f.read(-1))
			else:
				templates[k] = fn
				continue

		# Single game HTML
		gameID = len(games)  # start the ids from N (games count), to allow re-ordering in the range [0:N-1]
		gameID = (gameID + 1000 - (gameID % 1000))  # Round it up to the thousands
		games_html = ''
		games_css = ''
		for game in games:
			gameID += 1
			if args.debugEntryID and (gameID not in args.debugEntryID):
				continue

			# Image renamer
			for p in range(1, len(game['_defaultImagePaths'])):
				if exists(game['_defaultImagePaths'][p]):
					rename(game['_defaultImagePaths'][p], game['_defaultImagePaths'][0])

			params = {
				'id': gameID,
				'title': clean(game['title']),
				'description': description(game['summary']),
				'search': json.dumps(game['_searchable']).replace("'", "&apos;"),
				'developers': clean(delist(game['developers'])),
				'platforms': clean(delist(game['platformList'])),
				'score': game['criticsScore'],
				'publishers': clean(delist(game['publishers'])),
				'released': game['releaseDate'],
				'genres': delist(game['genres']),
				'themes': delist(game['themes']),
				'playtime': duration(game['gameMins'])
			}

			game_html = templates['game'].format('a', **params)
			games_css += '#game-{0}{{order:{0};background-image:url("{1}");}}'.format(gameID, game['_defaultImagePaths'][0])

			# Remove parameters already printed
			repeatable_fields.params = {x:params[x] for x in params if x not in templates['game'].used_keys() and isinstance(x, str)}
			games_html += re.sub(r'(\s*){rep}(.*?){/rep}', repeatable_fields, game_html)

		try:
			with open(args.fileHTML, 'w', encoding='utf-8') as f:
				css = ('<style>' + templates['style'] + '</style>') if args.embed else ('<link rel="stylesheet" type="text/css" href="' + templates['style'] + '">')
				js = ('<script>' + templates['script'] + '</script>') if args.embed else ('<script src="' + templates['script'] + '"></script>')
				f.write(templates['index'].format(**{
					'language': 'en',
					'title': args.title,
					'imageCSS': '' if args.debugEntryID else games_css,
					'style': css,
					'javascript': js,
					'content': games_html
				}))
			print('HTML5 list exported')
		except FileNotFoundError:
			print('Unable to write to “{}”, make sure that the path exists and that you have the write permissions'.format(args.fileHTML))
			return

if "__main__" == __name__:
	def ba(variableName, description, defaultValue=False):
		""" Boolean argument: creates a default boolean argument with the name of the storage variable and
			the description to be shown in the help screen
		"""
		return {
			'action': 'store_true',
			'required': defaultValue,
			'help': description,
			'dest': variableName,
		}

	args = Arguments(
		[
			[
				['-d'],
				{
					'default': ',',
					'type': str,
					'required': False,
					'metavar': 'CHARACTER',
					'help': 'CSV field separator, defaults to comma',
					'dest': 'delimiter',
				}
			],
			[
				['-i', '--input'],
				{
					'default': 'gameDB.csv',
					'type': str,
					'nargs': 1,
					'required': False,
					'metavar': 'FN',
					'help': 'CSV file path',
					'dest': 'fileCSV',
				}
			],
			[
				['-l', '--list'],
				{
					'default': 'imagelist.txt',
					'type': str,
					'nargs': 1,
					'required': False,
					'metavar': 'FN',
					'help': 'pathname of the generated list of cover URLs',
					'dest': 'fileImageList',
				}
			],
			[
				['-o', '--output'],
				{
					'default': 'index.html',
					'type': str,
					'nargs': 1,
					'required': False,
					'metavar': 'FN',
					'help': 'pathname of the generated HTML5 games list',
					'dest': 'fileHTML',
				}
			],
			[['--image-list'], ba('imageList', 'create an image list')],
			[['--html5'], ba('htmlExport', 'export the game list in html5 format')],
			[
				['--title'],
				{
					'default': 'GOG Galaxy 2 game library',
					'type': str,
					'nargs': 1,
					'required': False,
					'metavar': 'TITLE',
					'help': 'title of the HTML5 file',
					'dest': 'title',
				}
			],
			[['--embed'], ba('embed', 'embeds CSS & JS instead of linking the resources')],
			[
				['--debug'],
				{
					'default': False,
					'type': int,
					'nargs': '+',
					'required': False,
					'help': argparse.SUPPRESS,
					'dest': 'debugEntryID',
				}
			],
		],
		description='GOG Galaxy 2 export converter: parses the “GOG Galaxy 2 exporter” CSV to generate a list of cover images and/or a searchable HTML5 list of games.'
	)

	if args.anyOption(['delimiter', 'fileCSV', 'fileImageList', 'fileHTML', 'title', 'debugEntryID']):
		if exists(args.fileCSV):
			Main(args)
		else:
			print('Unable to find “{}”, make sure to specify the proper path with “-i” (see --help)'.format(args.fileCSV))
	else:
		args.help()
