"""
Tests for clearing overdue schedules on successful script execution.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
from app.models import Script, ScriptSchedule, ScriptExecution
from app.services.script_runner import ScriptRunner


class ClearOverdueSchedulesTestCase(TestCase):
    """Test that overdue schedules are cleared on successful script execution."""

    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

        # Create a test script
        self.script = Script.objects.create(
            name="Test Script",
            description="A test script",
            language="python",
            code='print("Hello, World!")',
            owner=self.user,
        )

    def test_clear_overdue_schedules_method(self):
        """Test the _clear_overdue_schedules method directly."""
        # Create a schedule with next_run in the past (overdue)
        past_time = timezone.now() - timedelta(hours=2)
        schedule = ScriptSchedule.objects.create(
            script=self.script,
            name="Test Schedule",
            schedule_type="interval",
            start_datetime=past_time,
            interval_unit="hours",
            interval_value=2,
            next_run=past_time,
            is_active=True,
            created_by=self.user,
        )

        # Verify the script has overdue schedules
        self.assertTrue(
            self.script.has_overdue_schedules,
            "Script should have overdue schedules before clearing",
        )

        # Create a script runner
        runner = ScriptRunner(self.script)
        execution = ScriptExecution.objects.create(
            script=self.script,
            triggered_by=self.user,
            status="success",
        )
        runner.execution = execution

        # Mock schedule_job to prevent actual scheduler interaction
        with patch("app.services.scheduler.schedule_job") as mock_schedule_job:
            # Call the method directly
            runner._clear_overdue_schedules()

            # Verify that schedule_job was called for the overdue schedule
            mock_schedule_job.assert_called_once()
            called_schedule = mock_schedule_job.call_args[0][0]
            self.assertEqual(called_schedule.id, schedule.id)

    def test_has_overdue_schedules_property(self):
        """Test the has_overdue_schedules property."""
        # Create a schedule with next_run in the past (overdue)
        past_time = timezone.now() - timedelta(hours=1)
        ScriptSchedule.objects.create(
            script=self.script,
            name="Overdue Schedule",
            schedule_type="single",
            start_datetime=past_time,
            next_run=past_time,
            is_active=True,
            created_by=self.user,
        )

        # Check that the script has overdue schedules
        self.assertTrue(self.script.has_overdue_schedules)

    def test_no_overdue_schedules(self):
        """Test when there are no overdue schedules."""
        # Create a schedule with next_run in the future
        future_time = timezone.now() + timedelta(hours=1)
        ScriptSchedule.objects.create(
            script=self.script,
            name="Future Schedule",
            schedule_type="single",
            start_datetime=future_time,
            next_run=future_time,
            is_active=True,
            created_by=self.user,
        )

        # Check that the script does not have overdue schedules
        self.assertFalse(self.script.has_overdue_schedules)

    def test_inactive_schedule_not_overdue(self):
        """Test that inactive schedules are not considered overdue."""
        # Create an inactive schedule with next_run in the past
        past_time = timezone.now() - timedelta(hours=1)
        ScriptSchedule.objects.create(
            script=self.script,
            name="Inactive Schedule",
            schedule_type="single",
            start_datetime=past_time,
            next_run=past_time,
            is_active=False,
            created_by=self.user,
        )

        # Check that the script does not have overdue schedules
        self.assertFalse(self.script.has_overdue_schedules)

    def test_multiple_overdue_schedules(self):
        """Test clearing multiple overdue schedules."""
        # Create multiple schedules with next_run in the past
        past_time1 = timezone.now() - timedelta(hours=2)
        past_time2 = timezone.now() - timedelta(hours=1)

        schedule1 = ScriptSchedule.objects.create(
            script=self.script,
            name="Overdue Schedule 1",
            schedule_type="interval",
            start_datetime=past_time1,
            interval_unit="hours",
            interval_value=3,
            next_run=past_time1,
            is_active=True,
            created_by=self.user,
        )

        schedule2 = ScriptSchedule.objects.create(
            script=self.script,
            name="Overdue Schedule 2",
            schedule_type="interval",
            start_datetime=past_time2,
            interval_unit="hours",
            interval_value=2,
            next_run=past_time2,
            is_active=True,
            created_by=self.user,
        )

        # Verify the script has overdue schedules
        self.assertTrue(self.script.has_overdue_schedules)

        # Create a script runner
        runner = ScriptRunner(self.script)
        execution = ScriptExecution.objects.create(
            script=self.script,
            triggered_by=self.user,
            status="success",
        )
        runner.execution = execution

        # Mock schedule_job to prevent actual scheduler interaction
        with patch("app.services.scheduler.schedule_job") as mock_schedule_job:
            # Call the method directly
            runner._clear_overdue_schedules()

            # Verify that schedule_job was called for both overdue schedules
            self.assertEqual(mock_schedule_job.call_count, 2)
            called_schedule_ids = {
                call[0][0].id for call in mock_schedule_job.call_args_list
            }
            self.assertEqual(called_schedule_ids, {schedule1.id, schedule2.id})

