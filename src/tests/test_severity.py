"""
Unit tests for severity classification logic and Pydantic complaint models.
"""
import sys
import os
import pytest

# Add src/ to path so we can import dashboard_api modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard_api.models.complaint import (
    classify_severity,
    ComplaintPayload,
    ComplaintRecord,
)


# =================== classify_severity() ===================

class TestClassifySeverity:
    """Tests for the classify_severity helper function."""

    def test_low_severity(self):
        assert classify_severity(5) == "Low"
        assert classify_severity(10) == "Low"
        assert classify_severity(19.9) == "Low"

    def test_medium_severity(self):
        assert classify_severity(20) == "Medium"
        assert classify_severity(25) == "Medium"
        assert classify_severity(39.9) == "Medium"

    def test_high_severity(self):
        assert classify_severity(40) == "High"
        assert classify_severity(50) == "High"
        assert classify_severity(69.9) == "High"

    def test_critical_severity(self):
        assert classify_severity(70) == "Critical"
        assert classify_severity(80) == "Critical"
        assert classify_severity(100) == "Critical"

    def test_boundary_zero(self):
        assert classify_severity(0) == "Low"

    def test_boundary_exact_thresholds(self):
        """Exact boundary values: 20, 40, 70."""
        assert classify_severity(20) == "Medium"
        assert classify_severity(40) == "High"
        assert classify_severity(70) == "Critical"

    def test_just_below_thresholds(self):
        """Values just below each boundary."""
        assert classify_severity(19.99) == "Low"
        assert classify_severity(39.99) == "Medium"
        assert classify_severity(69.99) == "High"


# =================== ComplaintPayload ===================

class TestComplaintPayload:
    """Tests for the ComplaintPayload Pydantic model."""

    def test_valid_payload(self):
        payload = ComplaintPayload(
            location="Test Street, Jalna",
            timestamp="20260607-120000",
            garbage_percentage=45.5,
            detected_time=320.0,
            image_path="garbage_20260607-120000.jpg"
        )
        assert payload.location == "Test Street, Jalna"
        assert payload.garbage_percentage == 45.5
        assert payload.detected_time == 320.0

    def test_payload_boundary_values(self):
        """garbage_percentage should accept 0 and 100."""
        payload_zero = ComplaintPayload(
            location="Test", timestamp="t", garbage_percentage=0,
            detected_time=0, image_path="img.jpg"
        )
        assert payload_zero.garbage_percentage == 0

        payload_max = ComplaintPayload(
            location="Test", timestamp="t", garbage_percentage=100,
            detected_time=0, image_path="img.jpg"
        )
        assert payload_max.garbage_percentage == 100

    def test_payload_invalid_garbage_percentage(self):
        """garbage_percentage > 100 or < 0 should raise validation error."""
        with pytest.raises(Exception):
            ComplaintPayload(
                location="Test", timestamp="t", garbage_percentage=101,
                detected_time=0, image_path="img.jpg"
            )
        with pytest.raises(Exception):
            ComplaintPayload(
                location="Test", timestamp="t", garbage_percentage=-1,
                detected_time=0, image_path="img.jpg"
            )

    def test_payload_negative_detected_time(self):
        """detected_time < 0 should raise validation error."""
        with pytest.raises(Exception):
            ComplaintPayload(
                location="Test", timestamp="t", garbage_percentage=50,
                detected_time=-10, image_path="img.jpg"
            )


# =================== ComplaintRecord ===================

class TestComplaintRecord:
    """Tests for the ComplaintRecord model and from_payload factory."""

    def test_from_payload_creates_record(self):
        payload = ComplaintPayload(
            location="Market Square, Jalna",
            timestamp="20260607-130000",
            garbage_percentage=55.0,
            detected_time=400.0,
            image_path="garbage_20260607-130000.jpg"
        )
        record = ComplaintRecord.from_payload(payload, evidence_url="https://example.com/img.jpg")

        assert record.location == "Market Square, Jalna"
        assert record.severity == "High"  # 55% -> High
        assert record.garbage_pct == 55.0
        assert record.duration_seconds == 400
        assert record.evidence_url == "https://example.com/img.jpg"

    def test_from_payload_severity_mapping(self):
        """Verify from_payload correctly maps severity for different percentages."""
        # Low
        p = ComplaintPayload(location="A", timestamp="t", garbage_percentage=10,
                             detected_time=60, image_path="x.jpg")
        assert ComplaintRecord.from_payload(p).severity == "Low"

        # Medium
        p = ComplaintPayload(location="A", timestamp="t", garbage_percentage=25,
                             detected_time=60, image_path="x.jpg")
        assert ComplaintRecord.from_payload(p).severity == "Medium"

        # High
        p = ComplaintPayload(location="A", timestamp="t", garbage_percentage=50,
                             detected_time=60, image_path="x.jpg")
        assert ComplaintRecord.from_payload(p).severity == "High"

        # Critical
        p = ComplaintPayload(location="A", timestamp="t", garbage_percentage=75,
                             detected_time=60, image_path="x.jpg")
        assert ComplaintRecord.from_payload(p).severity == "Critical"

    def test_from_payload_default_evidence_url(self):
        """evidence_url defaults to empty string."""
        p = ComplaintPayload(location="A", timestamp="t", garbage_percentage=30,
                             detected_time=60, image_path="x.jpg")
        record = ComplaintRecord.from_payload(p)
        assert record.evidence_url == ""

    def test_duration_seconds_is_int(self):
        """detected_time (float) should be cast to int for duration_seconds."""
        p = ComplaintPayload(location="A", timestamp="t", garbage_percentage=30,
                             detected_time=305.7, image_path="x.jpg")
        record = ComplaintRecord.from_payload(p)
        assert record.duration_seconds == 305
        assert isinstance(record.duration_seconds, int)
