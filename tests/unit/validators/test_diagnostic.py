import json

from dev.validators.diagnostic import Diagnostic, ValidationReport, format_diagnostics


class TestDiagnostic:
    """Tests for the shared Diagnostic dataclass."""

    def test_creation(self):
        """Test basic diagnostic creation with all fields."""
        d = Diagnostic(
            file="test.md", line=10, col=5,
            end_line=10, end_col=20,
            severity="error", code="TEST_CODE",
            message="Test message",
        )
        assert d.file == "test.md"
        assert d.line == 10
        assert d.col == 5
        assert d.severity == "error"
        assert d.code == "TEST_CODE"
        assert d.message == "Test message"
        assert d.source == "palimpsest"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        d = Diagnostic(
            file="test.md", line=1, col=0,
            end_line=1, end_col=0,
            severity="warning", code="WARN",
            message="A warning",
        )
        result = d.to_dict()
        assert result["file"] == "test.md"
        assert result["severity"] == "warning"
        assert result["code"] == "WARN"
        assert result["source"] == "palimpsest"

    def test_quickfix_line(self):
        """Test quickfix format output."""
        d = Diagnostic(
            file="entry.md", line=5, col=3,
            end_line=5, end_col=3,
            severity="error", code="ERR",
            message="Bad field",
        )
        assert d.quickfix_line() == "entry.md:5:3: error: Bad field"

    def test_to_dict_roundtrip(self):
        """Test that to_dict output is JSON-serializable."""
        d = Diagnostic(
            file="test.md", line=1, col=0,
            end_line=1, end_col=0,
            severity="info", code="INFO",
            message="Note",
        )
        json_str = json.dumps(d.to_dict())
        parsed = json.loads(json_str)
        assert parsed["severity"] == "info"


class TestValidationReport:
    """Tests for the ValidationReport container."""

    def test_empty_report(self):
        """Test empty report properties."""
        report = ValidationReport()
        assert report.is_valid
        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.errors == []
        assert report.warnings == []

    def test_add_error(self):
        """Test adding an error-level diagnostic."""
        report = ValidationReport(file_path="test.md")
        report.add_error("Missing field", code="MISSING")

        assert report.error_count == 1
        assert not report.is_valid
        assert report.diagnostics[0].severity == "error"
        assert report.diagnostics[0].file == "test.md"

    def test_add_warning(self):
        """Test adding a warning-level diagnostic."""
        report = ValidationReport(file_path="test.md")
        report.add_warning("Deprecated field", code="DEPRECATED")

        assert report.warning_count == 1
        assert report.is_valid  # warnings don't invalidate
        assert report.diagnostics[0].severity == "warning"

    def test_add(self):
        """Test adding a pre-built diagnostic."""
        report = ValidationReport()
        d = Diagnostic(
            file="f.md", line=1, col=0,
            end_line=1, end_col=0,
            severity="error", code="X", message="msg",
        )
        report.add(d)
        assert len(report.diagnostics) == 1
        assert report.diagnostics[0] is d

    def test_merge(self):
        """Test merging two reports."""
        r1 = ValidationReport()
        r1.add_error("Error 1", code="E1")
        r2 = ValidationReport()
        r2.add_warning("Warn 1", code="W1")

        r1.merge(r2)
        assert len(r1.diagnostics) == 2
        assert r1.error_count == 1
        assert r1.warning_count == 1

    def test_quickfix_output(self):
        """Test quickfix output formatting."""
        report = ValidationReport(file_path="test.md")
        report.add_error("Bad", code="E", line=5, col=1)
        report.add_warning("Meh", code="W", line=10, col=0)

        output = report.quickfix_output()
        lines = output.split("\n")
        assert len(lines) == 2
        assert "test.md:5:1: error: Bad" in lines[0]
        assert "test.md:10:0: warning: Meh" in lines[1]

    def test_to_json(self):
        """Test JSON serialization."""
        report = ValidationReport(file_path="test.md")
        report.add_error("Error", code="E")

        parsed = json.loads(report.to_json())
        assert len(parsed) == 1
        assert parsed[0]["severity"] == "error"

    def test_errors_and_warnings_filters(self):
        """Test errors and warnings property filters."""
        report = ValidationReport()
        report.add_error("e1", code="E1")
        report.add_warning("w1", code="W1")
        report.add_error("e2", code="E2")

        assert len(report.errors) == 2
        assert len(report.warnings) == 1
        assert all(d.severity == "error" for d in report.errors)
        assert all(d.severity == "warning" for d in report.warnings)


class TestFormatDiagnostics:
    """Tests for the format_diagnostics function."""

    def test_text_format_with_file_and_line(self):
        """Test text format includes file, line, code, and message."""
        d = Diagnostic(
            file="test.md", line=5, col=3,
            end_line=5, end_col=3,
            severity="error", code="ERR",
            message="Problem",
        )
        output = format_diagnostics([d], "text")
        assert "test.md:5:3" in output
        assert "[ERR]" in output
        assert "Problem" in output

    def test_text_format_without_line(self):
        """Test text format when line is 0."""
        d = Diagnostic(
            file="test.md", line=0, col=0,
            end_line=0, end_col=0,
            severity="warning", code="W",
            message="Note",
        )
        output = format_diagnostics([d], "text")
        assert "test.md:" in output
        assert ":0:" not in output  # no line number shown

    def test_text_format_without_file(self):
        """Test text format when file is empty."""
        d = Diagnostic(
            file="", line=0, col=0,
            end_line=0, end_col=0,
            severity="error", code="DB_ERR",
            message="Schema drift",
        )
        output = format_diagnostics([d], "text")
        assert "[DB_ERR]" in output
        assert "Schema drift" in output

    def test_json_format(self):
        """Test JSON output format."""
        d = Diagnostic(
            file="test.md", line=1, col=0,
            end_line=1, end_col=0,
            severity="error", code="E",
            message="Bad",
        )
        output = format_diagnostics([d], "json")
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["severity"] == "error"
        assert parsed[0]["message"] == "Bad"

    def test_empty_list(self):
        """Test formatting empty diagnostics list."""
        assert format_diagnostics([], "text") == ""
        assert format_diagnostics([], "json") == "[]"
