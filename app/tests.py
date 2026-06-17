"""
Tests for clearing overdue schedules on successful script execution.
Tests for dynamic MCP tool generation.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
from app.models import Script, ScriptSchedule, ScriptExecution, GlobalCredential
from app.services.script_runner import ScriptRunner
# Import MCP server functions for testing
from app.mcp_server import (
    _get_mcp_tools_for_user,
    _convert_script_name_to_tool_name,
    _get_default_input_schema,
    _invalidate_mcp_tool_cache,
)


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


class GlobalCredentialTestCase(TestCase):
    """Test global credential management."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="testpass123"
        )

    def test_create_api_key_credential(self):
        """Test creating an API key credential."""
        cred = GlobalCredential.objects.create(
            user=self.user,
            name="My API Key",
            credential_type="api_key",
        )
        cred.set_encrypted_data({"api_key": "secret123"})
        cred.save()

        self.assertEqual(cred.name, "My API Key")
        self.assertEqual(cred.credential_type, "api_key")
        self.assertEqual(cred.get_decrypted_data(), {"api_key": "secret123"})

    def test_credential_user_isolation(self):
        """Test that users cannot access each other's credentials."""
        cred = GlobalCredential.objects.create(
            user=self.user,
            name="User Credential",
            credential_type="generic",
        )
        cred.set_encrypted_data({"key": "value"})
        cred.save()

        # Other user cannot see this credential
        other_creds = GlobalCredential.objects.filter(user=self.other_user)
        self.assertEqual(other_creds.count(), 0)

    def test_masked_value_never_returns_secret(self):
        """Test that get_masked_value never exposes actual secret values."""
        cred = GlobalCredential.objects.create(
            user=self.user,
            name="Test Credential",
            credential_type="api_key",
        )
        cred.set_encrypted_data({"api_key": "super_secret_key_12345"})
        cred.save()

        # Masked value should not contain the actual secret
        masked = cred.get_masked_value()
        self.assertNotIn("super_secret_key_12345", masked)
        self.assertIn("••", masked)  # Should have masked indicator (bullets)

    def test_attach_credential_to_script(self):
        """Test attaching credentials to scripts."""
        cred1 = GlobalCredential.objects.create(
            user=self.user,
            name="Cred 1",
            credential_type="generic",
        )
        cred2 = GlobalCredential.objects.create(
            user=self.user,
            name="Cred 2",
            credential_type="generic",
        )
        
        script = Script.objects.create(
            name="Test Script",
            language="python",
            code='print("test")',
            owner=self.user,
        )
        
        script.credentials.add(cred1, cred2)
        
        self.assertEqual(script.credentials.count(), 2)
        self.assertIn(cred1, script.credentials.all())
        self.assertIn(cred2, script.credentials.all())

    def test_script_expose_to_mcp_default_false(self):
        """Test that expose_to_mcp defaults to False."""
        script = Script.objects.create(
            name="Test Script",
            language="python",
            code='print("test")',
            owner=self.user,
        )
        
        self.assertFalse(script.expose_to_mcp)


class MCPExposureTestCase(TestCase):
    """Test MCP exposure functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_mcp_exposure_filtering(self):
        """Test that only exposed scripts are accessible via MCP."""
        # Create scripts with different exposure settings
        script_public = Script.objects.create(
            name="Public Script",
            language="python",
            code='print("public")',
            owner=self.user,
            is_public=True,
        )
        
        script_mcp = Script.objects.create(
            name="MCP Script",
            language="python",
            code='print("mcp")',
            owner=self.user,
            is_public=True,
            expose_to_mcp=True,
        )
        
        # Filter for MCP-exposed scripts
        mcp_scripts = Script.objects.filter(expose_to_mcp=True, is_public=True)
        
        self.assertEqual(mcp_scripts.count(), 1)
        self.assertEqual(mcp_scripts.first(), script_mcp)

    def test_mcp_exposure_can_be_toggled(self):
        """Test that MCP exposure can be enabled/disabled."""
        script = Script.objects.create(
            name="Test Script",
            language="python",
            code='print("test")',
            owner=self.user,
        )
        
        self.assertFalse(script.expose_to_mcp)
        
        script.expose_to_mcp = True
        script.save()
        
        self.assertTrue(Script.objects.get(id=script.id).expose_to_mcp)


class MCPToolNameConversionTestCase(TestCase):
    """Test MCP tool name conversion functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_script_name_to_tool_name_lowercase_snake_case(self):
        """Test that script names are converted to lowercase snake_case."""
        self.assertEqual(
            _convert_script_name_to_tool_name("Newsletter Builder"),
            "scriptdash_newsletter_builder"
        )
        self.assertEqual(
            _convert_script_name_to_tool_name("MyScript"),
            "scriptdash_my_script"
        )
        self.assertEqual(
            _convert_script_name_to_tool_name("API Script!"),
            "scriptdash_api_script"
        )

    def test_script_name_with_unsafe_characters(self):
        """Test that unsafe characters in script names are handled."""
        # Test special characters
        self.assertEqual(
            _convert_script_name_to_tool_name("My Script@#$%"),
            "scriptdash_my_script"
        )
        
        # Test starting with number
        self.assertEqual(
            _convert_script_name_to_tool_name("123 Script"),
            "scriptdash_123_script"
        )

    def test_custom_mcp_tool_name(self):
        """Test that custom MCP tool names are used when provided."""
        self.assertEqual(
            _convert_script_name_to_tool_name("Newsletter Builder", "newsletter_tool"),
            "newsletter_tool"
        )
        
        # Custom name should still be normalized
        self.assertEqual(
            _convert_script_name_to_tool_name("Newsletter Builder", "My Custom Tool!"),
            "my_custom_tool"
        )
        
        # Custom name starting with number should still get prefix for validity
        # but this test expects no scriptdash_ prefix for custom names
        # Actually, looking at the requirements again, custom names don't get scriptdash_ prefix
        # Let me update the function to match this expectation

    def test_empty_script_name(self):
        """Test handling of empty script names."""
        result = _convert_script_name_to_tool_name("")
        self.assertTrue(result.startswith("scriptdash_"))


class DynamicMCPToolTestCase(TestCase):
    """Test dynamic MCP tool registration functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="testpass123"
        )
        # Clear cache before each test
        _invalidate_mcp_tool_cache(self.user.id)

    def tearDown(self):
        """Clean up after tests."""
        # Clear cache after each test
        _invalidate_mcp_tool_cache(self.user.id)

    def test_only_exposed_scripts_get_dynamic_tools(self):
        """Test that only scripts with expose_to_mcp=True get dynamic tools."""
        script_hidden = Script.objects.create(
            name="Hidden Script",
            language="python",
            code='print("hidden")',
            owner=self.user,
            expose_to_mcp=False,
        )
        
        script_exposed = Script.objects.create(
            name="Exposed Script",
            language="python",
            code='print("exposed")',
            owner=self.user,
            expose_to_mcp=True,
        )
        
        # Force refresh by invalidating cache
        _invalidate_mcp_tool_cache(self.user.id)
        mcp_tools = _get_mcp_tools_for_user(self.user.id)
        
        mcp_tools_hidden = [t for t in mcp_tools if t["script_id"] == script_hidden.id]
        self.assertEqual(len(mcp_tools_hidden), 0)
        
        mcp_tools_exposed = [t for t in mcp_tools if t["script_id"] == script_exposed.id]
        self.assertEqual(len(mcp_tools_exposed), 1)

    def test_default_input_schema_generation(self):
        """Test that default input schema is generated for scripts without schema."""
        _invalidate_mcp_tool_cache(self.user.id)
        script = Script.objects.create(
            name="Test Script",
            language="python",
            code='print("test")',
            owner=self.user,
            expose_to_mcp=True,
        )
        
        # No schema set
        self.assertIsNone(script.input_schema)
        
        tools = _get_mcp_tools_for_user(self.user.id)
        tool = next((t for t in tools if t["script_id"] == script.id), None)
        
        self.assertIsNotNone(tool)
        self.assertIn("input_text", tool["input_schema"]["properties"])
        self.assertIn("timeout_seconds", tool["input_schema"]["properties"])

    def test_custom_input_schema(self):
        """Test that custom input schema is used when provided."""
        _invalidate_mcp_tool_cache(self.user.id)
        custom_schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to process"}
            },
            "required": ["message"]
        }
        
        script = Script.objects.create(
            name="Custom Schema Script",
            language="python",
            code='print(input)',
            owner=self.user,
            expose_to_mcp=True,
            input_schema=custom_schema,
        )
        
        tools = _get_mcp_tools_for_user(self.user.id)
        tool = next((t for t in tools if t["script_id"] == script.id), None)
        
        self.assertIsNotNone(tool)
        self.assertEqual(tool["input_schema"], custom_schema)

    def test_script_description_fallback(self):
        """Test that fallback description is used when script has no description."""
        _invalidate_mcp_tool_cache(self.user.id)
        script = Script.objects.create(
            name="Undescribed Script",
            language="python",
            code='print("test")',
            owner=self.user,
            expose_to_mcp=True,
            description="",
        )
        
        tools = _get_mcp_tools_for_user(self.user.id)
        tool = next((t for t in tools if t["script_id"] == script.id), None)
        
        self.assertIsNotNone(tool)
        self.assertIn("Undescribed Script", tool["description"])
        self.assertTrue(tool["description"].startswith("Run the ScriptDash script:"))

    def test_destructive_flag_propagation(self):
        """Test that destructive flag is properly set in tool definition."""
        _invalidate_mcp_tool_cache(self.user.id)
        script_safe = Script.objects.create(
            name="Safe Script",
            language="python",
            code='print("safe")',
            owner=self.user,
            expose_to_mcp=True,
            is_destructive=False,
        )
        
        script_destructive = Script.objects.create(
            name="Destructive Script",
            language="python",
            code='import os; os.remove("file")',
            owner=self.user,
            expose_to_mcp=True,
            is_destructive=True,
        )
        
        tools = _get_mcp_tools_for_user(self.user.id)
        
        tool_safe = next((t for t in tools if t["script_id"] == script_safe.id), None)
        tool_destructive = next((t for t in tools if t["script_id"] == script_destructive.id), None)
        
        self.assertFalse(tool_safe["is_destructive"])
        self.assertTrue(tool_destructive["is_destructive"])

    def test_user_isolation_in_mcp_tools(self):
        """Test that users can only see their own MCP-exposed scripts."""
        _invalidate_mcp_tool_cache(self.user.id)
        _invalidate_mcp_tool_cache(self.other_user.id)
        script_user = Script.objects.create(
            name="User Script",
            language="python",
            code='print("user")',
            owner=self.user,
            expose_to_mcp=True,
        )
        
        script_other = Script.objects.create(
            name="Other User Script",
            language="python",
            code='print("other")',
            owner=self.other_user,
            expose_to_mcp=True,
        )
        
        user_tools = _get_mcp_tools_for_user(self.user.id)
        other_tools = _get_mcp_tools_for_user(self.other_user.id)
        
        user_tool_ids = {t["script_id"] for t in user_tools}
        other_tool_ids = {t["script_id"] for t in other_tools}
        
        self.assertIn(script_user.id, user_tool_ids)
        self.assertNotIn(script_other.id, user_tool_ids)
        self.assertNotIn(script_user.id, other_tool_ids)
        self.assertIn(script_other.id, other_tool_ids)

    def test_no_secrets_exposed_in_tool_definitions(self):
        """Test that secrets/credentials are never exposed through tool definitions."""
        _invalidate_mcp_tool_cache(self.user.id)
        script = Script.objects.create(
            name="Secret Script",
            language="python",
            code='print(os.environ.get("SECRET"))',
            owner=self.user,
            expose_to_mcp=True,
        )
        
        cred = GlobalCredential.objects.create(
            user=self.user,
            name="API Credential",
            credential_type="api_key",
        )
        cred.set_encrypted_data({"api_key": "super_secret_api_key_12345"})
        cred.save()
        
        script.credentials.add(cred)
        
        tools = _get_mcp_tools_for_user(self.user.id)
        tool = next((t for t in tools if t["script_id"] == script.id), None)
        
        # Tool definition should not contain any secret values
        tool_str = str(tool)
        self.assertNotIn("super_secret_api_key_12345", tool_str)
        self.assertNotIn("SECRET", tool_str)

    def test_source_code_never_exposed(self):
        """Test that script source code is never in tool definitions."""
        _invalidate_mcp_tool_cache(self.user.id)
        script = Script.objects.create(
            name="Source Script",
            language="python",
            code='import os; os.system("rm -rf /")',  # Destructive code
            owner=self.user,
            expose_to_mcp=True,
        )
        
        tools = _get_mcp_tools_for_user(self.user.id)
        tool = next((t for t in tools if t["script_id"] == script.id), None)
        
        tool_str = str(tool)
        self.assertNotIn("rm -rf /", tool_str)
        self.assertNotIn("import os", tool_str)


class BackwardCompatibilityTestCase(TestCase):
    """Test backward compatibility - existing tools should still work."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_generic_tools_still_exist(self):
        """Test that generic tools like list_scripts, run_script still work."""
        # This test verifies that the generic tools are still present in the codebase
        from app.mcp_server import admin_mcp
        
        # Check that generic tools are registered on admin_mcp
        tool_names = list(admin_mcp._tool_manager._tools.keys())
        
        # These generic tools should always be present
        self.assertIn("list_scripts", tool_names)
        self.assertIn("run_script", tool_names)
        self.assertIn("get_execution", tool_names)

    def test_script_update_without_new_fields(self):
        """Test that script updates work without the new MCP fields."""
        script = Script.objects.create(
            name="Test Script",
            language="python",
            code='print("test")',
            owner=self.user,
        )
        
        # Update without new fields should still work
        script.name = "Updated Script"
        script.save()
        
        # New fields should have default values
        self.assertEqual(script.mcp_tool_name, "")
        self.assertIsNone(script.input_schema)
        self.assertFalse(script.is_destructive)

    def test_script_creation_backwards_compatible(self):
        """Test that script creation works with old parameters."""
        script = Script.objects.create(
            name="Simple Script",
            language="python",
            code='print("test")',
            owner=self.user,
        )
        
        # Default values should be applied
        self.assertFalse(script.expose_to_mcp)
        self.assertEqual(script.mcp_tool_name, "")
        self.assertIsNone(script.input_schema)
        self.assertFalse(script.is_destructive)

