import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, call

from dev.builders.pdfbuilder import PdfBuilder, PdfBuildError, BuildStats
from dev.core.temporal_files import TemporalFileManager
from dev.utils.md import split_frontmatter

class TestPdfBuilder:
    """Tests for the PdfBuilder class."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger instance."""
        return MagicMock()

    @pytest.fixture
    def setup_real_paths(self, tmp_path):
        """Setup real directory structure and files for testing."""
        md_base_dir = tmp_path / "journal" / "md"
        pdf_base_dir = tmp_path / "journal" / "pdf"
        preamble_base_dir = tmp_path / "preambles"

        md_year_dir = md_base_dir / "2025"
        md_year_dir.mkdir(parents=True)
        pdf_base_dir.mkdir(parents=True)
        preamble_base_dir.mkdir(parents=True)

        # Use ## headers to ensure notes formatting trigger works
        (md_year_dir / "2025-01-01.md").write_text("---\ntitle: Entry 1\n---\n## Header\nContent 1")
        (md_year_dir / "2025-01-02.md").write_text("---\ntitle: Entry 2\n---\n## Entry 2\nContent 2")
        (md_year_dir / "2025-02-10.md").write_text("---\ntitle: Entry 3\n---\n## Entry 3\nContent 3")

        (preamble_base_dir / "clean.tex").write_text("clean preamble content")
        (preamble_base_dir / "notes.tex").write_text("notes preamble content")

        return {
            "md_dir": md_base_dir,
            "pdf_dir": pdf_base_dir,
            "clean_preamble": preamble_base_dir / "clean.tex",
            "notes_preamble": preamble_base_dir / "notes.tex",
            "md_year_dir": md_year_dir
        }

    def test_init(self, mock_logger, setup_real_paths):
        """Test PdfBuilder initialization."""
        builder = PdfBuilder(
            year="2025",
            md_dir=setup_real_paths["md_dir"],
            pdf_dir=setup_real_paths["pdf_dir"],
            preamble=setup_real_paths["clean_preamble"],
            logger=mock_logger
        )
        assert builder.year == "2025"
        assert builder.md_dir == setup_real_paths["md_dir"]
        assert builder.pdf_dir == setup_real_paths["pdf_dir"]
        assert builder.preamble == setup_real_paths["clean_preamble"]
        assert builder.logger == mock_logger

    def test_build_raises_error_if_no_preamble(self, mock_logger, setup_real_paths):
        """Test build method raises error if no preamble is provided."""
        builder = PdfBuilder(
            year="2025",
            md_dir=setup_real_paths["md_dir"],
            pdf_dir=setup_real_paths["pdf_dir"],
            preamble=None,
            preamble_notes=None,
            logger=mock_logger
        )
        with pytest.raises(PdfBuildError, match="At least one preamble file must be provided"):
            builder.build()

    def test_build_raises_error_if_preamble_not_found(self, mock_logger, setup_real_paths):
        """Test build method raises error if preamble file does not exist."""
        builder = PdfBuilder(
            year="2025",
            md_dir=setup_real_paths["md_dir"],
            pdf_dir=setup_real_paths["pdf_dir"],
            preamble=setup_real_paths["md_dir"] / "non_existent.tex", # Pass a non-existent path
            logger=mock_logger
        )
        with pytest.raises(PdfBuildError, match="Clean preamble not found"):
            builder.build()

    def test_build_raises_error_if_md_dir_not_found(self, mock_logger, setup_real_paths):
        """Test build method raises error if Markdown directory does not exist."""
        builder = PdfBuilder(
            year="2025",
            md_dir=setup_real_paths["md_dir"].parent / "non_existent_md", # Pass non-existent MD dir
            pdf_dir=setup_real_paths["pdf_dir"],
            preamble=setup_real_paths["clean_preamble"],
            logger=mock_logger
        )
        with pytest.raises(PdfBuildError, match="Markdown directory not found"):
            builder.build()

    @patch("dev.builders.pdfbuilder.convert_file")
    @patch.object(TemporalFileManager, "create_temp_file", autospec=True, return_value=Path("/tmp/temp_file_clean.md"))
    @patch.object(TemporalFileManager, "cleanup", autospec=True, return_value={"files_removed": 1})
    @patch("dev.utils.md.split_frontmatter", autospec=True, side_effect=lambda fm, body: ("", body.splitlines()))
    def test_build_clean_pdf_creation(
        self,
        mock_split_frontmatter,
        mock_cleanup,
        mock_create_temp_file,
        mock_convert_file,
        mock_logger,
        setup_real_paths,
        mocker # pytest-mock fixture
    ):
        """Test the creation of a clean PDF."""
        
        # We need a mock for the open call within _write_temp_md to inspect writes, 
        # BUT mocking builtins.open affects file reading too. 
        # Simpler: let it write to a real temp path and check content.
        
        # Create a real temp file path in the temp directory
        real_temp_path = setup_real_paths["pdf_dir"] / "temp_clean.md"
        mock_create_temp_file.return_value = real_temp_path
        
        # Mock convert_file to do nothing (we just check it's called)
        
        builder = PdfBuilder(
            year="2025",
            md_dir=setup_real_paths["md_dir"],
            pdf_dir=setup_real_paths["pdf_dir"],
            preamble=setup_real_paths["clean_preamble"],
            logger=mock_logger,
            force_overwrite=True
        )

        stats = builder.build()

        assert stats.files_processed == 3
        assert stats.pdfs_created == 1
        assert stats.errors == 0
        
        # Verify content written to temporary MD file
        assert real_temp_path.exists()
        content = real_temp_path.read_text()

        assert "January, 2025" in content
        assert "February, 2025" in content
        assert "Content 1" in content
        assert "Content 2" in content
        assert "Content 3" in content
        assert r"\tableofcontents" in content
        
        # Verify convert_file arguments
        args, kwargs = mock_convert_file.call_args
        assert args[0] == str(real_temp_path)
        assert kwargs['outputfile'] == str(setup_real_paths["pdf_dir"] / "2025.pdf")
        assert 'extra_args' in kwargs
        assert '--include-in-header' in kwargs['extra_args']
        assert str(setup_real_paths["clean_preamble"]) in kwargs['extra_args']

        mock_cleanup.assert_called_once()

    @patch("dev.builders.pdfbuilder.convert_file")
    @patch.object(TemporalFileManager, "create_temp_file", autospec=True, return_value=Path("/tmp/temp_file_notes.md"))
    @patch.object(TemporalFileManager, "cleanup", autospec=True, return_value={"files_removed": 1})
    @patch("dev.utils.md.split_frontmatter", autospec=True, side_effect=lambda fm, body: ("", body.splitlines()))
    def test_build_notes_pdf_creation(
        self,
        mock_split_frontmatter,
        mock_cleanup,
        mock_create_temp_file,
        mock_convert_file,
        mock_logger,
        setup_real_paths,
        mocker # pytest-mock fixture
    ):
        """Test the creation of a notes PDF."""
        # Create a real temp file path in the temp directory
        real_temp_path = setup_real_paths["pdf_dir"] / "temp_notes.md"
        mock_create_temp_file.return_value = real_temp_path

        builder = PdfBuilder(
            year="2025",
            md_dir=setup_real_paths["md_dir"],
            pdf_dir=setup_real_paths["pdf_dir"],
            preamble=None,
            preamble_notes=setup_real_paths["notes_preamble"],
            logger=mock_logger,
            force_overwrite=True
        )

        stats = builder.build()

        assert stats.files_processed == 3
        assert stats.pdfs_created == 1
        assert stats.errors == 0
        
        assert real_temp_path.exists()
        content = real_temp_path.read_text()
        
        # Verify notes formatting
        assert r"\nolinenumbers" in content
        assert r"\linenumbers" in content
        assert r"\setcounter{linenumber}{1}" in content
        assert "**Curation**" in content # Annotation template check
        
        args, kwargs = mock_convert_file.call_args
        assert kwargs['outputfile'] == str(setup_real_paths["pdf_dir"] / "2025-notes.pdf")
        assert str(setup_real_paths["notes_preamble"]) in kwargs['extra_args']

        mock_cleanup.assert_called_once()