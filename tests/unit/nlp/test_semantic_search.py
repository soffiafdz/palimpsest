import pytest
from unittest.mock import MagicMock, patch
from datetime import date

# We need to mock numpy and sentence_transformers BEFORE importing the module
# if they are not installed, to ensure we can test the 'success' paths.
# However, the module uses a try-import block.

from dev.nlp.semantic_search import SemanticSearch

class TestSemanticSearch:

    @pytest.fixture
    def mock_model(self):
        """Mock SentenceTransformer model."""
        model = MagicMock()
        # Mock encode to return a numpy-like array (list of lists for simplicity in mocks)
        # But the code expects numpy array for dot product.
        # We'll mock the numpy operations too.
        return model

    @pytest.fixture
    def mock_entries(self):
        e1 = MagicMock()
        e1.id = 1
        e1.date = date(2024, 1, 1)
        e1.file_path = "entry1.md"
        e1.epigraph = None
        e1.notes = None
        
        e2 = MagicMock()
        e2.id = 2
        e2.date = date(2024, 1, 2)
        e2.file_path = "entry2.md"
        e2.epigraph = "Quote"
        e2.notes = "Note"
        
        return [e1, e2]

    @patch("dev.nlp.semantic_search.TRANSFORMERS_AVAILABLE", False)
    def test_init_raises_import_error_if_missing_deps(self):
        with pytest.raises(ImportError, match="Sentence transformers not installed"):
            SemanticSearch()

    @patch("dev.nlp.semantic_search.TRANSFORMERS_AVAILABLE", True)
    @patch("dev.nlp.semantic_search.SentenceTransformer")
    def test_init_success(self, mock_transformer_cls):
        search = SemanticSearch()
        assert search.model is not None
        mock_transformer_cls.assert_called_with("all-MiniLM-L6-v2")

    @patch("dev.nlp.semantic_search.TRANSFORMERS_AVAILABLE", True)
    @patch("dev.nlp.semantic_search.SentenceTransformer")
    @patch("dev.nlp.semantic_search.np")
    @patch("dev.nlp.semantic_search.pickle")
    def test_build_index(self, mock_pickle, mock_np, mock_transformer_cls, mock_entries, tmp_path):
        # Setup
        search = SemanticSearch()
        mock_model = mock_transformer_cls.return_value
        
        # Mock embedding return
        mock_embeddings = MagicMock()
        mock_model.encode.return_value = mock_embeddings
        
        # Mock extraction (file read)
        with patch("pathlib.Path.read_text", side_effect=["Entry 1 content", "Entry 2 content"]):
            with patch("pathlib.Path.exists", return_value=True):
                search.build_index(mock_entries)

        assert search.embeddings == mock_embeddings
        assert len(search.entry_ids) == 2
        assert search.entry_texts == ["Entry 1 content", "Entry 2 content\n\nQuote\n\nNote"]
        
        # Test caching
        cache_path = tmp_path / "cache.pkl"
        search.build_index(mock_entries, cache_path=cache_path)
        # Verify pickle.dump was called
        assert mock_pickle.dump.called

    @patch("dev.nlp.semantic_search.TRANSFORMERS_AVAILABLE", True)
    @patch("dev.nlp.semantic_search.SentenceTransformer")
    @patch("dev.nlp.semantic_search.np")
    def test_find_similar_numpy(self, mock_np, mock_transformer_cls, mock_entries):
        search = SemanticSearch()
        search.embeddings = MagicMock()
        search.entry_ids = [1, 2]
        search.entry_dates = ["2024-01-01", "2024-01-02"]
        search.entry_texts = ["Text 1", "Text 2"]
        search.use_faiss = False # Force numpy search

        # Mock numpy operations
        # similarities = dot / (norm * norm)
        # We need dot / float -> similarities_list
        mock_dot_result = MagicMock()
        mock_dot_result.__truediv__.return_value = [0.8, 0.2] # The final similarity scores
        
        mock_np.dot.return_value = mock_dot_result
        mock_np.linalg.norm.return_value = 1.0
        mock_np.argsort.return_value = [0, 1] # Indices sorted (0 is 0.8, 1 is 0.2)

        results = search.find_similar("query")

        assert len(results) == 1 # Only one above default threshold 0.3
        assert results[0].entry_id == 1
        assert results[0].similarity == 0.8

    @patch("dev.nlp.semantic_search.TRANSFORMERS_AVAILABLE", True)
    @patch("dev.nlp.semantic_search.SentenceTransformer")
    def test_find_similar_no_index_raises(self, mock_transformer_cls):
        search = SemanticSearch()
        with pytest.raises(ValueError, match="Index not built"):
            search.find_similar("query")

    @patch("dev.nlp.semantic_search.TRANSFORMERS_AVAILABLE", True)
    @patch("dev.nlp.semantic_search.SentenceTransformer")
    @patch("dev.nlp.semantic_search.np")
    def test_extract_entry_text(self, mock_np, mock_transformer_cls):
        search = SemanticSearch()
        entry = MagicMock()
        entry.file_path = "test.md"
        entry.epigraph = "Epigraph"
        entry.notes = None

        # Test frontmatter stripping
        content = "---\nkey: value\n---\nActual Content"
        with patch("pathlib.Path.read_text", return_value=content):
            with patch("pathlib.Path.exists", return_value=True):
                text = search._extract_entry_text(entry)
        
        assert "Actual Content" in text
        assert "Epigraph" in text
        assert "key: value" not in text
