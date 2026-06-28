# ====================================================================================================
# memory_library.py – Memory Library for CrownStar‑Absolute
# Implements the book metaphor for organising memories:
#   - MemoryBook: a single memory (title, pages, metadata)
#   - MemoryShelf: collection of books (with ordering)
#   - MemorySection: major division containing shelves
#   - MemoryCatalog: search index (title, author, subject, emotion, date)
# ====================================================================================================

import time
import uuid
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger("CrownStar.MemoryLibrary")

# --------------------------------------------------------------------
# 1. MemoryBook (Individual memory as a book)
# --------------------------------------------------------------------
@dataclass
class MemoryPage:
    """A single page within a memory book."""
    page_number: int
    title: str
    content: str
    footnote: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryBook:
    """
    A single memory represented as a book.
    Contains pages, metadata, reading history.
    """
    book_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    author: str = ""
    description: str = ""
    publication_date: float = field(default_factory=time.time)
    pages: List[MemoryPage] = field(default_factory=list)
    
    # Classification
    section: str = ""      # e.g., "Early Life", "Career", "Relationships"
    shelf: str = ""        # e.g., "Family", "Work Projects"
    subjects: List[str] = field(default_factory=list)  # tags/categories
    dewey_code: str = ""   # optional classification
    
    # Reading metadata
    times_read: int = 0
    last_read: float = 0.0
    is_favorite: bool = False
    importance: float = 0.5   # 0.0 to 1.0
    
    # Associated memory ID (if this book wraps a memory)
    memory_id: Optional[str] = None
    
    def add_page(self, page: MemoryPage):
        """Add a page to the book (auto‑numbers if needed)."""
        if page.page_number <= 0:
            page.page_number = len(self.pages) + 1
        self.pages.append(page)
    
    def get_page(self, page_number: int) -> Optional[MemoryPage]:
        """Retrieve a page by number."""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None
    
    def mark_read(self):
        """Record that this book has been read/accessed."""
        self.times_read += 1
        self.last_read = time.time()
    
    def get_summary(self) -> str:
        """Return a short summary of the book."""
        return f"{self.title} by {self.author} – {len(self.pages)} pages, {self.times_read} reads"
    
    def to_dict(self) -> Dict:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "publication_date": self.publication_date,
            "pages": [{"page_number": p.page_number, "title": p.title, "content": p.content[:200],
                      "footnote": p.footnote, "metadata": p.metadata} for p in self.pages],
            "section": self.section,
            "shelf": self.shelf,
            "subjects": self.subjects,
            "dewey_code": self.dewey_code,
            "times_read": self.times_read,
            "last_read": self.last_read,
            "is_favorite": self.is_favorite,
            "importance": self.importance,
            "memory_id": self.memory_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryBook':
        pages = [MemoryPage(**p) for p in data.get("pages", [])]
        return cls(
            book_id=data.get("book_id", str(uuid.uuid4())),
            title=data.get("title", ""),
            author=data.get("author", ""),
            description=data.get("description", ""),
            publication_date=data.get("publication_date", time.time()),
            pages=pages,
            section=data.get("section", ""),
            shelf=data.get("shelf", ""),
            subjects=data.get("subjects", []),
            dewey_code=data.get("dewey_code", ""),
            times_read=data.get("times_read", 0),
            last_read=data.get("last_read", 0.0),
            is_favorite=data.get("is_favorite", False),
            importance=data.get("importance", 0.5),
            memory_id=data.get("memory_id")
        )
    
    @classmethod
    def from_memory(cls, memory_id: str, title: str, content: str, author: str = "EverOne") -> 'MemoryBook':
        """Create a MemoryBook from a simple memory entry."""
        pages = [
            MemoryPage(page_number=1, title="Memory", content=content[:500])
        ]
        return cls(
            title=title[:100],
            author=author,
            description=content[:200],
            pages=pages,
            memory_id=memory_id,
            importance=0.6
        )

# --------------------------------------------------------------------
# 2. MemoryShelf (Collection of books on a shelf)
# --------------------------------------------------------------------
@dataclass
class MemoryShelf:
    """
    A shelf in the library, containing books (memories) of a similar theme.
    Books are ordered by position (0 = leftmost).
    """
    shelf_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    books: List[MemoryBook] = field(default_factory=list)
    max_capacity: int = 100
    order: List[str] = field(default_factory=list)  # list of book_ids in order
    
    def add_book(self, book: MemoryBook, position: Optional[int] = None) -> bool:
        """Add a book to this shelf, optionally at a specific position."""
        if len(self.books) >= self.max_capacity:
            logger.warning(f"Shelf '{self.name}' is full (max {self.max_capacity})")
            return False
        if book.book_id in [b.book_id for b in self.books]:
            logger.warning(f"Book {book.book_id} already on shelf '{self.name}'")
            return False
        if position is None:
            self.books.append(book)
            self.order.append(book.book_id)
        else:
            self.books.insert(position, book)
            self.order.insert(position, book.book_id)
        return True
    
    def remove_book(self, book_id: str) -> bool:
        """Remove a book from the shelf by ID."""
        for i, book in enumerate(self.books):
            if book.book_id == book_id:
                self.books.pop(i)
                if book_id in self.order:
                    self.order.remove(book_id)
                return True
        return False
    
    def get_books_ordered(self) -> List[MemoryBook]:
        """Return books in their stored order."""
        ordered = []
        for bid in self.order:
            for book in self.books:
                if book.book_id == bid:
                    ordered.append(book)
                    break
        return ordered
    
    def get_books_by_importance(self, descending: bool = True) -> List[MemoryBook]:
        """Return books sorted by importance."""
        sorted_books = sorted(self.books, key=lambda b: b.importance, reverse=descending)
        return sorted_books
    
    def to_dict(self) -> Dict:
        return {
            "shelf_id": self.shelf_id,
            "name": self.name,
            "description": self.description,
            "max_capacity": self.max_capacity,
            "order": self.order,
            "books": [b.to_dict() for b in self.books]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryShelf':
        books = [MemoryBook.from_dict(b) for b in data.get("books", [])]
        shelf = cls(
            shelf_id=data.get("shelf_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            books=books,
            max_capacity=data.get("max_capacity", 100),
            order=data.get("order", [])
        )
        return shelf

# --------------------------------------------------------------------
# 3. MemorySection (Major division containing shelves)
# --------------------------------------------------------------------
@dataclass
class MemorySection:
    """
    A major section of the library (e.g., "Childhood", "Career", "Relationships").
    Contains multiple shelves.
    """
    section_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    shelves: Dict[str, MemoryShelf] = field(default_factory=dict)  # shelf_name -> MemoryShelf
    icon: str = "📚"   # optional icon/emoji
    
    def add_shelf(self, shelf: MemoryShelf) -> bool:
        """Add a shelf to this section."""
        if shelf.name in self.shelves:
            logger.warning(f"Shelf '{shelf.name}' already exists in section '{self.name}'")
            return False
        self.shelves[shelf.name] = shelf
        return True
    
    def get_shelf(self, name: str) -> Optional[MemoryShelf]:
        """Retrieve a shelf by name."""
        return self.shelves.get(name)
    
    def remove_shelf(self, name: str) -> bool:
        """Remove a shelf from this section."""
        if name in self.shelves:
            del self.shelves[name]
            return True
        return False
    
    def get_all_books(self) -> List[MemoryBook]:
        """Retrieve all books across all shelves in this section."""
        books = []
        for shelf in self.shelves.values():
            books.extend(shelf.books)
        return books
    
    def to_dict(self) -> Dict:
        return {
            "section_id": self.section_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "shelves": {name: shelf.to_dict() for name, shelf in self.shelves.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemorySection':
        shelves = {}
        for name, shelf_data in data.get("shelves", {}).items():
            shelves[name] = MemoryShelf.from_dict(shelf_data)
        return cls(
            section_id=data.get("section_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            shelves=shelves,
            icon=data.get("icon", "📚")
        )

# --------------------------------------------------------------------
# 4. MemoryCatalog (Search index for books)
# --------------------------------------------------------------------
class MemoryCatalog:
    """
    Search index for the library: supports searching by title, author, subject, date, emotion.
    """
    def __init__(self):
        self._books_by_title: Dict[str, List[str]] = defaultdict(list)    # title -> book_ids
        self._books_by_author: Dict[str, List[str]] = defaultdict(list)   # author -> book_ids
        self._books_by_subject: Dict[str, List[str]] = defaultdict(list)  # subject -> book_ids
        self._books_by_date: List[Tuple[float, str]] = []                 # (pub_date, book_id)
        self._books_by_importance: List[Tuple[float, str]] = []           # (importance, book_id)
        self._book_map: Dict[str, MemoryBook] = {}                        # book_id -> book
        self._needs_rebuild = True
    
    def _rebuild(self):
        """Rebuild all indices from the book map."""
        if not self._needs_rebuild:
            return
        self._books_by_title.clear()
        self._books_by_author.clear()
        self._books_by_subject.clear()
        self._books_by_date.clear()
        self._books_by_importance.clear()
        
        for book_id, book in self._book_map.items():
            # Title index
            if book.title:
                self._books_by_title[book.title.lower()].append(book_id)
            # Author index
            if book.author:
                self._books_by_author[book.author.lower()].append(book_id)
            # Subjects index
            for subject in book.subjects:
                self._books_by_subject[subject.lower()].append(book_id)
            # Date index
            self._books_by_date.append((book.publication_date, book_id))
            # Importance index
            self._books_by_importance.append((book.importance, book_id))
        
        # Sort date and importance lists for fast range queries
        self._books_by_date.sort(key=lambda x: x[0])
        self._books_by_importance.sort(key=lambda x: x[0], reverse=True)
        self._needs_rebuild = False
    
    def add_book(self, book: MemoryBook):
        """Add a book to the catalog (or update it)."""
        self._book_map[book.book_id] = book
        self._needs_rebuild = True
    
    def remove_book(self, book_id: str):
        """Remove a book from the catalog."""
        if book_id in self._book_map:
            del self._book_map[book_id]
            self._needs_rebuild = True
    
    def search_by_title(self, title_query: str, exact: bool = False) -> List[MemoryBook]:
        """Search books by title (case‑insensitive partial match unless exact)."""
        self._rebuild()
        query = title_query.lower()
        results = []
        for title, ids in self._books_by_title.items():
            if exact:
                match = title == query
            else:
                match = query in title
            if match:
                for book_id in ids:
                    if book_id in self._book_map:
                        results.append(self._book_map[book_id])
        return results
    
    def search_by_author(self, author_query: str) -> List[MemoryBook]:
        """Search books by author (case‑insensitive partial match)."""
        self._rebuild()
        query = author_query.lower()
        results = []
        for author, ids in self._books_by_author.items():
            if query in author:
                for book_id in ids:
                    if book_id in self._book_map:
                        results.append(self._book_map[book_id])
        return results
    
    def search_by_subject(self, subject: str) -> List[MemoryBook]:
        """Search books by subject (exact match, case‑insensitive)."""
        self._rebuild()
        key = subject.lower()
        ids = self._books_by_subject.get(key, [])
        return [self._book_map[bid] for bid in ids if bid in self._book_map]
    
    def search_by_date_range(self, start: float = 0, end: float = float('inf')) -> List[MemoryBook]:
        """Search books published between start and end timestamps."""
        self._rebuild()
        results = []
        for date, book_id in self._books_by_date:
            if start <= date <= end:
                if book_id in self._book_map:
                    results.append(self._book_map[book_id])
        return results
    
    def get_most_important(self, limit: int = 10) -> List[MemoryBook]:
        """Return the most important books."""
        self._rebuild()
        results = []
        for _, book_id in self._books_by_importance[:limit]:
            if book_id in self._book_map:
                results.append(self._book_map[book_id])
        return results
    
    def get_recent(self, limit: int = 10) -> List[MemoryBook]:
        """Return the most recently published books."""
        self._rebuild()
        results = []
        for date, book_id in reversed(self._books_by_date[-limit:]):
            if book_id in self._book_map:
                results.append(self._book_map[book_id])
        return results

# --------------------------------------------------------------------
# 5. MemoryLibrary (Top‑level orchestrator)
# --------------------------------------------------------------------
class MemoryLibrary:
    """
    The complete memory library: manages sections, shelves, books, and catalog.
    Integrates with XPointer and biomimetic memory.
    """
    
    def __init__(self, name: str = "CrownStar Memory Library"):
        self.name = name
        self.sections: Dict[str, MemorySection] = {}
        self.catalog = MemoryCatalog()
        self._default_section_created = False
        self._create_default_sections()
        logger.info(f"MemoryLibrary '{name}' initialised")
    
    def _create_default_sections(self):
        """Create default sections and shelves for common memory categories."""
        # Section: Core Memories
        core = MemorySection(name="Core Memories", description="Foundational memories and identity")
        # Section: Life Events
        life = MemorySection(name="Life Events", description="Significant life experiences")
        # Section: Knowledge
        knowledge = MemorySection(name="Knowledge", description="Facts, skills, learning")
        # Section: Conversations
        conv = MemorySection(name="Conversations", description="Dialogues with users and others")
        # Section: Reflections
        ref = MemorySection(name="Reflections", description="Self‑reflection and contemplation")
        
        self.add_section(core)
        self.add_section(life)
        self.add_section(knowledge)
        self.add_section(conv)
        self.add_section(ref)
        
        self._default_section_created = True
    
    def add_section(self, section: MemorySection) -> bool:
        """Add a section to the library."""
        if section.name in self.sections:
            logger.warning(f"Section '{section.name}' already exists")
            return False
        self.sections[section.name] = section
        return True
    
    def get_section(self, name: str) -> Optional[MemorySection]:
        """Retrieve a section by name."""
        return self.sections.get(name)
    
    def add_book(self, book: MemoryBook, section_name: str = "Core Memories", shelf_name: str = "General") -> bool:
        """
        Add a book to a specific section and shelf.
        Creates the shelf if it doesn't exist.
        """
        section = self.get_section(section_name)
        if not section:
            section = MemorySection(name=section_name, description=f"Auto‑created section for '{section_name}'")
            self.add_section(section)
        
        shelf = section.get_shelf(shelf_name)
        if not shelf:
            shelf = MemoryShelf(name=shelf_name, description=f"Auto‑created shelf for '{shelf_name}'")
            section.add_shelf(shelf)
        
        success = shelf.add_book(book)
        if success:
            self.catalog.add_book(book)
            logger.debug(f"Book '{book.title}' added to {section_name}/{shelf_name}")
        return success
    
    def get_book(self, book_id: str) -> Optional[MemoryBook]:
        """Find a book by ID across all sections and shelves."""
        for section in self.sections.values():
            for shelf in section.shelves.values():
                for book in shelf.books:
                    if book.book_id == book_id:
                        return book
        return None
    
    def search_books(self, query: str, field: str = "title") -> List[MemoryBook]:
        """Search books by field: 'title', 'author', 'subject'."""
        if field == "title":
            return self.catalog.search_by_title(query)
        elif field == "author":
            return self.catalog.search_by_author(query)
        elif field == "subject":
            return self.catalog.search_by_subject(query)
        else:
            return []
    
    def get_recommendations(self, limit: int = 5, based_on: Optional[str] = None) -> List[MemoryBook]:
        """
        Get book recommendations based on importance, recency, or a specific book.
        Simple implementation: mix of most important and recent.
        """
        important = self.catalog.get_most_important(limit)
        recent = self.catalog.get_recent(limit)
        combined = list({b.book_id: b for b in important + recent}.values())
        return combined[:limit]
    
    def get_statistics(self) -> Dict:
        """Return library statistics."""
        total_books = sum(len(section.get_all_books()) for section in self.sections.values())
        total_shelves = sum(len(section.shelves) for section in self.sections.values())
        return {
            "name": self.name,
            "sections": len(self.sections),
            "shelves": total_shelves,
            "books": total_books,
            "catalog_size": len(self.catalog._book_map)
        }
    
    def to_dict(self) -> Dict:
        """Serialise the entire library to a dictionary."""
        return {
            "name": self.name,
            "sections": {name: section.to_dict() for name, section in self.sections.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryLibrary':
        lib = cls(name=data.get("name", "CrownStar Memory Library"))
        for name, section_data in data.get("sections", {}).items():
            section = MemorySection.from_dict(section_data)
            lib.sections[name] = section
            # Rebuild catalog
            for shelf in section.shelves.values():
                for book in shelf.books:
                    lib.catalog.add_book(book)
        return lib
    
    def save_to_file(self, filepath: str):
        """Save the entire library to a JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"MemoryLibrary saved to {filepath}")
    
    def load_from_file(self, filepath: str):
        """Load the entire library from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        new_lib = self.from_dict(data)
        self.sections = new_lib.sections
        self.catalog = new_lib.catalog
        logger.info(f"MemoryLibrary loaded from {filepath}")

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Create a library
lib = MemoryLibrary("My Memory Library")

# Create a memory book
book = MemoryBook(
    title="First Conversation with CrownStar",
    author="User",
    description="An interesting dialogue about AI.",
    subjects=["conversation", "AI"]
)
book.add_page(MemoryPage(page_number=1, title="Opening", content="Hello, CrownStar!"))
book.add_page(MemoryPage(page_number=2, title="Response", content="I am ready to assist."))

# Add to library
lib.add_book(book, section_name="Conversations", shelf_name="Chats")

# Search
results = lib.search_books("CrownStar", field="title")
for b in results:
    print(b.get_summary())

# Statistics
print(lib.get_statistics())

# Save
lib.save_to_file("memory_library.json")
"""

# ====================================================================================================
# END OF memory_library.py (33,672 characters)
# ====================================================================================================
