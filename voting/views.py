# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import View
import random
import json
from datetime import timedelta

from .models import CustomUser, Poll, Option, Vote, OTPLog
from .utils import send_sms_otp  # You'll need to implement this with your SMS API


# ==================== Authentication Views ====================

def register_view(request):
    """User registration with phone number"""
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        
        if not phone_number:
            messages.error(request, 'رقم الهاتف مطلوب')
            return render(request, 'registration/register.html')
        
        # Format phone number for Mauritania (normalize to 8 digits)
        from .utils import format_mauritanian_phone
        formatted_phone = format_mauritanian_phone(phone_number)
        
        if not formatted_phone:
            messages.error(request, 'يرجى إدخال رقم هاتف موريتاني صحيح (8 أرقام تبدأ بـ 2 أو 3 أو 4)')
            return render(request, 'registration/register.html')
        
        # Store the formatted number with +222 prefix for consistency
        full_phone_number = f"+222{formatted_phone}"
        
        # Check if user already exists
        if CustomUser.objects.filter(phone_number=full_phone_number).exists():
            messages.error(request, 'رقم الهاتف مسجل بالفعل')
            return render(request, 'registration/register.html')
        
        # Create user (not verified yet)
        try:
            user = CustomUser.objects.create_user(
                phone_number=full_phone_number,
                username=full_phone_number,
                user_type='user',
                is_phone_verified=False,
                otp_created_at=timezone.now()
            )
        except Exception as e:
            messages.error(request, 'خطأ في إنشاء الحساب')
            return render(request, 'registration/register.html')
        
        # Send OTP via SMS using Chinguisoft API
        success, otp_or_error = send_sms_otp(full_phone_number)
        
        if success:
            # Store the OTP code returned by Chinguisoft
            user.otp_code = otp_or_error
            user.save()
            
            # Log OTP request
            OTPLog.objects.create(phone_number=full_phone_number, otp_code=otp_or_error)
            
            request.session['registration_phone'] = full_phone_number
            messages.success(request, f'تم إرسال رمز التحقق إلى {formatted_phone}')
            return redirect('verify_otp')
        else:
            user.delete()  # Clean up if SMS fails
            messages.error(request, f'فشل في إرسال رمز التحقق: {otp_or_error}')
            return render(request, 'registration/register.html')
    
    return render(request, 'registration/register.html')


def verify_otp_view(request):
    """Verify OTP and complete registration"""
    phone_number = request.session.get('registration_phone')
    
    if not phone_number:
        messages.error(request, 'انتهت الجلسة. يرجى التسجيل مرة أخرى.')
        return redirect('register')
    
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not all([otp_code, password, confirm_password]):
            messages.error(request, 'جميع الحقول مطلوبة')
            return render(request, 'registration/verify_otp.html', {'phone_number': phone_number})
        
        if password != confirm_password:
            messages.error(request, 'كلمات المرور غير متطابقة')
            return render(request, 'registration/verify_otp.html', {'phone_number': phone_number})
        
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            
            # Check OTP validity (5 minutes expiry)
            if user.otp_created_at and timezone.now() - user.otp_created_at > timedelta(minutes=5):
                messages.error(request, 'انتهت صلاحية رمز التحقق. يرجى طلب رمز جديد.')
                return render(request, 'registration/verify_otp.html', {'phone_number': phone_number})
            
            if user.otp_code == otp_code:
                user.is_phone_verified = True
                user.set_password(password)
                user.otp_code = None
                user.otp_created_at = None
                user.save()
                
                # Mark OTP as used
                OTPLog.objects.filter(phone_number=phone_number, otp_code=otp_code).update(is_used=True)
                
                login(request, user)
                del request.session['registration_phone']
                messages.success(request, 'تم التسجيل بنجاح!')
                return redirect('dashboard')
            else:
                messages.error(request, 'رمز التحقق غير صحيح')
        
        except CustomUser.DoesNotExist:
            messages.error(request, 'المستخدم غير موجود')
            return redirect('register')
    
    return render(request, 'registration/verify_otp.html', {'phone_number': phone_number})


def login_view(request):
    """User login with phone number/username and password"""
    if request.method == 'POST':
        login_identifier = request.POST.get('login_identifier')
        password = request.POST.get('password')
        
        if not all([login_identifier, password]):
            messages.error(request, 'جميع الحقول مطلوبة')
            return render(request, 'registration/login.html')
        
        user = None
        
        # Try to determine if it's a phone number or username
        if login_identifier.isdigit() and len(login_identifier) == 8:
            # It's a phone number - format it for regular users
            from .utils import format_mauritanian_phone
            formatted_phone = format_mauritanian_phone(login_identifier)
            print(formatted_phone)
            if formatted_phone:
                full_phone_number = f"+222{formatted_phone}"
                print(full_phone_number)
                try:
                    user_obj = CustomUser.objects.get(phone_number=full_phone_number, user_type='user')
                    if not user_obj.is_phone_verified:
                        messages.error(request, 'رقم الهاتف غير مؤكد')
                        return render(request, 'registration/login.html')
                    
                    user = authenticate(request, username=full_phone_number, password=password)
                except CustomUser.DoesNotExist:
                    pass
            else:
                messages.error(request, 'رقم هاتف غير صحيح')
                return render(request, 'registration/login.html')
        else:
            # It's a username - for admin users
            try:
                user_obj = CustomUser.objects.get(username=login_identifier)
                if user_obj.is_admin():
                    user = authenticate(request, username=login_identifier, password=password)
                else:
                    messages.error(request, 'استخدم رقم الهاتف لتسجيل الدخول كمستخدم عادي')
                    return render(request, 'registration/login.html')
            except CustomUser.DoesNotExist:
                pass
        
        if user:
            login(request, user)
            
            # Redirect based on user type
            if user.user_type == 'super_admin':
                return redirect('admin_dashboard')
            elif user.user_type == 'view_admin':
                return redirect('poll_management')  # View admins go to poll management
            else:
                return redirect('dashboard')  # Normal users go to user dashboard
        else:
            messages.error(request, 'بيانات الدخول غير صحيحة')
    
    return render(request, 'registration/login.html')

def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'تم تسجيل الخروج بنجاح')
    return redirect('login')


# ==================== User Dashboard Views ====================

# Update dashboard_view to handle all user types properly
@login_required
def dashboard_view(request):
    """User dashboard - redirect admins to their appropriate pages"""
    # Super admins go to admin dashboard
    if request.user.user_type == 'super_admin':
        return redirect('admin_dashboard')
    
    # View admins should go to poll management, not user dashboard
    if request.user.user_type == 'view_admin':
        return redirect('poll_management')
    
    # Only regular users see the user dashboard
    # Get active polls
    now = timezone.now()
    active_polls = Poll.objects.filter(
        start_time__lte=now,
        end_time__gte=now,
        status='active'
    ).order_by('-created_at')
    
    # Get upcoming polls
    upcoming_polls = Poll.objects.filter(
        start_time__gt=now,
        status='scheduled'
    ).order_by('start_time')
    
    # Get user's voted polls
    voted_poll_ids = Vote.objects.filter(user=request.user).values_list('poll_id', flat=True)
    
    context = {
        'active_polls': active_polls,
        'upcoming_polls': upcoming_polls,
        'voted_poll_ids': voted_poll_ids,
    }
    
    return render(request, 'dashboard/user_dashboard.html', context)


# Update the poll_results_view to restrict access
# views.py

# views.py -> poll_results_view

from django.templatetags.static import static # Add this import at the top of the file

@login_required
def poll_results_view(request, poll_id):
    """Poll results view - ONLY for admins"""
    poll = get_object_or_404(Poll, id=poll_id)
    
    if not request.user.is_admin():
        messages.error(request, 'فقط المسؤولون يمكنهم عرض النتائج')
        return redirect('dashboard')
    
    user_vote = Vote.objects.filter(poll=poll, user=request.user).first() if request.user.user_type == 'user' else None
    
    total_votes = poll.get_total_votes()
    options_with_results = []
    
    for option in poll.options.all():
        vote_count = option.get_vote_count()
        percentage = option.get_vote_percentage(total_votes)
        options_with_results.append({
            'option': option,
            'vote_count': vote_count,
            'percentage': percentage
        })
        
    sorted_options_with_results = sorted(
        options_with_results, 
        key=lambda item: item['vote_count'], 
        reverse=True
    )

    # NEW: Get the absolute URL for the logo for printing
    logo_url = request.build_absolute_uri(static('club-logo.png'))
    
    context = {
        'poll': poll,
        'total_votes': total_votes,
        'options_with_results': sorted_options_with_results,
        'user_vote': user_vote,
        'logo_url': logo_url, # NEW: Pass the logo URL to the template
    }
    
    return render(request, 'polls/poll_results.html', context)

# Update the poll_detail_view to remove results redirect for normal users
@login_required
def poll_detail_view(request, poll_id):
    """Poll detail and voting"""
    poll = get_object_or_404(Poll, id=poll_id)
    
    # Check if user already voted
    user_vote = Vote.objects.filter(poll=poll, user=request.user).first()
    
    if request.method == 'POST' and not user_vote:
        option_id = request.POST.get('option_id')
        
        if not option_id:
            messages.error(request, 'الرجاء اختيار خيار')
            return render(request, 'polls/poll_detail.html', {'poll': poll})
        
        # Check if poll is still active
        if not poll.is_active():
            messages.error(request, 'هذا الاستطلاع لم يعد نشطاً')
            return redirect('dashboard')
        
        try:
            option = Option.objects.get(id=option_id, poll=poll)
            
            # Create vote
            Vote.objects.create(
                poll=poll,
                user=request.user,
                option=option,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, 'تم تسجيل صوتك بنجاح!')
            
            # Normal users go back to dashboard after voting, not to results
            if request.user.is_admin():
                return redirect('poll_results', poll_id=poll.id)
            else:
                return redirect('dashboard')
        
        except Option.DoesNotExist:
            messages.error(request, 'الخيار المحدد غير صحيح')
    
    context = {
        'poll': poll,
        'user_vote': user_vote,
        'can_vote': poll.is_active() and not user_vote,
        'can_view_results': request.user.is_admin(),  # Add this flag
    }
    
    return render(request, 'polls/poll_detail.html', context)

# ==================== Admin Views ====================

# Update admin_dashboard_view to restrict to super_admin only
@login_required
def admin_dashboard_view(request):
    """Admin dashboard - SUPER ADMIN ONLY"""
    if request.user.user_type != 'super_admin':
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة التحكم')
        return redirect('dashboard')
    
    # Get statistics
    total_users = CustomUser.objects.filter(user_type='user').count()
    total_polls = Poll.objects.count()
    active_polls = Poll.objects.filter(status='active').count()
    total_votes = Vote.objects.count()
    
    # Calculate verified users percentage
    verified_users_count = CustomUser.objects.filter(user_type='user', is_phone_verified=True).count()
    verified_users = round((verified_users_count / total_users * 100) if total_users > 0 else 0)
    
    # Recent polls (limit to 10)
    recent_polls = Poll.objects.all().order_by('-created_at')[:10]
    
    context = {
        'total_users': total_users,
        'total_polls': total_polls,
        'active_polls': active_polls,
        'total_votes': total_votes,
        'verified_users': verified_users,
        'recent_polls': recent_polls,
        'can_create_polls': request.user.can_create_polls(),
    }
    
    return render(request, 'admin/dashboard.html', context)


@login_required
def create_poll_view(request):
    """Create new poll (Super Admin only)"""
    if not request.user.can_create_polls():
        messages.error(request, 'Access denied')
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        options = request.POST.getlist('options')
        action = request.POST.get('action') # Get which button was clicked
        
        # Determine the status based on the button pressed
        if action == 'save_draft':
            poll_status = 'draft'
            success_message = 'Poll saved as draft successfully!'
        else: # Default action is to schedule
            poll_status = 'scheduled'
            success_message = 'Poll scheduled successfully!'
        
        if not all([title, start_time, end_time]) or len(options) < 2:
            messages.error(request, 'Title, start/end times, and at least 2 options are required')
            return render(request, 'admin/create_poll.html')
        
        try:
            # Create poll
            poll = Poll.objects.create(
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                created_by=request.user,
                 status=poll_status
            )
            
            # Create options
            for i, option_text in enumerate(options):
                if option_text.strip():
                    Option.objects.create(
                        poll=poll,
                        option_text=option_text.strip(),
                        order=i
                    )
            
            messages.success(request, 'Poll created successfully!')
            return redirect('poll_management')
        
        except Exception as e:
            messages.error(request, f'Error creating poll: {str(e)}')
    
    return render(request, 'admin/create_poll.html')

# views.py (add this new view in the Admin Views section)

@login_required
def update_poll_status_view(request, poll_id):
    """Manually update a poll's status (e.g., publish, close)."""
    if not request.user.can_create_polls():
        messages.error(request, 'Access denied')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        poll = get_object_or_404(Poll, id=poll_id)
        action = request.POST.get('action')

        if action == 'publish':
            # Publish a draft or scheduled poll immediately
            if poll.status in ['draft', 'scheduled']:
                poll.status = 'active'
                # Optional: update start time to now if it was in the future
                if poll.start_time > timezone.now():
                    poll.start_time = timezone.now()
                poll.save()
                messages.success(request, f"Poll '{poll.title}' has been published.")
        
        elif action == 'close':
            # Close an active poll immediately
            if poll.status == 'active':
                poll.status = 'closed'
                # Optional: update end time to now
                poll.end_time = timezone.now()
                poll.save()
                messages.success(request, f"Poll '{poll.title}' has been closed.")
        
        elif action == 'reopen':
            # Re-open a closed poll
            if poll.status == 'closed':
                poll.status = 'active'
                # You MUST set a new end date
                poll.end_time = timezone.now() + timedelta(days=1) # e.g., reopen for 1 day
                poll.save()
                messages.warning(request, f"Poll '{poll.title}' has been reopened and will close in 24 hours.")

    return redirect('poll_management')

@login_required
def poll_management_view(request):
    """Manage polls - Landing page for view_admin users"""
    if not request.user.is_admin():
        messages.error(request, 'ليس لديك صلاحية للوصول')
        return redirect('dashboard')
    
    # Add a welcome message for view_admin users
    if request.user.user_type == 'view_admin':
        messages.info(request, 'مرحباً! يمكنك عرض جميع الاستطلاعات والنتائج من هنا')
    
    # Search and filter functionality
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    polls = Poll.objects.all()
    
    if search_query:
        polls = polls.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    if status_filter:
        polls = polls.filter(status=status_filter)
    
    polls = polls.order_by(sort_by)
    
    paginator = Paginator(polls, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'can_create_polls': request.user.can_create_polls(),
        'is_view_admin': request.user.user_type == 'view_admin',  # Add flag for template
    }
    
    return render(request, 'admin/poll_management.html', context)

# ==================== AJAX Views ====================

@csrf_exempt
def resend_otp_view(request):
    """Resend OTP"""
    if request.method == 'POST':
        phone_number = request.session.get('registration_phone')
        
        if not phone_number:
            return JsonResponse({'success': False, 'message': 'Session expired'})
        
        # Check rate limiting (max 3 OTPs per 10 minutes)
        recent_otps = OTPLog.objects.filter(
            phone_number=phone_number,
            created_at__gte=timezone.now() - timedelta(minutes=10)
        ).count()
        
        if recent_otps >= 3:
            return JsonResponse({'success': False, 'message': 'Too many OTP requests. Please wait.'})
        
        # Generate new OTP using Chinguisoft
        success, otp_or_error = send_sms_otp(phone_number)
        
        if success:
            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                user.otp_code = otp_or_error
                user.otp_created_at = timezone.now()
                user.save()
                
                # Log OTP request
                OTPLog.objects.create(phone_number=phone_number, otp_code=otp_or_error)
                
                return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
            
            except CustomUser.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'User not found'})
        else:
            return JsonResponse({'success': False, 'message': f'Failed to send OTP: {otp_or_error}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})