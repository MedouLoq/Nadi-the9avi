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
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

from .models import CustomUser, Poll, Option, Vote, OTPLog, Team  # Add Team import

from .models import CustomUser, Poll, Option, Vote, OTPLog
from .utils import send_sms_otp  # You'll need to implement this with your SMS API


# ==================== Authentication Views ====================

# Add these imports to your existing views.py
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

from .models import CustomUser, Poll, Option, Vote, OTPLog, Team  # Add Team import

# Update the register_view to include full_name
def register_view(request):
    """User registration with phone number and full name"""
    if request.user.is_authenticated:
        if request.user.is_admin():
            return redirect('admin_dashboard')
        else:
            return redirect('dashboard')
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        full_name = request.POST.get('full_name')  # NEW: Get full name
        
        if not phone_number or not full_name:  # NEW: Require full name
            messages.error(request, 'رقم الهاتف والاسم الكامل مطلوبان')
            return render(request, 'registration/register.html')
        
        # Format phone number for Mauritania (normalize to 8 digits)
        from .utils import format_mauritanian_phone
        formatted_phone = format_mauritanian_phone(phone_number)
        
        if not formatted_phone:
            messages.error(request, 'يرجى إدخال رقم هاتف  صحيح (8 أرقام تبدأ بـ 2 أو 3 أو 4)')
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
                full_name=full_name,  # NEW: Add full name
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

# NEW: View for registered users list
@login_required
def registered_users_view(request):
    """View registered users - Admin only"""
    # if not request.user.is_admin():
    #     messages.error(request, 'ليس لديك صلاحية للوصول')
    #     return redirect('dashboard')
    
    # Search and filter functionality
    search_query = request.GET.get('search', '')
    verification_filter = request.GET.get('verification', '')
    
    users = CustomUser.objects.filter(user_type='user')
    
    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query) | 
            Q(phone_number__icontains=search_query)
        )
    
    if verification_filter:
        if verification_filter == 'verified':
            users = users.filter(is_phone_verified=True)
        elif verification_filter == 'unverified':
            users = users.filter(is_phone_verified=False)
    
    users = users.order_by('-created_at')
    
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    percentage_verified = 0
    if users.count() > 0:
        percentage_verified = round((users.filter(is_phone_verified=True).count() * 100) / users.count(), 2)
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'verification_filter': verification_filter,
        'total_users': users.count(),
        'verified_users': users.filter(is_phone_verified=True).count(),
        "percentage_verified": percentage_verified,
    }
    
    return render(request, 'admin/registered_users.html', context)

# NEW: Print registered users as PDF
@login_required
def print_users_pdf(request):
    """Generate PDF of registered users - Admin only"""
    if not request.user.is_admin():
        messages.error(request, 'ليس لديك صلاحية للوصول')
        return redirect('dashboard')
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="registered_users.pdf"'
    
    # Create the PDF object
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Container for 'story' elements
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1,  # Center alignment
    )
    
    # Add title
    title = Paragraph("قائمة المستخدمين المسجلين - النادي الثقافي لشباب لبير", title_style)
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Get users data
    users = CustomUser.objects.filter(user_type='user').order_by('full_name')
    
    # Create table data
    data = [['#', 'الاسم الكامل', 'رقم الهاتف', 'تاريخ التسجيل', 'مؤكد']]
    
    for i, user in enumerate(users, 1):
        data.append([
            str(i),
            user.full_name or 'غير محدد',
            user.phone_number or 'غير محدد',
            user.created_at.strftime('%Y-%m-%d'),
            'نعم' if user.is_phone_verified else 'لا'
        ])
    
    # Create table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

# NEW: Teams management view
@login_required
def teams_view(request):
    """View all registered teams - Public view"""
    teams = Team.objects.filter(is_active=True).order_by('name')
    
    context = {
        'teams': teams,
        'can_manage_teams': request.user.is_admin(),
    }
    
    return render(request, 'teams/teams_list.html', context)

# NEW: Team management view for admins
@login_required
def team_management_view(request):
    """Manage teams - Admin only"""
    if not request.user.is_admin():
        messages.error(request, 'ليس لديك صلاحية للوصول')
        return redirect('dashboard')
    
    # Search and filter functionality
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    teams = Team.objects.all()
    
    if search_query:
        teams = teams.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    if status_filter:
        if status_filter == 'active':
            teams = teams.filter(is_active=True)
        elif status_filter == 'inactive':
            teams = teams.filter(is_active=False)
    
    teams = teams.order_by('-created_at')
    
    paginator = Paginator(teams, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'can_create_teams': request.user.can_create_polls(),  # Same permission as polls
    }
    
    return render(request, 'admin/team_management.html', context)

# NEW: Create team view
@login_required
def create_team_view(request):
    """Create new team - Super Admin only"""
    if not request.user.can_create_polls():
        messages.error(request, 'ليس لديك صلاحية للوصول')
        return redirect('team_management')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        contact_info = request.POST.get('contact_info', '')
        image = request.FILES.get('image')
        program_document = request.FILES.get('program_document')
        
        if not name:
            messages.error(request, 'اسم الفريق مطلوب')
            return render(request, 'admin/create_team.html')
        
        try:
            team = Team.objects.create(
                name=name,
                description=description,
                contact_info=contact_info,
                image=image,
                program_document=program_document,
                created_by=request.user
            )
            
            messages.success(request, 'تم إنشاء الفريق بنجاح!')
            return redirect('team_management')
        
        except Exception as e:
            messages.error(request, f'خطأ في إنشاء الفريق: {str(e)}')
    
    return render(request, 'admin/create_team.html')

# NEW: Edit team view
@login_required
def edit_team_view(request, team_id):
    """Edit team - Super Admin only"""
    if not request.user.can_create_polls():
        messages.error(request, 'ليس لديك صلاحية للوصول')
        return redirect('team_management')
    
    team = get_object_or_404(Team, id=team_id)
    
    if request.method == 'POST':
        team.name = request.POST.get('name', team.name)
        team.description = request.POST.get('description', team.description)
        team.contact_info = request.POST.get('contact_info', team.contact_info)
        
        # Handle file uploads
        if request.FILES.get('image'):
            team.image = request.FILES['image']
        if request.FILES.get('program_document'):
            team.program_document = request.FILES['program_document']
        
        # Handle status
        team.is_active = request.POST.get('is_active') == 'on'
        
        try:
            team.save()
            messages.success(request, 'تم تحديث الفريق بنجاح!')
            return redirect('team_management')
        except Exception as e:
            messages.error(request, f'خطأ في تحديث الفريق: {str(e)}')
    
    context = {'team': team}
    return render(request, 'admin/edit_team.html', context)

# NEW: Team detail view
@login_required
def team_detail_view(request, team_id):
    """View team details"""
    team = get_object_or_404(Team, id=team_id)
    
    context = {
        'team': team,
        'can_edit': request.user.can_create_polls(),
    }
    
    return render(request, 'teams/team_detail.html', context)

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
                
                # FIXED: Use pop() instead of del to avoid KeyError
                request.session.pop('registration_phone', None)
                
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
    if request.user.is_authenticated:
        if request.user.is_admin():
            return redirect('admin_dashboard')
        else:
            return redirect('dashboard')
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
    """Create new poll (Super Admin only) - Team-based"""
    if not request.user.can_create_polls():
        messages.error(request, 'Access denied')
        return redirect('admin_dashboard')
    
    # Get available teams
    available_teams = Team.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        poll_type = request.POST.get('poll_type', 'team')  # 'team' or 'custom'
        action = request.POST.get('action')
        
        # Determine the status based on the button pressed
        if action == 'save_draft':
            poll_status = 'draft'
            success_message = 'Poll saved as draft successfully!'
        else:
            poll_status = 'scheduled'
            success_message = 'Poll scheduled successfully!'
        
        if not all([title, start_time, end_time]):
            messages.error(request, 'Title, start/end times are required')
            context = {'available_teams': available_teams}
            return render(request, 'admin/create_poll.html', context)
        
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
            
            if poll_type == 'team':
                # Create options based on selected teams
                selected_teams = request.POST.getlist('selected_teams')
                
                if len(selected_teams) < 2:
                    poll.delete()
                    messages.error(request, 'يجب اختيار فريقين على الأقل للتصويت')
                    context = {'available_teams': available_teams}
                    return render(request, 'admin/create_poll.html', context)
                
                for i, team_id in enumerate(selected_teams):
                    try:
                        team = Team.objects.get(id=team_id, is_active=True)
                        Option.objects.create(
                            poll=poll,
                            option_text=team.name,
                            team=team,
                            order=i
                        )
                    except Team.DoesNotExist:
                        continue
            
            else:
                # Create custom options (existing functionality)
                options = request.POST.getlist('options')
                
                if len(options) < 2:
                    poll.delete()
                    messages.error(request, 'At least 2 options are required')
                    context = {'available_teams': available_teams}
                    return render(request, 'admin/create_poll.html', context)
                
                for i, option_text in enumerate(options):
                    if option_text.strip():
                        Option.objects.create(
                            poll=poll,
                            option_text=option_text.strip(),
                            order=i
                        )
            
            messages.success(request, success_message)
            return redirect('poll_management')
        
        except Exception as e:
            messages.error(request, f'Error creating poll: {str(e)}')
    
    context = {'available_teams': available_teams}
    return render(request, 'admin/create_poll.html', context)
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