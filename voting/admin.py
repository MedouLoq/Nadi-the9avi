# voting/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import path
from django import forms
from .models import CustomUser, Poll, Option, Vote, Team, OTPLog

class SetPasswordForm(forms.Form):
    """Simple form to set user password"""
    password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=6,
        label="كلمة المرور الجديدة"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        min_length=6,
        label="تأكيد كلمة المرور"
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('كلمات المرور غير متطابقة')

        return cleaned_data

class CustomUserAdmin(UserAdmin):
    """Custom admin for CustomUser model"""
    list_display = ['username', 'full_name', 'phone_number', 'user_type', 'is_phone_verified', 'created_at']
    list_filter = ['user_type', 'is_phone_verified', 'is_staff', 'created_at']
    search_fields = ['username', 'phone_number', 'full_name']

    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {
            'fields': ('full_name', 'phone_number', 'user_type', 'is_phone_verified')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'full_name', 'phone_number', 'user_type', 'password1', 'password2', 'is_phone_verified'),
        }),
    )

    # Add custom action to set password
    actions = ['set_user_password']

    def set_user_password(self, request, queryset):
        """Custom action to set password for selected users"""
        if queryset.count() != 1:
            self.message_user(request, 'يرجى اختيار مستخدم واحد فقط', messages.ERROR)
            return

        user = queryset.first()

        if request.method == 'POST':
            form = SetPasswordForm(request.POST)
            if form.is_valid():
                new_password = form.cleaned_data['password']
                user.set_password(new_password)
                user.save()

                self.message_user(
                    request,
                    f'تم تعيين كلمة المرور بنجاح للمستخدم: {user.full_name or user.username}',
                    messages.SUCCESS
                )
                return redirect('admin:voting_customuser_changelist')
        else:
            form = SetPasswordForm()

        context = {
            'form': form,
            'user': user,
            'opts': self.model._meta,
            'title': f'تعيين كلمة مرور جديدة - {user.full_name or user.username}'
        }

        return render(request, 'admin/set_password.html', context)

    set_user_password.short_description = "تعيين كلمة مرور للمستخدم المحدد"

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

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    pass

# In admin.py

class OTPLogAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'otp_code', 'created_at', 'is_used', 'attempts']
    list_filter = ['is_used', 'created_at']
    search_fields = ['phone_number', 'otp_code']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

admin.site.register(OTPLog, OTPLogAdmin)
