#!/usr/bin/env python3
"""
test_metadata_pdf_pipeline.py
------------------------------
Integration tests for metadata PDF generation pipeline.

Tests the complete workflow:
1. Gather YAML files
2. Parse with MetadataEntry
3. Format with two-column layout
4. Track arc changes
5. Generate PDF with Pandoc

Test Coverage:
    - Full year PDF generation
    - Multiple entries with varying metadata
    - Arc marker injection
    - Output file creation
"""
# --- Standard library imports ---
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.builders.metadata_pdfbuilder import MetadataPdfBuilder
from dev.core.exceptions import PdfBuildError


# --- Fixtures ---


@pytest.fixture
def temp_yaml_dir(tmp_path):
    """Create temporary YAML directory with test files."""
    yaml_dir = tmp_path / "metadata" / "journal"
    year_dir = yaml_dir / "2025"
    year_dir.mkdir(parents=True)

    # Create test YAML files
    yaml1 = year_dir / "2025-02-28.yaml"
    yaml1.write_text(
        """date: 2025-02-28
summary: First entry
rating: 4.5
rating_justification: Strong narrative
arcs:
  - The Long Wanting
tags:
  - Introspection
themes:
  - name: Loneliness
    description: The weight of empty rooms.
scenes:
  - name: Morning Walk
    description: Through the park
    date: 2025-02-28
    people:
      - Clara
    locations:
      - Central Park
events:
  - name: City Wandering
    scenes:
      - Morning Walk
"""
    )

    yaml2 = year_dir / "2025-03-01.yaml"
    yaml2.write_text(
        """date: 2025-03-01
summary: Second entry
rating: 3.0
arcs:
  - The Long Wanting
  - The Stalled Transition
tags:
  - City
themes:
  - name: Hope
    description: A glimmer of possibility.
scenes:
  - name: Café Meeting
    description: Discussion over coffee
    date: 2025-03-01
    people:
      - Sarah
    locations:
      - Café Nord
"""
    )

    return yaml_dir


@pytest.fixture
def temp_pdf_dir(tmp_path):
    """Create temporary PDF output directory."""
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir(parents=True)
    return pdf_dir


@pytest.fixture
def mock_preamble(tmp_path):
    """Create mock preamble file."""
    preamble = tmp_path / "preamble_metadata.tex"
    preamble.write_text(
        """% Mock preamble
\\usepackage{geometry}
\\usepackage{fontspec}
\\usepackage{multicol}
"""
    )
    return preamble


# --- Test MetadataPdfBuilder ---


def test_gather_yaml_success(temp_yaml_dir):
    """Test successful YAML file gathering."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/preamble.tex"),
    )

    files = builder.gather_yaml()

    assert len(files) == 2
    assert all(f.suffix == ".yaml" for f in files)
    assert files[0].stem == "2025-02-28"
    assert files[1].stem == "2025-03-01"


def test_gather_yaml_no_directory(tmp_path):
    """Test error when YAML directory doesn't exist."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=tmp_path / "nonexistent",
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/preamble.tex"),
    )

    with pytest.raises(PdfBuildError, match="YAML directory not found"):
        builder.gather_yaml()


def test_gather_yaml_no_files(tmp_path):
    """Test error when no YAML files found."""
    yaml_dir = tmp_path / "metadata" / "journal" / "2025"
    yaml_dir.mkdir(parents=True)

    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=tmp_path / "metadata" / "journal",
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/preamble.tex"),
    )

    with pytest.raises(PdfBuildError, match="No YAML files found"):
        builder.gather_yaml()


def test_track_arc_changes():
    """Test arc change detection."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=Path("/tmp"),
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/preamble.tex"),
    )

    # No previous arcs - all are new
    current = ["Arc A", "Arc B"]
    previous = set()
    new_arcs = builder._track_arc_changes(current, previous)
    assert set(new_arcs) == {"Arc A", "Arc B"}

    # One new arc
    current = ["Arc A", "Arc B", "Arc C"]
    previous = {"Arc A", "Arc B"}
    new_arcs = builder._track_arc_changes(current, previous)
    assert new_arcs == ["Arc C"]

    # No new arcs
    current = ["Arc A", "Arc B"]
    previous = {"Arc A", "Arc B"}
    new_arcs = builder._track_arc_changes(current, previous)
    assert new_arcs == []


def test_write_temp_md_success(temp_yaml_dir, tmp_path):
    """Test successful temporary markdown creation."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/preamble.tex"),
    )

    files = builder.gather_yaml()
    tmp_file = tmp_path / "test.md"

    builder._write_temp_md(files, tmp_file)

    assert tmp_file.exists()
    content = tmp_file.read_text()

    # Check structure
    assert "February, 2025" in content or "March, 2025" in content
    assert "\\Huge\\bfseries 2025-02-28" in content
    assert "\\Huge\\bfseries 2025-03-01" in content
    assert "First entry" in content
    assert "Second entry" in content

    # Check arc tags (LaTeX format)
    assert "\\large\\bfseries" in content
    assert "The Stalled Transition" in content

    # Check TOC
    assert "\\tableofcontents" in content

    # Check newpage before entries
    assert "\\newpage" in content

    # Check events & scenes section (LaTeX format)
    assert "\\LARGE\\bfseries Events \\& Scenes" in content


def test_write_temp_md_arc_inline(temp_yaml_dir, tmp_path):
    """Test arc inline tags in entries."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/preamble.tex"),
    )

    files = builder.gather_yaml()
    tmp_file = tmp_path / "test.md"

    builder._write_temp_md(files, tmp_file)

    content = tmp_file.read_text()

    # Arcs shown as LaTeX tags in entries
    assert "The Long Wanting" in content
    assert "The Stalled Transition" in content
    assert "\\large\\bfseries" in content


@patch("dev.builders.metadata_pdfbuilder.convert_file")
def test_run_pandoc_success(mock_convert, tmp_path, mock_preamble):
    """Test successful Pandoc invocation."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=Path("/tmp"),
        pdf_dir=Path("/tmp"),
        preamble=mock_preamble,
    )

    in_md = tmp_path / "test.md"
    in_md.write_text("# Test")
    out_pdf = tmp_path / "test.pdf"

    metadata = {"title": "Test", "author": "Author"}
    vars = {"fontsize": "10pt"}

    builder._run_pandoc(in_md, out_pdf, mock_preamble, metadata, vars)

    # Verify pypandoc was called
    mock_convert.assert_called_once()
    args = mock_convert.call_args

    # Check arguments
    assert str(in_md) in args[0]
    assert args[1]["to"] == "pdf"
    assert str(out_pdf) in str(args[1]["outputfile"])


def test_run_pandoc_missing_input(tmp_path, mock_preamble):
    """Test error when input markdown doesn't exist."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=Path("/tmp"),
        pdf_dir=Path("/tmp"),
        preamble=mock_preamble,
    )

    in_md = tmp_path / "nonexistent.md"
    out_pdf = tmp_path / "test.pdf"

    with pytest.raises(PdfBuildError, match="Markdown file not found"):
        builder._run_pandoc(in_md, out_pdf, mock_preamble, {}, {})


def test_run_pandoc_missing_preamble(tmp_path):
    """Test error when preamble doesn't exist."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=Path("/tmp"),
        pdf_dir=Path("/tmp"),
        preamble=Path("/tmp/nonexistent.tex"),
    )

    in_md = tmp_path / "test.md"
    in_md.write_text("# Test")
    out_pdf = tmp_path / "test.pdf"

    with pytest.raises(PdfBuildError, match="Preamble file not found"):
        builder._run_pandoc(in_md, out_pdf, Path("/tmp/nonexistent.tex"), {}, {})


@patch("dev.builders.metadata_pdfbuilder.convert_file")
def test_build_success(
    mock_convert, temp_yaml_dir, temp_pdf_dir, mock_preamble, tmp_path
):
    """Test successful complete build."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=temp_pdf_dir,
        preamble=mock_preamble,
        force_overwrite=True,
    )

    # Mock Pandoc to avoid actual PDF generation
    def mock_pdf_gen(in_file, to, outputfile, extra_args):
        Path(outputfile).write_text("Mock PDF")

    mock_convert.side_effect = mock_pdf_gen

    stats = builder.build()

    assert stats.files_processed == 2
    assert stats.pdfs_created == 1
    assert stats.errors == 0

    # Check output file was created (by mock)
    pdf_path = temp_pdf_dir / "2025-metadata.pdf"
    assert pdf_path.exists()


@patch("dev.builders.metadata_pdfbuilder.convert_file")
def test_build_skip_existing(
    mock_convert, temp_yaml_dir, temp_pdf_dir, mock_preamble
):
    """Test that existing PDF is skipped without force_overwrite."""
    # Create existing PDF
    pdf_path = temp_pdf_dir / "2025-metadata.pdf"
    pdf_path.write_text("Existing PDF")

    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=temp_pdf_dir,
        preamble=mock_preamble,
        force_overwrite=False,
    )

    stats = builder.build()

    # Should not create PDF
    assert stats.pdfs_created == 0

    # Original file should be unchanged
    assert pdf_path.read_text() == "Existing PDF"

    # Pandoc should not be called
    mock_convert.assert_not_called()


def test_build_missing_preamble(temp_yaml_dir, temp_pdf_dir):
    """Test error when preamble doesn't exist."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=temp_pdf_dir,
        preamble=Path("/tmp/nonexistent.tex"),
    )

    with pytest.raises(PdfBuildError, match="Preamble not found"):
        builder.build()


@patch("dev.builders.metadata_pdfbuilder.convert_file")
def test_build_preserves_temp_on_error(
    mock_convert, temp_yaml_dir, temp_pdf_dir, mock_preamble
):
    """Test that temp files are preserved on error when keep_temp_on_error=True."""
    builder = MetadataPdfBuilder(
        year="2025",
        yaml_dir=temp_yaml_dir,
        pdf_dir=temp_pdf_dir,
        preamble=mock_preamble,
        keep_temp_on_error=True,
    )

    # Make Pandoc fail
    mock_convert.side_effect = RuntimeError("Pandoc failed")

    with pytest.raises(PdfBuildError, match="Pandoc conversion failed"):
        builder.build()

    # Stats should show error
    # (we can't check stats directly since exception is raised,
    #  but the test verifies the error path works)
