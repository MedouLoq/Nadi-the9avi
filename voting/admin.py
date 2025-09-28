# voting/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Poll, Option, Vote


class CustomUserAdmin(UserAdmin):
    """Custom admin for CustomUser model"""
    
    list_display = ['username', 'phone_number', 'user_type', 'is_phone_verified', 'created_at']
    list_filter = ['user_type', 'is_phone_verified', 'is_staff', 'created_at']
    search_fields = ['username', 'phone_number']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {
            'fields': ('phone_number', 'user_type', 'is_phone_verified')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'phone_number', 'user_type', 'password1', 'password2', 'is_phone_verified'),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override save to handle user type properly"""
        if not change:  # Creating new user
            if obj.user_type in ['view_admin', 'super_admin']:
                obj.is_staff = True
                obj.is_phone_verified = True
            if obj.user_type == 'super_admin':
                obj.is_superuser = True
        super().save_model(request, obj, form, change)


# Register models
admin.site.register(CustomUser, CustomUserAdmin)

# Optional: Register other models for admin viewing
@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'start_time', 'end_time', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description']
    date_hierarchy = 'created_at'

@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ['option_text', 'poll', 'order', 'created_at']
    list_filter = ['poll', 'created_at']
    search_fields = ['option_text', 'poll__title']

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'poll', 'option', 'voted_at']
    list_filter = ['poll', 'voted_at']
    search_fields = ['user__phone_number', 'user__username', 'poll__title']
    date_hierarchy = 'voted_at'