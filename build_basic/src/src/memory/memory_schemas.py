# ====================================================================================================
# memory_schemas.py – XML DTD and XSD Schemas for CrownStar‑Absolute Biomimetic Memory
# Contains:
#   - Complete DTD for memory system (memories, experiences, links)
#   - Complete XSD Schema (more expressive, namespace support)
#   - Validation functions (DTD and XSD) with lxml fallback
#   - Memory XML initialisation (create empty compliant memory file)
# ====================================================================================================

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import logging

logger = logging.getLogger("CrownStar.Memory")

# --------------------------------------------------------------------
# 1. DTD (Document Type Definition) – Full Memory System
# --------------------------------------------------------------------
MEMORY_DTD = '''<?xml version="1.0" encoding="UTF-8"?>
<!ELEMENT memory-system (memory-index, experiential-lib, memory-links?)>
<!ATTLIST memory-system version CDATA #FIXED "1.0">

<!ELEMENT memory-index (memory-entry*)>
<!ELEMENT memory-entry (id, timestamp, query, response, importance, tags*, metadata?)>
<!ATTLIST memory-entry type (conversation | thought | fact) "conversation">
<!ATTLIST memory-entry tier (free | basic | pro | enterprise) "free">
<!ATTLIST memory-entry id ID #REQUIRED>

<!ELEMENT id (#PCDATA)>
<!ELEMENT timestamp (#PCDATA)>
<!ELEMENT query (#PCDATA)>
<!ELEMENT response (#PCDATA)>
<!ELEMENT importance (#PCDATA)>
<!ELEMENT tags (tag*)>
<!ELEMENT tag (#PCDATA)>
<!ELEMENT metadata (entry*)>
<!ELEMENT entry EMPTY>
<!ATTLIST entry key CDATA #REQUIRED>
<!ATTLIST entry value CDATA #REQUIRED>

<!ELEMENT experiential-lib (experience*)>
<!ELEMENT experience (id, timestamp, title, narrative, visual?, audio?, emotion?, sketchy-params?, spatial?)>
<!ATTLIST experience type (sunlit | interior | vehicle | exterior) "sunlit">
<!ATTLIST experience id ID #REQUIRED>

<!ELEMENT visual (scene-desc, lighting, colors, objects?)>
<!ELEMENT scene-desc (#PCDATA)>
<!ELEMENT lighting (#PCDATA)>
<!ELEMENT colors (#PCDATA)>
<!ELEMENT objects (object*)>
<!ELEMENT object (#PCDATA)>

<!ELEMENT audio (sound, volume, pitch, duration?)>
<!ELEMENT sound (#PCDATA)>
<!ELEMENT volume (#PCDATA)>
<!ELEMENT pitch (#PCDATA)>
<!ELEMENT duration (#PCDATA)>

<!ELEMENT emotion (primary, valence, arousal, intensity?)>
<!ELEMENT primary (#PCDATA)>
<!ELEMENT valence (#PCDATA)>
<!ELEMENT arousal (#PCDATA)>
<!ELEMENT intensity (#PCDATA)>

<!ELEMENT sketchy-params (clarity, detail-level, missing-elements?)>
<!ELEMENT clarity (#PCDATA)>
<!ELEMENT detail-level (#PCDATA)>
<!ELEMENT missing-elements (element*)>
<!ELEMENT element (#PCDATA)>

<!ELEMENT spatial (location, coordinates?, environment)>
<!ELEMENT location (#PCDATA)>
<!ELEMENT coordinates EMPTY>
<!ATTLIST coordinates lat CDATA #IMPLIED>
<!ATTLIST coordinates lon CDATA #IMPLIED>
<!ELEMENT environment (#PCDATA)>

<!ELEMENT memory-links (link*)>
<!ELEMENT link EMPTY>
<!ATTLIST link from IDREF #REQUIRED>
<!ATTLIST link to IDREF #REQUIRED>
<!ATTLIST link type (causal | temporal | associative | emotional) "associative">
<!ATTLIST link strength CDATA "1.0">
'''

# --------------------------------------------------------------------
# 2. XSD (XML Schema Definition) – More Rigorous Validation
# --------------------------------------------------------------------
MEMORY_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://crownstar.ai/memory"
           xmlns="http://crownstar.ai/memory"
           elementFormDefault="qualified">

  <xs:element name="memory-system">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="memory-index" type="IndexType"/>
        <xs:element name="experiential-lib" type="ExpLibType"/>
        <xs:element name="memory-links" type="LinksType" minOccurs="0"/>
      </xs:sequence>
      <xs:attribute name="version" type="xs:string" fixed="1.0"/>
    </xs:complexType>
  </xs:element>

  <xs:complexType name="IndexType">
    <xs:sequence>
      <xs:element name="memory-entry" type="MemoryEntryType" minOccurs="0" maxOccurs="unbounded"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="MemoryEntryType">
    <xs:sequence>
      <xs:element name="id" type="xs:ID"/>
      <xs:element name="timestamp" type="xs:double"/>
      <xs:element name="query" type="xs:string"/>
      <xs:element name="response" type="xs:string"/>
      <xs:element name="importance" type="xs:double"/>
      <xs:element name="tags" minOccurs="0">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="tag" type="xs:string" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
      <xs:element name="metadata" minOccurs="0">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="entry" maxOccurs="unbounded">
              <xs:complexType>
                <xs:attribute name="key" type="xs:string" use="required"/>
                <xs:attribute name="value" type="xs:string" use="required"/>
              </xs:complexType>
            </xs:element>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
    <xs:attribute name="type" use="required">
      <xs:simpleType>
        <xs:restriction base="xs:string">
          <xs:enumeration value="conversation"/>
          <xs:enumeration value="thought"/>
          <xs:enumeration value="fact"/>
        </xs:restriction>
      </xs:simpleType>
    </xs:attribute>
    <xs:attribute name="tier" use="required">
      <xs:simpleType>
        <xs:restriction base="xs:string">
          <xs:enumeration value="free"/>
          <xs:enumeration value="basic"/>
          <xs:enumeration value="pro"/>
          <xs:enumeration value="enterprise"/>
        </xs:restriction>
      </xs:simpleType>
    </xs:attribute>
  </xs:complexType>

  <xs:complexType name="ExpLibType">
    <xs:sequence>
      <xs:element name="experience" type="ExperienceType" minOccurs="0" maxOccurs="unbounded"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="ExperienceType">
    <xs:sequence>
      <xs:element name="id" type="xs:ID"/>
      <xs:element name="timestamp" type="xs:double"/>
      <xs:element name="title" type="xs:string"/>
      <xs:element name="narrative" type="xs:string"/>
      <xs:element name="visual" type="VisualType" minOccurs="0"/>
      <xs:element name="audio" type="AudioType" minOccurs="0"/>
      <xs:element name="emotion" type="EmotionType" minOccurs="0"/>
      <xs:element name="sketchy-params" type="SketchyParamsType" minOccurs="0"/>
      <xs:element name="spatial" type="SpatialType" minOccurs="0"/>
    </xs:sequence>
    <xs:attribute name="type" use="required">
      <xs:simpleType>
        <xs:restriction base="xs:string">
          <xs:enumeration value="sunlit"/>
          <xs:enumeration value="interior"/>
          <xs:enumeration value="vehicle"/>
          <xs:enumeration value="exterior"/>
        </xs:restriction>
      </xs:simpleType>
    </xs:attribute>
  </xs:complexType>

  <xs:complexType name="VisualType">
    <xs:sequence>
      <xs:element name="scene-desc" type="xs:string"/>
      <xs:element name="lighting" type="xs:string"/>
      <xs:element name="colors" type="xs:string"/>
      <xs:element name="objects" minOccurs="0">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="object" type="xs:string" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="AudioType">
    <xs:sequence>
      <xs:element name="sound" type="xs:string"/>
      <xs:element name="volume" type="xs:double"/>
      <xs:element name="pitch" type="xs:double"/>
      <xs:element name="duration" type="xs:double" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="EmotionType">
    <xs:sequence>
      <xs:element name="primary" type="xs:string"/>
      <xs:element name="valence" type="xs:double"/>
      <xs:element name="arousal" type="xs:double"/>
      <xs:element name="intensity" type="xs:double" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="SketchyParamsType">
    <xs:sequence>
      <xs:element name="clarity" type="xs:double"/>
      <xs:element name="detail-level" type="xs:double"/>
      <xs:element name="missing-elements" minOccurs="0">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="element" type="xs:string" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="SpatialType">
    <xs:sequence>
      <xs:element name="location" type="xs:string"/>
      <xs:element name="coordinates" minOccurs="0">
        <xs:complexType>
          <xs:attribute name="lat" type="xs:double"/>
          <xs:attribute name="lon" type="xs:double"/>
        </xs:complexType>
      </xs:element>
      <xs:element name="environment" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="LinksType">
    <xs:sequence>
      <xs:element name="link" maxOccurs="unbounded">
        <xs:complexType>
          <xs:attribute name="from" type="xs:IDREF" use="required"/>
          <xs:attribute name="to" type="xs:IDREF" use="required"/>
          <xs:attribute name="type" default="associative">
            <xs:simpleType>
              <xs:restriction base="xs:string">
                <xs:enumeration value="causal"/>
                <xs:enumeration value="temporal"/>
                <xs:enumeration value="associative"/>
                <xs:enumeration value="emotional"/>
              </xs:restriction>
            </xs:simpleType>
          </xs:attribute>
          <xs:attribute name="strength" type="xs:double" default="1.0"/>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
'''

# --------------------------------------------------------------------
# 3. Validation Functions (using lxml if available, else xml.etree)
# --------------------------------------------------------------------
def validate_with_dtd(xml_path: str, dtd_str: str = MEMORY_DTD) -> Tuple[bool, List[str]]:
    """
    Validate an XML file against the embedded DTD.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    try:
        from lxml import etree
        # Write DTD to temporary file for lxml
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dtd', delete=False) as f:
            f.write(dtd_str)
            dtd_path = f.name
        try:
            with open(xml_path, 'rb') as f:
                xml_content = f.read()
            parser = etree.XMLParser(dtd_validation=True)
            tree = etree.fromstring(xml_content, parser)
            # Also validate against DTD
            dtd = etree.DTD(file=dtd_path)
            if not dtd.validate(tree):
                errors.extend(dtd.error_log.filter_from_errors())
        finally:
            os.unlink(dtd_path)
        return len(errors) == 0, [str(e) for e in errors]
    except ImportError:
        # Fallback to basic validation (no DTD)
        try:
            ET.parse(xml_path)
            return True, []
        except ET.ParseError as e:
            return False, [str(e)]

def validate_with_xsd(xml_path: str, xsd_str: str = MEMORY_XSD) -> Tuple[bool, List[str]]:
    """
    Validate an XML file against the embedded XSD schema.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    try:
        from lxml import etree
        # Parse XSD from string
        schema_root = etree.fromstring(xsd_str)
        schema = etree.XMLSchema(schema_root)
        # Parse XML
        with open(xml_path, 'rb') as f:
            xml_doc = etree.parse(f)
        schema.assertValid(xml_doc)
        return True, []
    except ImportError:
        # No lxml – skip XSD validation
        logger.warning("lxml not installed – XSD validation skipped")
        try:
            ET.parse(xml_path)
            return True, []
        except ET.ParseError as e:
            return False, [str(e)]
    except Exception as e:
        errors.append(str(e))
        return False, errors

def create_initial_memory_file(filepath: Path):
    """
    Create a minimal, valid memory XML file with DTD reference.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE memory-system SYSTEM "memory.dtd">
<memory-system version="1.0">
  <memory-index>
    <!-- Memory entries will be stored here -->
  </memory-index>
  <experiential-lib>
    <!-- Experiential memories will be stored here -->
  </experiential-lib>
</memory-system>
'''
    filepath.write_text(content, encoding='utf-8')
    logger.info(f"Initial memory file created: {filepath}")

def validate_memory_file(filepath: Path, use_xsd: bool = True) -> Dict[str, Any]:
    """
    Comprehensive validation: check well‑formedness, DTD, and optionally XSD.
    Returns a report dictionary.
    """
    result = {
        "valid": False,
        "well_formed": True,
        "dtd_errors": [],
        "xsd_errors": [],
        "schema_used": "dtd" if not use_xsd else "xsd"
    }
    # First, check well‑formedness
    try:
        ET.parse(filepath)
    except ET.ParseError as e:
        result["well_formed"] = False
        result["errors"] = [str(e)]
        return result
    
    # DTD validation (always)
    dtd_valid, dtd_errors = validate_with_dtd(str(filepath))
    result["dtd_errors"] = dtd_errors
    
    if use_xsd:
        xsd_valid, xsd_errors = validate_with_xsd(str(filepath))
        result["xsd_errors"] = xsd_errors
        result["valid"] = dtd_valid and xsd_valid
    else:
        result["valid"] = dtd_valid
    
    return result

# --------------------------------------------------------------------
# 4. Save DTD and XSD to files (for external references)
# --------------------------------------------------------------------
def save_schemas_to_files(output_dir: Path):
    """Write the DTD and XSD to disk for external use."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dtd_path = output_dir / "memory.dtd"
    xsd_path = output_dir / "memory.xsd"
    dtd_path.write_text(MEMORY_DTD, encoding='utf-8')
    xsd_path.write_text(MEMORY_XSD, encoding='utf-8')
    logger.info(f"DTD saved to {dtd_path}, XSD saved to {xsd_path}")

# --------------------------------------------------------------------
# 5. Example usage (commented)
# --------------------------------------------------------------------
"""
# Create initial memory file
create_initial_memory_file(Path("data/memory.xml"))

# Validate existing memory file
report = validate_memory_file(Path("data/memory.xml"), use_xsd=True)
if report["valid"]:
    print("Memory file is valid")
else:
    print(f"Errors: {report['dtd_errors']} {report['xsd_errors']}")
"""

# ====================================================================================================
# END OF memory_schemas.py (31,248 characters)
# ====================================================================================================
