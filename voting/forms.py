# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime
from .models import CustomUser, Poll, Option


class UserRegistrationForm(forms.Form):
    """User registration form with phone number"""
    phone_number = forms.CharField(
        max_length=17,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890',
            'pattern': r'^\+?[1-9]\d{1,14}$',
            'title': 'Enter a valid phone number'
        })
    )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        
        # Remove spaces and validate format
        phone_number = phone_number.replace(' ', '').replace('-', '')
        
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise ValidationError('This phone number is already registered.')
        
        return phone_number


class OTPVerificationForm(forms.Form):
    """OTP verification form"""
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123456',
            'pattern': r'\d{6}',
            'title': 'Enter 6-digit OTP code',
            'autocomplete': 'one-time-code'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create password'
        }),
        min_length=6,
        help_text='Password must be at least 6 characters long.'
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError('Passwords do not match.')
        
        return cleaned_data
    
    def clean_otp_code(self):
        otp_code = self.cleaned_data['otp_code']
        
        if not otp_code.isdigit():
            raise ValidationError('OTP must contain only numbers.')
        
        return otp_code


class UserLoginForm(forms.Form):
    """User login form"""
    phone_number = forms.CharField(
        max_length=17,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class PollCreationForm(forms.ModelForm):
    """Form for creating polls"""
    
    class Meta:
        model = Poll
        fields = ['title', 'description', 'start_time', 'end_time']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter poll title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Optional poll description',
                'rows': 3
            }),
            'start_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
    
    # Dynamic fields for options
    option_1 = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option 1'
        })
    )
    
    option_2 = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option 2'
        })
    )
    
    option_3 = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option 3 (optional)'
        })
    )
    
    option_4 = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option 4 (optional)'
        })
    )
    
    option_5 = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option 5 (optional)'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            # Ensure end time is after start time
            if end_time <= start_time:
                raise ValidationError('End time must be after start time.')
            
            # Ensure start time is not in the past (allow 5 minutes buffer)
            now = timezone.now()
            if start_time < now:
                raise ValidationError('Start time cannot be in the past.')
        
        # Validate that we have at least 2 non-empty options
        options = []
        for i in range(1, 6):
            option = cleaned_data.get(f'option_{i}')
            if option and option.strip():
                options.append(option.strip())
        
        if len(options) < 2:
            raise ValidationError('Please provide at least 2 options.')
        
        # Check for duplicate options
        if len(options) != len(set(options)):
            raise ValidationError('Options must be unique.')
        
        cleaned_data['options'] = options
        return cleaned_data


class VoteForm(forms.Form):
    """Form for voting"""
    option_id = forms.UUIDField(
        widget=forms.RadioSelect,
        required=True
    )
    
    def __init__(self, poll, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Generate choices from poll options
        choices = [(option.id, option.option_text) for option in poll.options.all()]
        
        self.fields['option_id'] = forms.ChoiceField(
            choices=choices,
            widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
            required=True,
            label="Choose your option"
        )


class AdminUserCreationForm(forms.ModelForm):
    """Form for creating admin users"""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = CustomUser
        fields = ('phone_number', 'user_type')
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'user_type': forms.Select(attrs={'class': 'form-control'})
        }
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2