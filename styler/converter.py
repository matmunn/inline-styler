import os
import sys
import urllib
import codecs
import urlparse
import csv
import cssutils

from lxml import etree
from cssutils.script import csscombine
from cssutils.script import CSSCapture
from cssselect import CSSSelector, ExpressionError

# Added requirement for BeautifulSoup
from bs4 import BeautifulSoup

from django.conf import settings

class Conversion:
	def __init__(self):
		self.CSSErrors=[]
		self.CSSUnsupportErrors=dict()
		self.supportPercentage=100
		self.convertedHTML=""

	def perform(self,document,sourceHTML,sourceURL,srcPrefix):
		aggregateCSS="";
		if len(srcPrefix) and not srcPrefix.endswith('/'):
			srcPrefix = srcPrefix + '/'

		# retrieve CSS rel links from html pasted and aggregate into one string
		CSSRelSelector = CSSSelector("link[rel=stylesheet],link[rel=StyleSheet],link[rel=STYLESHEET]")
		matching = CSSRelSelector.evaluate(document)
		for element in matching:
			try:
				csspath=element.get("href")
				if len(sourceURL):
					if element.get("href").lower().find("http://",0) < 0:
						parsedUrl=urlparse.urlparse(sourceURL);
						csspath=urlparse.urljoin(parsedUrl.scheme+"://"+parsedUrl.hostname, csspath)
				f=urllib.urlopen(csspath)
				aggregateCSS+=''.join(f.read())
				element.getparent().remove(element)
			except:
				raise IOError('The stylesheet '+element.get("href")+' could not be found')

		#include inline style elements
		print aggregateCSS
		CSSStyleSelector = CSSSelector("style,Style")
		matching = CSSStyleSelector.evaluate(document)
		for element in matching:
			aggregateCSS+=element.text
			element.getparent().remove(element)

		#convert  document to a style dictionary compatible with etree
		styledict = self.getView(document, aggregateCSS)

		#set inline style attribute if not one of the elements not worth styling
		ignoreList=['html','head','title','meta','link','script','repeater','singleline','multiline','br','layout']
		for element, style in styledict.items():
			if element.tag not in ignoreList:
				v = style.getCssText(separator=u'')
				element.set('style', v)

		#convert tree back to plain text html
		self.convertedHTML = etree.tostring(document, method="xml", pretty_print=True,encoding='UTF-8')
		self.convertedHTML= self.convertedHTML.replace('&#13;', '') #tedious raw conversion of line breaks.

		# We've inline styled the CSS, now do the HTML src tags
		soup = BeautifulSoup(self.convertedHTML)
		for img in soup.find_all("img"):
			img['src'] = srcPrefix + img.get('src')

		# Now we would like to set width and min-width on all our tables
		for table in soup.find_all("table"):
			if table.get('width') is not None:
				width = table.get('width')
				if not width.endswith('%'):
					if table.get('style') is None:
						style = []
					else:
						style = table.get('style').split(';')
					style = [x for x in style if x]
					style.append("min-width:" + width + "px")
					style.append("width:" + width + "px")
					table['style'] = ';'.join(style)

		# Might as well go ahead and throw a style tag in the head for iOS fixes
		if soup.html.head is None:
			soup.html.insert(0, soup.new_tag('head'))
		if soup.html.head.style is None:
			soup.html.head.append(soup.new_tag('style', type="text/css"))
		soup.html.head.style.append("""a[href^="x-apple-data-detectors:"] {
    color: #000000;
    text-decoration: none;
}
a[href^="tel"], a[href^="sms"] {
    color: #000000;
    text-decoration: none;
}""")

		for img in soup.find_all('img'):
			if 'spacer.gif' in img.get('src'):
				classes = img.get('class')
				if classes is not None:
					if 'w' in classes:
						img.parent['width'] = img.get('width')
					if 'h' in classes:
						img.parent['height'] = img.get('height')

		self.convertedHTML = str(soup)

		return self

	def styleattribute(self,element):
		"""
		returns css.CSSStyleDeclaration of inline styles, for html: @style
		"""
		cssText = element.get('style')
		if cssText:
			return cssutils.css.CSSStyleDeclaration(cssText=cssText)
		else:
			return None

	def getView(self, document, css):

		view = {}
		specificities = {}
		supportratios={}
		supportFailRate=0
		supportTotalRate=0;
		compliance=dict()

		#load CSV containing css property client support into dict
		mycsv = csv.DictReader(open(os.path.join(settings.FILEROOT, "css_compliance.csv")), delimiter=',')
		for row in mycsv:
			#count clients so we can calculate an overall support percentage later
			clientCount=len(row)
			compliance[row['property'].strip()]=dict(row);

		#decrement client count to account for first col which is property name
		clientCount-=1

		#sheet = csscombine(path="http://www.torchbox.com/css/front/import.css")
		sheet = cssutils.parseString(css)

		rules = (rule for rule in sheet if rule.type == rule.STYLE_RULE)
		for rule in rules:

			for selector in rule.selectorList:
				try:
					cssselector = CSSSelector(selector.selectorText)
					matching = cssselector.evaluate(document)

					for element in matching:
						# add styles for all matching DOM elements
						if element not in view:
							# add initial
							view[element] = cssutils.css.CSSStyleDeclaration()
							specificities[element] = {}

							# add inline style if present
							inlinestyletext= element.get('style')
							if inlinestyletext:
								inlinestyle= cssutils.css.CSSStyleDeclaration(cssText=inlinestyletext)
							else:
								inlinestyle = None
							if inlinestyle:
								for p in inlinestyle:
									# set inline style specificity
									view[element].setProperty(p)
									specificities[element][p.name] = (1,0,0,0)

						for p in rule.style:
							#create supportratio dic item for this property
							if p.name not in supportratios:
								supportratios[p.name]={'usage':0,'failedClients':0}
							#increment usage
							supportratios[p.name]['usage']+=1

							try:
								if not p.name in self.CSSUnsupportErrors:
									for client, support in compliance[p.name].items():
										if support == "N" or support=="P":
											#increment client failure count for this property
											supportratios[p.name]['failedClients']+=1
											if not p.name in self.CSSUnsupportErrors:
												if support == "P":
													self.CSSUnsupportErrors[p.name]=[client + ' (partial support)']
												else:
													self.CSSUnsupportErrors[p.name]=[client]
											else:
												if support == "P":
													self.CSSUnsupportErrors[p.name].append(client + ' (partial support)')
												else:
													self.CSSUnsupportErrors[p.name].append(client)

							except KeyError:
								pass

							# update styles
							if p not in view[element]:
								view[element].setProperty(p.name, p.value, p.priority)
								specificities[element][p.name] = selector.specificity
							else:
								sameprio = (p.priority == view[element].getPropertyPriority(p.name))
								if not sameprio and bool(p.priority) or (sameprio and selector.specificity >= specificities[element][p.name]):
									# later, more specific or higher prio
									view[element].setProperty(p.name, p.value, p.priority)

				except ExpressionError:
					if str(sys.exc_info()[1]) not in self.CSSErrors:
						self.CSSErrors.append(str(sys.exc_info()[1]))
					pass

		for props, propvals in supportratios.items():
			supportFailRate+=(propvals['usage']) * int(propvals['failedClients'])
			supportTotalRate+=int(propvals['usage']) * clientCount

		if(supportFailRate and supportTotalRate):
			self.supportPercentage= 100- ((float(supportFailRate)/float(supportTotalRate)) * 100)
		return view

class MyURLopener(urllib.FancyURLopener):
	http_error_default = urllib.URLopener.http_error_default
