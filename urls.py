from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
	(r'^$', include('inline-styler.styler.urls')),
	(r'^styler/', include('inline-styler.styler.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
		(r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.STATICROOT}),
	)
