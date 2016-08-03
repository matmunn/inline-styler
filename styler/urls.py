from django.conf.urls.defaults import *

urlpatterns = patterns('inline-styler.styler.views',
	(r'^$', 'index'),
	(r'^convert/$', 'convert'),
	(r'^api/$', 'api'),
)
