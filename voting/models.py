from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import uuid


class CustomUserManager(BaseUserManager):
    """Custom user manager to handle both username and phone-based users"""
    
    def create_user(self, username=None, phone_number=None, password=None, **extra_fields):
        """Create and return a regular user or admin user"""
        user_type = extra_fields.get('user_type', 'user')
        
        if user_type == 'user':
            # Regular user - requires phone number
            if not phone_number:
                raise ValueError('Regular users must have a phone number')
            extra_fields.setdefault('is_staff', False)
            extra_fields.setdefault('is_superuser', False)
            extra_fields.setdefault('is_phone_verified', False)
            
            # For regular users, use phone_number as username
            user = self.model(phone_number=phone_number, username=phone_number, **extra_fields)
        else:
            # Admin user - requires username
            if not username:
                raise ValueError('Admin users must have a username')
            extra_fields.setdefault('is_staff', True)
            extra_fields.setdefault('is_phone_verified', True)
            
            if user_type == 'super_admin':
                extra_fields.setdefault('is_superuser', True)
            
            user = self.model(username=username, phone_number=phone_number, **extra_fields)
        
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, password=None, **extra_fields):
        """Create and return a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'super_admin')
        extra_fields.setdefault('is_phone_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(username=username, password=password, **extra_fields)


class CustomUser(AbstractUser):
    """Custom user model with phone number for regular users and username for admins"""
    ADMIN_CHOICES = [
        ('user', 'Regular User'),
        ('view_admin', 'View Admin'),
        ('super_admin', 'Super Admin'),
    ]
    
    # Override the id field to use UUID
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Phone number field with validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Phone number for regular users"
    )
    
    # OTP verification fields
    is_phone_verified = models.BooleanField(
        default=False,
        help_text="Whether the phone number has been verified via OTP"
    )
    otp_code = models.CharField(
        max_length=6, 
        blank=True, 
        null=True,
        help_text="Current OTP code for verification"
    )
    otp_created_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When the current OTP was generated"
    )
    
    # User type field
    user_type = models.CharField(
        max_length=15, 
        choices=ADMIN_CHOICES, 
        default='user',
        help_text="Type of user: regular user, view admin, or super admin"
    )
    
    # Additional timestamp
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this user account was created"
    )
    
    # Use custom manager
    objects = CustomUserManager()
    
    # Keep username as USERNAME_FIELD for Django compatibility
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        # For regular users, set username to phone_number if not set
        if self.user_type == 'user' and self.phone_number and not self.username:
            self.username = self.phone_number
        
        # Set staff/superuser status based on user_type
        if self.user_type == 'super_admin':
            self.is_staff = True
            self.is_superuser = True
        elif self.user_type == 'view_admin':
            self.is_staff = True
            self.is_superuser = False
        else:
            # Regular users are not staff
            self.is_staff = False
            self.is_superuser = False
        
        # Auto-verify admin users
        if self.user_type in ['view_admin', 'super_admin']:
            self.is_phone_verified = True
            
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate user data"""
        super().clean()
        
        # Regular users must have phone numbers
        if self.user_type == 'user' and not self.phone_number:
            raise ValidationError('Regular users must have a phone number')
        
        # Admin users must have usernames
        if self.user_type in ['view_admin', 'super_admin'] and not self.username:
            raise ValidationError('Admin users must have a username')
    
    def __str__(self):
        if self.user_type == 'user' and self.phone_number:
            return f"{self.phone_number} ({self.get_user_type_display()})"
        else:
            return f"{self.username} ({self.get_user_type_display()})"
    
    def is_admin(self):
        """Check if user is any type of admin"""
        return self.user_type in ['view_admin', 'super_admin']
    
    def is_super_admin(self):
        """Check if user is a super admin"""
        return self.user_type == 'super_admin'
    
    def can_create_polls(self):
        """Check if user can create polls"""
        return self.user_type == 'super_admin'
    
    def can_view_results(self):
        """Check if user can view poll results"""
        return self.user_type in ['view_admin', 'super_admin']
    
    def get_display_name(self):
        """Get display name for the user"""
        if self.user_type == 'user':
            return self.phone_number or self.username
        else:
            return self.username or self.phone_number





class Poll(models.Model):
    """Poll/Voting form model"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_polls')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.status == 'active'
    
    def is_upcoming(self):
        return timezone.now() < self.start_time and self.status == 'scheduled'
    
    def is_expired(self):
        return timezone.now() > self.end_time or self.status == 'closed'
    
    def get_total_votes(self):
        return Vote.objects.filter(poll=self).count()
    
    def update_status(self):
        """Auto update poll status based on time"""
        now = timezone.now()
        if self.status == 'scheduled' and now >= self.start_time:
            self.status = 'active'
        elif self.status == 'active' and now > self.end_time:
            self.status = 'closed'
        self.save()


class Option(models.Model):
    """Poll options/choices"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        unique_together = ['poll', 'option_text']
    
    def __str__(self):
        return f"{self.poll.title} - {self.option_text}"
    
    def get_vote_count(self):
        return self.votes.count()
    
    def get_vote_percentage(self, total_votes):
        if total_votes == 0:
            return 0
        return (self.get_vote_count() / total_votes) * 100


class Vote(models.Model):
    """User votes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='votes')
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name='votes')
    voted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    class Meta:
        unique_together = ['poll', 'user']  # Ensures one vote per user per poll
        ordering = ['-voted_at']
    
    def __str__(self):
        return f"{self.user.phone_number} voted for {self.option.option_text} in {self.poll.title}"


class OTPLog(models.Model):
    """Track OTP requests for rate limiting"""
    phone_number = models.CharField(max_length=17)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.phone_number} - {self.created_at}"