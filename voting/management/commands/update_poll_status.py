#commands/update_poll_status.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from voting.models import Poll  # Replace with your app name


class Command(BaseCommand):
    help = 'Update poll statuses based on current time'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
    
    def handle(self, *args, **options):
        now = timezone.now()
        updated_count = 0
        
        # Update scheduled polls to active
        scheduled_polls = Poll.objects.filter(
            status='scheduled',
            start_time__lte=now
        )
        
        for poll in scheduled_polls:
            if now <= poll.end_time:
                poll.status = 'active'
                poll.save()
                updated_count += 1
                if options['verbose']:
                    self.stdout.write(f"Poll '{poll.title}' activated")
        
        # Update active polls to closed
        active_polls = Poll.objects.filter(
            status='active',
            end_time__lt=now
        )
        
        for poll in active_polls:
            poll.status = 'closed'
            poll.save()
            updated_count += 1
            if options['verbose']:
                self.stdout.write(f"Poll '{poll.title}' closed")
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} polls')
        )


# management/commands/create_admin_user.py
from django.core.management.base import BaseCommand
from django.core.management import CommandError
from voting.models import CustomUser  # Replace with your app name


class Command(BaseCommand):
    help = 'Create admin users (view_admin or super_admin)'
    
    def add_arguments(self, parser):
        parser.add_argument('phone_number', type=str, help='Phone number for the admin')
        parser.add_argument('password', type=str, help='Password for the admin')
        parser.add_argument(
            '--type',
            type=str,
            choices=['view_admin', 'super_admin'],
            default='view_admin',
            help='Type of admin to create'
        )
    
    def handle(self, *args, **options):
        phone_number = options['phone_number']
        password = options['password']
        admin_type = options['type']
        
        # Check if user already exists
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise CommandError(f'User with phone number {phone_number} already exists')
        
        # Create admin user
        admin_user = CustomUser.objects.create_user(
            phone_number=phone_number,
            username=phone_number,
            password=password,
            user_type=admin_type,
            is_phone_verified=True,
            is_staff=True if admin_type == 'super_admin' else False
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {admin_type} with phone number {phone_number}'
            )
        )


# management/commands/send_poll_notifications.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from voting.models import Poll, CustomUser
from voting.utils import send_sms_notification


class Command(BaseCommand):
    help = 'Send notifications about upcoming or active polls'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--upcoming',
            action='store_true',
            help='Send notifications for upcoming polls (starting in 1 hour)',
        )
        parser.add_argument(
            '--closing',
            action='store_true',
            help='Send notifications for polls closing in 1 hour',
        )
    
    def handle(self, *args, **options):
        now = timezone.now()
        sent_count = 0
        
        if options['upcoming']:
            # Notify about polls starting in 1 hour
            upcoming_polls = Poll.objects.filter(
                status='scheduled',
                start_time__gte=now,
                start_time__lte=now + timedelta(hours=1)
            )
            
            users = CustomUser.objects.filter(
                user_type='user',
                is_phone_verified=True
            )
            
            for poll in upcoming_polls:
                message = f"Voting will start soon for: {poll.title}. Be ready to vote!"
                
                for user in users:
                    if send_sms_notification(user.phone_number, message):
                        sent_count += 1
        
        if options['closing']:
            # Notify about polls closing in 1 hour
            closing_polls = Poll.objects.filter(
                status='active',
                end_time__gte=now,
                end_time__lte=now + timedelta(hours=1)
            )
            
            # Get users who haven't voted yet
            for poll in closing_polls:
                voted_user_ids = poll.votes.values_list('user_id', flat=True)
                users_not_voted = CustomUser.objects.filter(
                    user_type='user',
                    is_phone_verified=True
                ).exclude(id__in=voted_user_ids)
                
                message = f"Last chance to vote! '{poll.title}' closes in 1 hour."
                
                for user in users_not_voted:
                    if send_sms_notification(user.phone_number, message):
                        sent_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully sent {sent_count} notifications')
        )


# management/commands/cleanup_old_otps.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from voting.models import OTPLog


class Command(BaseCommand):
    help = 'Clean up old OTP logs (older than 24 hours)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Delete OTP logs older than this many hours (default: 24)',
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        deleted_count, _ = OTPLog.objects.filter(
            created_at__lt=cutoff_time
        ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {deleted_count} old OTP logs (older than {hours} hours)'
            )
        )


# management/commands/export_poll_results.py
import csv
from django.core.management.base import BaseCommand
from django.utils import timezone
from voting.models import Poll


class Command(BaseCommand):
    help = 'Export poll results to CSV'
    
    def add_arguments(self, parser):
        parser.add_argument('poll_id', type=str, help='Poll ID to export')
        parser.add_argument(
            '--output',
            type=str,
            default='poll_results.csv',
            help='Output filename (default: poll_results.csv)'
        )
    
    def handle(self, *args, **options):
        poll_id = options['poll_id']
        output_file = options['output']
        
        try:
            poll = Poll.objects.get(id=poll_id)
        except Poll.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Poll with ID {poll_id} not found'))
            return
        
        # Create CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            writer.writerow([
                'Poll Title',
                'Option',
                'Vote Count',
                'Percentage'
            ])
            
            total_votes = poll.get_total_votes()
            
            # Data rows
            for option in poll.options.all():
                vote_count = option.get_vote_count()
                percentage = option.get_vote_percentage(total_votes)
                
                writer.writerow([
                    poll.title,
                    option.option_text,
                    vote_count,
                    f"{percentage:.2f}%"
                ])
            
            # Summary row
            writer.writerow([])
            writer.writerow(['Total Votes', '', total_votes, '100.00%'])
        
        self.stdout.write(
            self.style.SUCCESS(f'Poll results exported to {output_file}')
        )