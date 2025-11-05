from django.contrib import admin
from .models import Conversation

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('user_message', 'bot_response', 'timestamp')
    list_filter = ('timestamp', 'language')
    search_fields = ('user_message', 'bot_response')

# This removes all the complex (and now deleted) models
# from the admin panel.