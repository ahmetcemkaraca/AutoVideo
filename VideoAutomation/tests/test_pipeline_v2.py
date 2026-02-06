#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for VideoAutomation pipeline v2 components.

Tests cover:
- Error handling and categorization
- State management and persistence
- Configuration validation
- Retry policies and circuit breakers
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.errors import (
    ErrorCategory, ErrorSeverity, ErrorContext,
    RetryPolicy, ErrorTracker, CircuitBreaker,
    categorize_google_api_error, with_retry
)
from automation.config_v2 import (
    PipelineConfig, YouTubeConfig, RenderConfig,
    VideoCodec, PrivacyStatus, validate_with_schema
)
from automation.state_v2 import (
    StateManager, VideoRecord, PipelineStats, StateMigration
)
from automation.monitoring import (
    MonitorDashboard, PipelineStatus, TaskProgress, TaskType
)


class TestErrorHandling(unittest.TestCase):
    """Test error handling components."""

    def test_categorize_api_errors(self):
        """Test API error categorization."""
        # Test rate limiting
        context = categorize_google_api_error(429, "Rate limit exceeded")
        self.assertEqual(context.category, ErrorCategory.QUOTA)
        self.assertTrue(context.can_retry)

        # Test server error
        context = categorize_google_api_error(500, "Internal server error")
        self.assertEqual(context.category, ErrorCategory.TRANSIENT)
        self.assertTrue(context.can_retry)

        # Test auth error
        context = categorize_google_api_error(401, "Invalid credentials")
        self.assertEqual(context.category, ErrorCategory.AUTHENTICATION)
        self.assertFalse(context.can_retry)

    def test_retry_policy(self):
        """Test retry policy calculations."""
        # Disable jitter for deterministic testing
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )

        # Test exponential backoff
        delay_0 = policy.get_delay(0)
        delay_1 = policy.get_delay(1)
        delay_2 = policy.get_delay(2)

        self.assertGreater(delay_1, delay_0)
        self.assertGreater(delay_2, delay_1)
        self.assertEqual(delay_0, 1.0)
        self.assertEqual(delay_1, 2.0)
        self.assertEqual(delay_2, 4.0)

        # Test max delay
        policy = RetryPolicy(max_delay=10.0, base_delay=1.0, jitter=False)
        delay = policy.get_delay(20)  # Would exceed max
        self.assertLessEqual(delay, 10.0)

    def test_retry_policy_with_jitter(self):
        """Test retry policy with jitter enabled."""
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True
        )

        # With jitter, delays should vary but follow exponential pattern
        delay_0 = policy.get_delay(0)
        delay_1 = policy.get_delay(1)
        delay_2 = policy.get_delay(2)

        # Should be in approximately the right range (base +/- 25%)
        self.assertGreater(delay_0, 0.5)  # 1.0 - 25%
        self.assertLess(delay_0, 1.5)    # 1.0 + 25%

        self.assertGreater(delay_1, 1.0)  # 2.0 - 25%
        self.assertLess(delay_1, 3.0)    # 2.0 + 25%

        self.assertGreater(delay_2, 2.5)  # 4.0 - 25%
        self.assertLess(delay_2, 5.5)    # 4.0 + 25%

    def test_error_tracker(self):
        """Test error tracking."""
        tracker = ErrorTracker(window_seconds=3600)

        # Record errors
        tracker.record(ErrorContext(
            category=ErrorCategory.TRANSIENT,
            message="Test error 1"
        ))
        tracker.record(ErrorContext(
            category=ErrorCategory.PERMANENT,
            message="Test error 2"
        ))

        # Check counts
        self.assertEqual(tracker.get_error_count(), 2)
        self.assertEqual(tracker.get_error_count(ErrorCategory.TRANSIENT), 1)
        self.assertEqual(tracker.get_error_count(ErrorCategory.PERMANENT), 1)

        # Check summary
        summary = tracker.get_summary()
        self.assertEqual(summary["total_errors"], 2)
        self.assertIn("by_category", summary)

    def test_circuit_breaker(self):
        """Test circuit breaker behavior."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        # Should start closed
        self.assertEqual(cb.state, "CLOSED")

        # Successful call
        result = cb.call(lambda: "success")
        self.assertEqual(result, "success")
        self.assertEqual(cb.state, "CLOSED")

        # Failures
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except:
                pass

        # Should be open now
        self.assertEqual(cb.state, "OPEN")

        # Should block calls
        with self.assertRaises(Exception):
            cb.call(lambda: "blocked")

        # Reset
        cb.reset()
        self.assertEqual(cb.state, "CLOSED")


class TestConfiguration(unittest.TestCase):
    """Test configuration management."""

    def setUp(self):
        """Create temp directory for test configs."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)

    def test_youtube_config_validation(self):
        """Test YouTube config validation."""
        # Valid config
        config = YouTubeConfig()
        errors = config.validate()
        self.assertEqual(len(errors), 0)

        # Invalid privacy
        config = YouTubeConfig(default_privacy="invalid")
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("privacy" in e.lower() for e in errors))

    def test_render_config_validation(self):
        """Test render config validation."""
        # Valid config
        config = RenderConfig()
        errors = config.validate()
        self.assertEqual(len(errors), 0)

        # Invalid codec
        config = RenderConfig(codec="invalid")
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("codec" in e.lower() for e in errors))

        # Invalid duration format
        config = RenderConfig(target_duration="invalid")
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("duration" in e.lower() for e in errors))

    def test_pipeline_config_defaults(self):
        """Test pipeline config default values."""
        config = PipelineConfig()

        self.assertIsInstance(config.work_dir, Path)
        self.assertIsInstance(config.music_dir, Path)
        self.assertIsInstance(config.output_dir, Path)
        self.assertEqual(config.music_dir, config.work_dir / "music")
        self.assertEqual(config.output_dir, config.work_dir / "output")

    def test_pipeline_config_save_load(self):
        """Test saving and loading pipeline config."""
        config = PipelineConfig(
            continuous_mode=True,
            delay_between_videos=600
        )

        config.save(self.config_path)

        # Load config
        loaded = PipelineConfig.from_file(self.config_path)

        self.assertEqual(loaded.continuous_mode, True)
        self.assertEqual(loaded.delay_between_videos, 600)


class TestStateManager(unittest.TestCase):
    """Test state management."""

    def setUp(self):
        """Create temp directory for test states."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / "test_state.json"

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)

    def test_state_initialization(self):
        """Test state manager initialization."""
        manager = StateManager(self.state_file, auto_backup=False)

        self.assertEqual(manager.video_count, 0)
        self.assertTrue(manager.is_healthy)

    def test_add_video(self):
        """Test adding video records."""
        manager = StateManager(self.state_file, auto_backup=False)

        manager.add_video(
            video_id="test123",
            title="Test Video",
            genre="ambient",
            style="relaxing"
        )

        self.assertEqual(manager.video_count, 1)

        video = manager.get_video("test123")
        self.assertIsNotNone(video)
        self.assertEqual(video.title, "Test Video")
        self.assertEqual(video.genre, "ambient")

    def test_upload_status_tracking(self):
        """Test upload status tracking."""
        manager = StateManager(self.state_file, auto_backup=False)

        manager.add_video(
            video_id="test123",
            title="Test Video"
        )

        # Mark attempt
        manager.mark_upload_attempt("test123")
        video = manager.get_video("test123")
        self.assertEqual(video.upload_attempts, 1)

        # Mark success
        manager.mark_upload_success("test123")
        video = manager.get_video("test123")
        self.assertIsNotNone(video.uploaded_at)

        # Mark failure
        manager.mark_upload_failed("test123", "Upload failed")
        video = manager.get_video("test123")
        self.assertEqual(video.last_error, "Upload failed")

    def test_state_persistence(self):
        """Test state persistence across reloads."""
        # Create and save state
        manager1 = StateManager(self.state_file, auto_backup=False)
        manager1.add_video(
            video_id="test123",
            title="Test Video"
        )

        # Load in new manager
        manager2 = StateManager(self.state_file, auto_backup=False)

        self.assertEqual(manager2.video_count, 1)
        video = manager2.get_video("test123")
        self.assertEqual(video.title, "Test Video")

    def test_state_validation(self):
        """Test state validation."""
        manager = StateManager(self.state_file, auto_backup=False)

        # Add valid video
        manager.add_video(
            video_id="test123",
            title="Test Video"
        )

        is_valid, issues = manager.validate()
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)

    def test_state_export_import(self):
        """Test state export and import."""
        manager1 = StateManager(self.state_file, auto_backup=False)
        manager1.add_video(
            video_id="test123",
            title="Test Video"
        )

        # Export
        json_data = manager1.export_json()
        self.assertIsNotNone(json_data)

        # Import to new state
        new_state_file = Path(self.temp_dir) / "new_state.json"
        manager2 = StateManager(new_state_file, auto_backup=False)
        manager2.import_json(json_data)

        self.assertEqual(manager2.video_count, 1)
        video = manager2.get_video("test123")
        self.assertEqual(video.title, "Test Video")


class TestMonitoring(unittest.TestCase):
    """Test monitoring dashboard."""

    def test_dashboard_initialization(self):
        """Test dashboard initialization."""
        dashboard = MonitorDashboard(enable_live=False)

        self.assertEqual(dashboard.status, PipelineStatus.IDLE)
        self.assertEqual(len(dashboard.tasks), 0)
        self.assertEqual(len(dashboard.errors), 0)

    def test_task_tracking(self):
        """Test task progress tracking."""
        dashboard = MonitorDashboard(enable_live=False)

        task = TaskProgress(
            task_id="test_task",
            task_type=TaskType.RENDER,
            description="Test render task"
        )

        dashboard.add_task(task)

        self.assertEqual(len(dashboard.tasks), 1)

        # Update progress
        dashboard.update_task("test_task", 50, 100)
        self.assertEqual(dashboard.tasks["test_task"].current, 50)

        # Complete task
        dashboard.complete_task("test_task")
        self.assertTrue(dashboard.tasks["test_task"].completed)

    def test_error_tracking(self):
        """Test error tracking."""
        dashboard = MonitorDashboard(enable_live=False)

        dashboard.add_error("test_category", "Test error message", "high")

        self.assertEqual(len(dashboard.errors), 1)
        self.assertEqual(dashboard.errors[0].category, "test_category")
        self.assertEqual(dashboard.errors[0].severity, "high")

    def test_status_updates(self):
        """Test status updates."""
        dashboard = MonitorDashboard(enable_live=False)

        dashboard.set_status(PipelineStatus.RENDERING, "Rendering video...")
        self.assertEqual(dashboard.status, PipelineStatus.RENDERING)
        self.assertEqual(dashboard.status_message, "Rendering video...")

    def test_metrics_tracking(self):
        """Test metrics tracking."""
        dashboard = MonitorDashboard(enable_live=False)

        dashboard.start_run(1)
        self.assertEqual(dashboard.current_iteration, 1)

        dashboard.complete_run(success=True, render_time=100.0, upload_time=50.0)
        self.assertEqual(dashboard.metrics.total_runs, 1)
        self.assertEqual(dashboard.metrics.successful_runs, 1)
        self.assertEqual(dashboard.metrics.total_render_time, 100.0)

    def test_upload_tracking(self):
        """Test upload tracking."""
        dashboard = MonitorDashboard(enable_live=False)

        dashboard.add_upload("Test Video", "success", "abc123")

        self.assertEqual(len(dashboard.recent_uploads), 1)
        self.assertEqual(dashboard.recent_uploads[0]["title"], "Test Video")
        self.assertEqual(dashboard.recent_uploads[0]["status"], "success")


class TestRetryDecorator(unittest.TestCase):
    """Test retry decorator."""

    def test_successful_call(self):
        """Test successful call without retry."""
        policy = RetryPolicy(max_attempts=3)

        @with_retry(policy)
        def test_func():
            return "success"

        result = test_func()
        self.assertEqual(result, "success")

    def test_retry_on_failure(self):
        """Test retry on transient failure."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)

        attempts = []

        @with_retry(policy)
        def test_func():
            attempts.append(1)
            if len(attempts) < 2:
                raise Exception("Transient error")
            return "success"

        result = test_func()
        self.assertEqual(result, "success")
        self.assertEqual(len(attempts), 2)

    def test_max_attempts_exceeded(self):
        """Test failure after max attempts."""
        policy = RetryPolicy(max_attempts=2, base_delay=0.01)

        @with_retry(policy)
        def test_func():
            raise Exception("Persistent error")

        with self.assertRaises(Exception):
            test_func()


class TestIntegration(unittest.TestCase):
    """Integration tests for pipeline components."""

    def setUp(self):
        """Create temp directory."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)

    def test_config_state_integration(self):
        """Test config and state manager integration."""
        config_path = Path(self.temp_dir) / "config.json"
        state_path = Path(self.temp_dir) / "state.json"

        # Create config
        config = PipelineConfig(
            work_dir=Path(self.temp_dir),
            state_file=state_path
        )

        # Initialize state
        state = StateManager(state_path, auto_backup=False)

        # Add video
        state.add_video(
            video_id="test123",
            title="Test Video"
        )

        # Verify
        self.assertEqual(state.video_count, 1)
        self.assertEqual(state.stats.total_videos_created, 1)


if __name__ == "__main__":
    unittest.main()
