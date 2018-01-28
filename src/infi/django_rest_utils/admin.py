from django.contrib import admin

from models import APIToken




class APITokenAdmin(admin.ModelAdmin):

    list_display = ('user', 'token')
    list_filter = ('user', )
    search_fields = ('user__username', 'token')



admin.site.register(APIToken, APITokenAdmin)