# urls.py (app level)
from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('logout/', views.logout_view, name='logout'),
    
    # User Dashboard URLs
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('poll/<uuid:poll_id>/', views.poll_detail_view, name='poll_detail'),
    path('poll/<uuid:poll_id>/results/', views.poll_results_view, name='poll_results'),
    
    # Admin URLs
    path('vote-admin/dashboard/', views.admin_dashboard_view, name='admin_dashboard'), 
    path('vote-admin/create-poll/', views.create_poll_view, name='create_poll'),
    path('vote-admin/polls/', views.poll_management_view, name='poll_management'),
    path('vote-admin/poll/<uuid:poll_id>/update-status/', views.update_poll_status_view, name='update_poll_status'),
    
    # NEW: User Management URLs
    path('vote-admin/users/', views.registered_users_view, name='registered_users'),
    path('vote-admin/users/print/', views.print_users_pdf, name='print_users_pdf'),
    
    # NEW: Team Management URLs
    path('teams/', views.teams_view, name='teams_list'),
    path('teams/<uuid:team_id>/', views.team_detail_view, name='team_detail'),
    path('vote-admin/teams/', views.team_management_view, name='team_management'),
    path('vote-admin/teams/create/', views.create_team_view, name='create_team'),
    path('vote-admin/teams/<uuid:team_id>/edit/', views.edit_team_view, name='edit_team'),
    
    # AJAX URLs
    path('ajax/resend-otp/', views.resend_otp_view, name='resend_otp'),
]