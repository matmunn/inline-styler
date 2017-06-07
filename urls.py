from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
	(r'^$', include('styler.urls')),
	(r'^styler/', include('styler.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
		(r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.STATICROOT}),
	)
