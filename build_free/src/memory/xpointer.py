# ====================================================================================================
# xpointer.py – XPointer Resolver for CrownStar‑Absolute Biomimetic Memory
# Implements XPointer Framework (W3C) subset:
#   - xpointer(id("...")) – resolve by ID
#   - element(/1/2/3) – resolve by path in XML tree
# Caches resolved results for performance.
# ====================================================================================================

import re
import xml.etree.ElementTree as ET
from typing import Optional, Union, Dict, Any, Tuple
from collections import OrderedDict
import logging
from pathlib import Path

logger = logging.getLogger("CrownStar.XPointer")

# --------------------------------------------------------------------
# XPointer Syntax Patterns
# --------------------------------------------------------------------
ID_PATTERN = re.compile(r'^xpointer\(id\("([^"]+)"\)\)$')
ELEMENT_PATTERN = re.compile(r'^element\((/[\d/]*)\)$')
SIMPLE_PATTERN = re.compile(r'^#([a-zA-Z][a-zA-Z0-9_-]*)$')  # simple fragment identifier

# --------------------------------------------------------------------
# XPointer Resolver Class
# --------------------------------------------------------------------
class XPointerResolver:
    """
    Resolves XPointer expressions to memory fragments or XML nodes.
    
    Usage:
        resolver = XPointerResolver(memory_xml_path)
        node = resolver.resolve('xpointer(id("mem-123"))')
        # or
        node = resolver.resolve('element(/1/2/3)')
    """
    
    def __init__(self, xml_path: Optional[Path] = None, xml_tree: Optional[ET.ElementTree] = None):
        """
        Args:
            xml_path: Path to the memory XML file (optional, can be set later)
            xml_tree: Existing ElementTree (optional)
        """
        self.xml_path = Path(xml_path) if xml_path else None
        self._tree = xml_tree
        self._cache = OrderedDict()
        self._cache_maxsize = 1000
        self._id_to_element: Dict[str, ET.Element] = {}
        self._build_id_index()
        logger.info("XPointerResolver initialised")
    
    def set_xml_path(self, xml_path: Path):
        """Set or update the XML file path and reload the tree."""
        self.xml_path = xml_path
        self._load_tree()
    
    def _load_tree(self):
        """Load the XML tree from the file path."""
        if self.xml_path and self.xml_path.exists():
            try:
                self._tree = ET.parse(self.xml_path)
                self._build_id_index()
                logger.debug(f"Loaded XML tree from {self.xml_path}")
            except ET.ParseError as e:
                logger.error(f"Failed to parse XML: {e}")
                self._tree = None
        else:
            logger.warning(f"XML file not found: {self.xml_path}")
            self._tree = None
    
    def _build_id_index(self):
        """Build an index of elements by their 'id' attribute for fast ID resolution."""
        self._id_to_element.clear()
        if self._tree is None:
            return
        root = self._tree.getroot()
        for elem in root.iter():
            elem_id = elem.get('id')
            if elem_id:
                self._id_to_element[elem_id] = elem
    
    def _cached(self, xpointer: str, resolver_func):
        """Cache wrapper for resolved results."""
        if xpointer in self._cache:
            logger.debug(f"XPointer cache hit: {xpointer}")
            return self._cache[xpointer]
        result = resolver_func(xpointer)
        if len(self._cache) >= self._cache_maxsize:
            self._cache.popitem(last=False)
        self._cache[xpointer] = result
        return result
    
    # --------------------------------------------------------------------
    # Resolution methods
    # --------------------------------------------------------------------
    def resolve(self, xpointer: str) -> Optional[ET.Element]:
        """
        Main entry point: resolve an XPointer expression to an XML element.
        Returns None if resolution fails.
        """
        if self._tree is None:
            self._load_tree()
        if self._tree is None:
            return None
        
        # Try each scheme
        result = self._cached(xpointer, self._resolve_scheme)
        return result
    
    def _resolve_scheme(self, xpointer: str) -> Optional[ET.Element]:
        """Try each XPointer scheme."""
        # Scheme 1: xpointer(id("..."))
        m = ID_PATTERN.match(xpointer)
        if m:
            elem_id = m.group(1)
            return self._id_to_element.get(elem_id)
        
        # Scheme 2: element(/1/2/3)
        m = ELEMENT_PATTERN.match(xpointer)
        if m:
            path = m.group(1)
            return self._resolve_element_path(path)
        
        # Scheme 3: simple fragment #id
        m = SIMPLE_PATTERN.match(xpointer)
        if m:
            elem_id = m.group(1)
            return self._id_to_element.get(elem_id)
        
        logger.debug(f"Unsupported XPointer scheme: {xpointer}")
        return None
    
    def _resolve_element_path(self, path: str) -> Optional[ET.Element]:
        """
        Resolve an element path like '/1/2/3' (1‑based indexing).
        The root is implicitly the document root.
        """
        if not path or path == '/':
            return self._tree.getroot()
        # Remove leading slash and split
        path = path.lstrip('/')
        if not path:
            return self._tree.getroot()
        indices = [int(x) for x in path.split('/')]
        current = self._tree.getroot()
        for idx in indices:
            # 1‑based indexing: child number (idx-1)
            if idx < 1:
                return None
            children = list(current)
            if idx - 1 < len(children):
                current = children[idx - 1]
            else:
                return None
        return current
    
    # --------------------------------------------------------------------
    # XPointer creation helpers
    # --------------------------------------------------------------------
    @staticmethod
    def create_id_pointer(elem_id: str) -> str:
        """Create an xpointer(id(...)) expression."""
        return f'xpointer(id("{elem_id}"))'
    
    @staticmethod
    def create_element_pointer(path: list) -> str:
        """Create an element(/1/2/3) expression from a list of indices (1‑based)."""
        path_str = '/' + '/'.join(str(i) for i in path)
        return f'element({path_str})'
    
    @staticmethod
    def create_simple_pointer(elem_id: str) -> str:
        """Create a simple fragment identifier (#id)."""
        return f'#{elem_id}'
    
    # --------------------------------------------------------------------
    # Batch resolution and utilities
    # --------------------------------------------------------------------
    def resolve_many(self, xpointers: list) -> list:
        """Resolve multiple XPointers, returning list of elements (None for failures)."""
        return [self.resolve(xp) for xp in xpointers]
    
    def resolve_memory_fragment(self, xpointer: str) -> Optional[Dict]:
        """
        Resolve an XPointer to a memory fragment dictionary (convenience for BiomimeticMemory).
        Returns a dict with 'type', 'content', etc.
        """
        elem = self.resolve(xpointer)
        if elem is None:
            return None
        
        # Convert element to a simple dict representation
        result = {
            "type": elem.tag,
            "attributes": dict(elem.attrib),
            "content": elem.text.strip() if elem.text else "",
            "children": [child.tag for child in elem]
        }
        # If it's a memory entry, extract more fields
        if elem.tag == 'memory-entry':
            result["memory_id"] = elem.findtext('id', '')
            result["query"] = elem.findtext('query', '')
            result["response"] = elem.findtext('response', '')
        elif elem.tag == 'experience':
            result["experience_id"] = elem.findtext('id', '')
            result["title"] = elem.findtext('title', '')
            result["narrative"] = elem.findtext('narrative', '')[:200]
        return result
    
    def clear_cache(self):
        """Clear the resolution cache."""
        self._cache.clear()
        logger.debug("XPointer cache cleared")
    
    def refresh(self):
        """Reload the XML file and rebuild the ID index."""
        self._load_tree()
        self.clear_cache()
    
    # --------------------------------------------------------------------
    # Statistics
    # --------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """Return resolver statistics."""
        return {
            "cache_size": len(self._cache),
            "cache_maxsize": self._cache_maxsize,
            "id_index_size": len(self._id_to_element),
            "xml_loaded": self._tree is not None,
            "xml_path": str(self.xml_path) if self.xml_path else None
        }


# --------------------------------------------------------------------
# Standalone functions for quick use (without full class)
# --------------------------------------------------------------------
def quick_resolve(xml_path: Path, xpointer: str) -> Optional[ET.Element]:
    """Quickly resolve an XPointer without creating a persistent resolver."""
    resolver = XPointerResolver(xml_path)
    return resolver.resolve(xpointer)


def quick_resolve_id(xml_path: Path, elem_id: str) -> Optional[ET.Element]:
    """Quickly resolve by ID using the simple fragment scheme."""
    return quick_resolve(xml_path, f'#{elem_id}')


def xpointer_for_memory(memory_id: str) -> str:
    """Convenience function to create an XPointer for a memory by its ID."""
    return XPointerResolver.create_id_pointer(memory_id)


def xpointer_for_experience(exp_id: str) -> str:
    """Convenience function to create an XPointer for an experiential memory."""
    return XPointerResolver.create_id_pointer(exp_id)


# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
if __name__ == "__main__":
    # Create a sample memory XML
    from memory_schemas import create_initial_memory_file
    xml_file = Path("data/memory.xml")
    create_initial_memory_file(xml_file)
    
    # Add a test memory entry (simplified)
    import xml.etree.ElementTree as ET
    tree = ET.parse(xml_file)
    root = tree.getroot()
    idx = root.find("memory-index")
    entry = ET.SubElement(idx, "memory-entry", {"type": "conversation", "tier": "free", "id": "mem-001"})
    ET.SubElement(entry, "id").text = "mem-001"
    ET.SubElement(entry, "timestamp").text = "1234567890"
    ET.SubElement(entry, "query").text = "What is XPointer?"
    ET.SubElement(entry, "response").text = "XPointer is a fragment identifier for XML."
    ET.SubElement(entry, "importance").text = "0.8"
    tree.write(xml_file)
    
    # Resolve
    resolver = XPointerResolver(xml_file)
    elem = resolver.resolve('xpointer(id("mem-001"))')
    if elem is not None:
        print("Found:", elem.findtext("query"))
    print("Stats:", resolver.get_stats())
"""

# ====================================================================================================
# END OF xpointer.py (31,456 characters)
# ====================================================================================================
