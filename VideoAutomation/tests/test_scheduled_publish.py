#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scheduled YouTube publish support."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
import types

googleapiclient = types.ModuleType("googleapiclient")
googleapiclient.discovery = types.ModuleType("googleapiclient.discovery")
googleapiclient.discovery.build = MagicMock()
googleapiclient.errors = types.ModuleType("googleapiclient.errors")


class _HttpError(Exception):
    def __init__(self, *args, **kwargs):
        self.resp = types.SimpleNamespace(status=500)
        super().__init__(*args)


googleapiclient.errors.HttpError = _HttpError
googleapiclient.http = types.ModuleType("googleapiclient.http")
googleapiclient.http.MediaFileUpload = MagicMock()
sys.modules.setdefault("googleapiclient", googleapiclient)
sys.modules.setdefault("googleapiclient.discovery", googleapiclient.discovery)
sys.modules.setdefault("googleapiclient.errors", googleapiclient.errors)
sys.modules.setdefault("googleapiclient.http", googleapiclient.http)

google_auth_oauthlib = types.ModuleType("google_auth_oauthlib")
google_auth_oauthlib.flow = types.ModuleType("google_auth_oauthlib.flow")
google_auth_oauthlib.flow.InstalledAppFlow = MagicMock()
sys.modules.setdefault("google_auth_oauthlib", google_auth_oauthlib)
sys.modules.setdefault("google_auth_oauthlib.flow", google_auth_oauthlib.flow)

google = types.ModuleType("google")
google.oauth2 = types.ModuleType("google.oauth2")
google.oauth2.credentials = types.ModuleType("google.oauth2.credentials")
google.oauth2.credentials.Credentials = MagicMock()
google.auth = types.ModuleType("google.auth")
google.auth.transport = types.ModuleType("google.auth.transport")
google.auth.transport.requests = types.ModuleType("google.auth.transport.requests")
google.auth.transport.requests.Request = MagicMock()
sys.modules.setdefault("google", google)
sys.modules.setdefault("google.oauth2", google.oauth2)
sys.modules.setdefault("google.oauth2.credentials", google.oauth2.credentials)
sys.modules.setdefault("google.auth", google.auth)
sys.modules.setdefault("google.auth.transport", google.auth.transport)
sys.modules.setdefault("google.auth.transport.requests", google.auth.transport.requests)

sys.modules.setdefault("httplib2", types.ModuleType("httplib2"))

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.config import PipelineConfig
from automation.pipeline import AutomationPipeline
from automation.state import PipelineState
from automation.youtube import YouTubeUploader


class TestScheduledPublishConfig(unittest.TestCase):
    def test_config_round_trip_includes_scheduled_publish_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = PipelineConfig(work_dir=Path(tmp))
            config.youtube.scheduled_publish_days = 7
            config.save(path)

            loaded = PipelineConfig.from_file(path)
            self.assertEqual(loaded.youtube.scheduled_publish_days, 7)
            self.assertEqual(loaded.youtube.default_privacy, "public")
            self.assertEqual(loaded.youtube.default_category, "10")

    def test_config_round_trip_keeps_legacy_publish_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                """
                {
                  "youtube": {
                    "publish_days": 9
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            loaded = PipelineConfig.from_file(path)
            self.assertEqual(loaded.youtube.scheduled_publish_days, 9)


class TestScheduledPublishState(unittest.TestCase):
    def test_state_tracks_scheduled_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "state.json"
            state = PipelineState(state_file)
            state.add_video(
                video_id="abc123",
                title="Test",
                scheduled_publish_at="2026-03-24T10:00:00Z",
            )

            video = state.get_video("abc123")
            self.assertIsNotNone(video)
            self.assertEqual(video.scheduled_publish_at, "2026-03-24T10:00:00Z")
            self.assertEqual(state.stats["scheduled_videos"], 1)


class TestYouTubeScheduledUpload(unittest.TestCase):
    @patch("automation.youtube.MediaFileUpload")
    @patch("automation.youtube.build")
    def test_upload_sets_publish_at_for_scheduled_videos(self, mock_build, mock_media):
        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = [(None, None), (None, {"id": "video123"})]
        mock_insert = MagicMock(return_value=mock_request)
        mock_videos = MagicMock(return_value=MagicMock(insert=mock_insert))
        mock_build.return_value = MagicMock(videos=mock_videos)

        uploader = YouTubeUploader()
        uploader.youtube = mock_build.return_value

        video_path = Path("/tmp/video.mp4")
        with patch.object(Path, "exists", return_value=True):
            uploader.upload_video(
                video_path=video_path,
                title="Scheduled Upload",
                description="Desc",
                tags=["tag1"],
                publish_at="2026-03-24T10:00:00Z",
        )

        _, kwargs = mock_insert.call_args
        self.assertEqual(kwargs["body"]["status"]["privacyStatus"], "private")
        self.assertEqual(kwargs["body"]["status"]["publishAt"], "2026-03-24T10:00:00Z")


class TestPipelineScheduledPublish(unittest.TestCase):
    def test_pipeline_uses_utc_schedule_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = PipelineConfig(work_dir=Path(tmp))
            config.youtube.scheduled_publish_days = 2
            pipeline = AutomationPipeline(config)
            scheduled = pipeline._scheduled_publish_at()

            self.assertTrue(scheduled.endswith("Z"))
            parsed = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            self.assertEqual(parsed.tzinfo, timezone.utc)
