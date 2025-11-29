#!/usr/bin/env python3
"""
semantic_search.py
------------------
Semantic search using sentence transformers and vector embeddings.

Level 3: Sentence Transformers for semantic similarity

Features:
- Semantic entry search (find similar entries by meaning, not keywords)
- Theme clustering
- Similar entry detection
- Question answering

Uses:
- all-MiniLM-L6-v2: Fast, lightweight model (80MB)
- Cosine similarity for matching
- FAISS for fast vector search (optional)

Usage:
    # Initialize semantic search
    semantic = SemanticSearch()

    # Build index
    semantic.build_index(entries)

    # Find similar entries
    results = semantic.find_similar("I'm feeling anxious about work")

    # Cluster by theme
    clusters = semantic.cluster_entries(entries, num_clusters=5)
"""
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass
import pickle

if TYPE_CHECKING:
    import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    np = None

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None


@dataclass
class SemanticResult:
    """Semantic search result."""

    entry_id: int
    date: str
    similarity: float
    snippet: str = ""


class SemanticSearch:
    """
    Semantic search engine using sentence transformers.

    Intelligence Level: ⭐⭐⭐⭐☆

    Finds semantically similar entries even if they don't share keywords.

    Example:
        Query: "I'm feeling anxious about my relationship"
        Matches:
        - Entry about "worry about connection with partner"
        - Entry about "stress in my friendship"
        - Entry about "nervous about family dynamics"

        (Note: No shared keywords, but similar meaning!)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", use_faiss: bool = True):
        """
        Initialize semantic search.

        Args:
            model_name: Sentence transformer model
                - all-MiniLM-L6-v2: Fast, lightweight (80MB)
                - all-mpnet-base-v2: More accurate, slower (420MB)
            use_faiss: Use FAISS for fast similarity search

        Raises:
            ImportError: If sentence-transformers not installed
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "Sentence transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        self.model = SentenceTransformer(model_name)
        self.use_faiss = use_faiss and FAISS_AVAILABLE

        # Index storage
        self.embeddings: Optional["np.ndarray"] = None
        self.entry_ids: List[int] = []
        self.entry_dates: List[str] = []
        self.entry_texts: List[str] = []

        # FAISS index (if available)
        self.faiss_index = None

    def build_index(self, entries: List[Any], cache_path: Optional[Path] = None):
        """
        Build semantic search index from entries.

        Args:
            entries: List of Entry database objects
            cache_path: Optional path to cache embeddings

        This can be slow for large collections. Consider caching!
        """
        # Try to load from cache
        if cache_path and cache_path.exists():
            self._load_cache(cache_path)
            return

        # Extract texts and metadata
        texts = []
        entry_ids = []
        entry_dates = []

        for entry in entries:
            # Read entry text
            text = self._extract_entry_text(entry)
            if not text:
                continue

            texts.append(text)
            entry_ids.append(entry.id)
            entry_dates.append(entry.date.isoformat())

        # Encode all texts
        print(f"Encoding {len(texts)} entries...")
        embeddings = self.model.encode(
            texts, show_progress_bar=True, convert_to_numpy=True
        )

        # Store
        self.embeddings = embeddings
        self.entry_ids = entry_ids
        self.entry_dates = entry_dates
        self.entry_texts = texts

        # Build FAISS index if available
        if self.use_faiss:
            self._build_faiss_index()

        # Save cache if requested
        if cache_path:
            self._save_cache(cache_path)

    def find_similar(
        self, query: str, limit: int = 10, min_similarity: float = 0.3
    ) -> List[SemanticResult]:
        """
        Find semantically similar entries.

        Args:
            query: Search query (natural language)
            limit: Maximum results
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of SemanticResult ordered by similarity
        """
        if self.embeddings is None:
            raise ValueError("Index not built. Call build_index() first.")

        # Encode query
        query_embedding = self.model.encode(query, convert_to_numpy=True)

        # Find similar entries
        if self.use_faiss and self.faiss_index:
            # FAISS search (fast)
            results = self._search_faiss(query_embedding, limit)
        else:
            # Numpy search (slower)
            results = self._search_numpy(query_embedding, limit)

        # Filter by minimum similarity
        results = [r for r in results if r.similarity >= min_similarity]

        return results

    def find_similar_to_entry(
        self, entry_id: int, limit: int = 10
    ) -> List[SemanticResult]:
        """
        Find entries similar to a specific entry.

        Args:
            entry_id: Entry ID to find similar entries for
            limit: Maximum results

        Returns:
            List of SemanticResult
        """
        if self.embeddings is None:
            raise ValueError("Index not built. Call build_index() first.")

        # Find entry embedding
        try:
            idx = self.entry_ids.index(entry_id)
        except ValueError:
            raise ValueError(f"Entry {entry_id} not in index")

        query_embedding = self.embeddings[idx]

        # Find similar
        if self.use_faiss and self.faiss_index:
            results = self._search_faiss(query_embedding, limit + 1)
        else:
            results = self._search_numpy(query_embedding, limit + 1)

        # Remove self
        results = [r for r in results if r.entry_id != entry_id]

        return results[:limit]

    def cluster_entries(self, num_clusters: int = 10) -> Dict[int, List[int]]:
        """
        Cluster entries by semantic similarity.

        Args:
            num_clusters: Number of clusters

        Returns:
            Dict mapping cluster_id -> list of entry_ids
        """
        if self.embeddings is None:
            raise ValueError("Index not built. Call build_index() first.")

        from sklearn.cluster import KMeans

        # Perform clustering
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        labels = kmeans.fit_predict(self.embeddings)

        # Group by cluster
        clusters = {}
        for i, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(self.entry_ids[i])

        return clusters

    def _extract_entry_text(self, entry) -> str:
        """Extract text content from entry."""
        text_parts = []

        # Read body from file
        if entry.file_path:
            file_path = Path(entry.file_path)
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")

                    # Extract body (skip YAML frontmatter)
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            text_parts.append(parts[2].strip())
                        else:
                            text_parts.append(content)
                    else:
                        text_parts.append(content)
                except Exception:
                    pass

        # Add epigraph and notes
        if entry.epigraph:
            text_parts.append(entry.epigraph)

        if entry.notes:
            text_parts.append(entry.notes)

        return "\n\n".join(text_parts)

    def _search_numpy(
        self, query_embedding: "np.ndarray", limit: int
    ) -> List[SemanticResult]:
        """Search using numpy (slower but always available)."""
        # Compute cosine similarity
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top k
        top_indices = np.argsort(similarities)[::-1][:limit]

        results = []
        for idx in top_indices:
            idx = int(idx)
            results.append(
                SemanticResult(
                    entry_id=self.entry_ids[idx],
                    date=self.entry_dates[idx],
                    similarity=float(similarities[idx]),
                    snippet=self._get_snippet(self.entry_texts[idx]),
                )
            )

        return results

    def _search_faiss(
        self, query_embedding: "np.ndarray", limit: int
    ) -> List[SemanticResult]:
        """Search using FAISS (faster)."""
        # Ensure 2D array
        query_embedding = query_embedding.reshape(1, -1)

        # Search
        distances, indices = self.faiss_index.search(query_embedding, limit)

        results = []
        for i, idx in enumerate(indices[0]):
            idx = int(idx)
            # FAISS returns L2 distance, convert to cosine similarity
            # similarity = 1 - (distance / 2)
            similarity = 1 - (distances[0][i] / 2)

            results.append(
                SemanticResult(
                    entry_id=self.entry_ids[idx],
                    date=self.entry_dates[idx],
                    similarity=float(similarity),
                    snippet=self._get_snippet(self.entry_texts[idx]),
                )
            )

        return results

    def _build_faiss_index(self):
        """Build FAISS index for fast search."""
        if not FAISS_AVAILABLE:
            return

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(self.embeddings)

        # Create index
        dimension = self.embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatIP(dimension)  # Inner product (cosine)

        # Add embeddings
        self.faiss_index.add(self.embeddings)

    def _get_snippet(self, text: str, max_length: int = 100) -> str:
        """Extract snippet from text."""
        text = text.replace("\n", " ").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _save_cache(self, cache_path: Path):
        """Save embeddings to cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "embeddings": self.embeddings,
            "entry_ids": self.entry_ids,
            "entry_dates": self.entry_dates,
            "entry_texts": self.entry_texts,
        }

        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f)

    def _load_cache(self, cache_path: Path):
        """Load embeddings from cache."""
        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)

        self.embeddings = cache_data["embeddings"]
        self.entry_ids = cache_data["entry_ids"]
        self.entry_dates = cache_data["entry_dates"]
        self.entry_texts = cache_data["entry_texts"]

        # Rebuild FAISS index
        if self.use_faiss:
            self._build_faiss_index()


def check_dependencies() -> Dict[str, bool]:
    """Check semantic search dependencies."""
    return {
        "sentence_transformers": TRANSFORMERS_AVAILABLE,
        "faiss": FAISS_AVAILABLE,
    }


if __name__ == "__main__":
    deps = check_dependencies()

    print("Semantic Search Dependencies:")
    print(f"  Sentence Transformers: {'✓' if deps['sentence_transformers'] else '✗'}")
    print(f"  FAISS (optional):      {'✓' if deps['faiss'] else '✗'}")

    if not deps["sentence_transformers"]:
        print("\nInstall with: pip install sentence-transformers")

    if not deps["faiss"]:
        print("Install FAISS (optional) with: pip install faiss-cpu")
