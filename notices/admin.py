from django.contrib import admin
from .models import Notice, NotifyGroup, NoticeResponse, NoticeDocument


class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'created', 'expires_at', 'uploaded_by')


class NotifyGroupAdmin(admin.ModelAdmin):
    list_display = ('group_name',)


class NoticeResponseAdmin(admin.ModelAdmin):
    list_display = ('notice', 'responder', 'created')


admin.site.register(Notice, NoticeAdmin)
admin.site.register(NoticeDocument)
admin.site.register(NotifyGroup, NotifyGroupAdmin)
admin.site.register(NoticeResponse, NoticeResponseAdmin)
