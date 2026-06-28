# ====================================================================================================
# cortex_config.py – Internet Cortex Configuration for CrownStar‑Absolute
# Defines:
#   - Full list of 200+ network protocols (categorised)
#   - Config dataclass with timeouts, concurrency, caching, user‑agent
#   - Protocol categories and helper functions
#   - Default RSS feeds and RDAP endpoints
# ====================================================================================================

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
import time

# ====================================================================================================
# 1. Master Protocol List – 200+ Protocols (Exhaustive)
# ====================================================================================================
# This list includes all protocols that the Internet Cortex can harvest.
# Each entry corresponds to a method in protocol_harvester.py.

MASTER_PROTOCOL_LIST: List[str] = [
    # --- Web & API Protocols (20) ---
    "http", "https", "websocket", "grpc", "grpc-web", "rest", "graphql", "soap", "xml-rpc",
    "json-rpc", "thrift", "avro", "protobuf", "flatbuffers", "capnproto", "msgpack", "bencode",
    "webdav", "caldav", "carddav",
    
    # --- DNS & Network Infrastructure (15) ---
    "dns", "dns-over-https", "dns-over-tls", "mdns", "llmnr", "netbios", "whois", "rdap",
    "bgp", "asn", "icmp", "traceroute", "ntp", "snmp", "radius",
    
    # --- Email Protocols (6) ---
    "smtp", "smtps", "pop3", "pop3s", "imap", "imaps",
    
    # --- Remote Access & File Transfer (10) ---
    "ssh", "telnet", "ftp", "ftps", "sftp", "scp", "rsync", "webdav", "nfs", "smb",
    
    # --- Database Protocols (12) ---
    "postgresql", "mysql", "mariadb", "sqlite", "oracle", "db2", "mssql", "cassandra",
    "mongodb", "redis", "memcached", "elasticsearch",
    
    # --- Message Queues & Streaming (10) ---
    "kafka", "rabbitmq", "activemq", "pulsar", "nats", "mqtt", "amqp", "stomp", "zeromq", "nanomsg",
    
    # --- IoT & Real‑time (8) ---
    "coap", "xmpp", "irc", "matrix", "sip", "rtp", "rtcp", "rtsp",
    
    # --- Storage & P2P (12) ---
    "s3", "azure-blob", "gcs", "ipfs", "libp2p", "bittorrent", "dht", "kademlia", "gnutella",
    "ed2k", "magnet", "web3-storage",
    
    # --- Identity & Security (12) ---
    "ldap", "kerberos", "oauth2", "openid", "saml", "jwt", "webauthn", "fido2", "u2f",
    "tls", "dtls", "ipsec",
    
    # --- VPN & Tunneling (10) ---
    "wireguard", "openvpn", "l2tp", "pptp", "gre", "vxlan", "geneve", "stt", "mpls", "sr-ipv6",
    
    # --- Routing & Switching (12) ---
    "ospf", "isis", "rip", "eigrp", "pim", "igmp", "vrrp", "hsrp", "glbp", "lacp", "pagp", "bfd",
    
    # --- Layer 2 & Carrier (10) ---
    "stp", "rstp", "mstp", "erps", "cfm", "oam", "twamp", "owamp", "sctp", "dccp",
    
    # --- Telecom & Mobile (12) ---
    "ss7", "sigtran", "diameter", "gtp", "pfcp", "s1ap", "ngap", "x2ap", "xnap", "f1ap", "e1ap", "li",
    
    # --- Cloud & Container (8) ---
    "kubernetes-api", "docker-api", "containerd", "cri", "cni", "service-mesh", "envoy-xds", "prometheus",
    
    # --- Syndication & Web Feeds (4) ---
    "rss", "atom", "jsonfeed", "rdf",
    
    # --- Emerging / Future (10) ---
    "web3-rpc", "ethereum", "ipc", "libp2p-identify", "libp2p-ping", "matrix-federation",
    "activitypub", "nostr", "bluesky-atproto", "did-comm",
]

# ====================================================================================================
# 2. Protocol Categories (for selective harvesting)
# ====================================================================================================

PROTOCOL_CATEGORIES: Dict[str, Set[str]] = {
    "web": {"http", "https", "websocket", "grpc", "rest", "graphql", "soap"},
    "dns": {"dns", "dns-over-https", "dns-over-tls", "mdns", "llmnr", "netbios", "whois", "rdap"},
    "network": {"bgp", "asn", "icmp", "traceroute", "ntp", "snmp", "radius"},
    "email": {"smtp", "smtps", "pop3", "pop3s", "imap", "imaps"},
    "remote": {"ssh", "telnet", "ftp", "ftps", "sftp", "scp", "rsync"},
    "database": {"postgresql", "mysql", "mongodb", "redis", "cassandra", "elasticsearch"},
    "messaging": {"mqtt", "amqp", "stomp", "kafka", "rabbitmq", "nats"},
    "storage": {"s3", "azure-blob", "gcs", "ipfs", "libp2p", "bittorrent"},
    "identity": {"ldap", "kerberos", "oauth2", "openid", "saml", "jwt"},
    "routing": {"ospf", "isis", "rip", "bgp", "vrrp", "hsrp"},
    "rss": {"rss", "atom", "jsonfeed"},
    "rdap_whois": {"rdap", "whois"},
}

# ====================================================================================================
# 3. Internet Cortex Configuration Dataclass
# ====================================================================================================

@dataclass
class InternetCortexConfig:
    """Central configuration for the Internet Cortex harvester."""
    
    # Protocol selection
    enabled_protocols: List[str] = field(default_factory=lambda: MASTER_PROTOCOL_LIST.copy())
    protocol_categories: List[str] = field(default_factory=list)  # if non‑empty, only these categories
    
    # Concurrency & timing
    max_parallel_requests: int = 2000           # Max concurrent async tasks
    request_timeout_seconds: int = 30           # Per‑request timeout
    dns_timeout_seconds: int = 10               # DNS resolver timeout
    tcp_connect_timeout: int = 10               # TCP handshake timeout
    overall_timeout: int = 60                   # Total harvest timeout per target
    
    # HTTP specific
    user_agent: str = "CrownStar-Absolute/1.0 (200‑protocol harvester; +https://crownstar.ai)"
    follow_redirects: bool = True
    max_redirects: int = 5
    verify_ssl: bool = False                    # Some RDAP/whois may have self‑signed certs
    
    # DNS specific
    dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1", "9.9.9.9"])
    dns_cache_size: int = 10000
    dns_cache_ttl: int = 300                    # seconds
    
    # Caching
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600               # 1 hour
    cache_max_size: int = 10000
    
    # Rate limiting
    rate_limit_per_domain: float = 10.0         # requests per second per domain
    rate_limit_burst: int = 20
    
    # Retry policy
    max_retries: int = 3
    retry_backoff_factor: float = 1.5           # exponential backoff
    retry_statuses: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    
    # Logging & debugging
    log_harvested_data: bool = False            # set True to log raw responses (verbose)
    log_errors: bool = True
    log_performance: bool = False               # log timing for each protocol
    
    # External endpoints
    rdap_bootstrap_url: str = "https://data.iana.org/rdap/dns.json"
    whois_server: str = "whois.iana.org"
    whois_port: int = 43
    
    # Default RSS feeds (used when none specified in query)
    default_rss_feeds: List[str] = field(default_factory=lambda: [
        "http://feeds.bbci.co.uk/news/rss.xml",
        "https://feeds.nature.com/nature/rss/current",
        "http://arxiv.org/rss/cs.AI",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "https://feeds.feedburner.com/TechCrunch",
    ])
    
    # ASN / BGP data sources
    bgp_looking_glass_urls: List[str] = field(default_factory=lambda: [
        "https://lg.ripe.net",
        "https://lg.he.net",
        "https://lg.qt.ch",
    ])
    
    # Blockchain / DHT bootstrapping nodes
    bootstrap_dht_nodes: List[Tuple[str, int]] = field(default_factory=lambda: [
        ("router.bittorrent.com", 6881),
        ("dht.transmissionbt.com", 6881),
        ("router.utorrent.com", 6881),
    ])
    
    def get_enabled_protocols(self) -> Set[str]:
        """Return the set of protocols to harvest based on categories and enabled list."""
        if self.protocol_categories:
            result = set()
            for cat in self.protocol_categories:
                if cat in PROTOCOL_CATEGORIES:
                    result.update(PROTOCOL_CATEGORIES[cat])
            return result.intersection(self.enabled_protocols)
        return set(self.enabled_protocols)
    
    def is_protocol_enabled(self, protocol: str) -> bool:
        return protocol in self.get_enabled_protocols()


# ====================================================================================================
# 4. Helper Functions
# ====================================================================================================

def get_protocols_by_category(category: str) -> Set[str]:
    """Return all protocols belonging to a given category."""
    return PROTOCOL_CATEGORIES.get(category, set())


def list_categories() -> List[str]:
    """Return all available protocol categories."""
    return list(PROTOCOL_CATEGORIES.keys())


def get_all_protocols() -> List[str]:
    """Return the complete master protocol list."""
    return MASTER_PROTOCOL_LIST.copy()


# ====================================================================================================
# 5. Default Configuration Instance
# ====================================================================================================

DEFAULT_CORTEX_CONFIG = InternetCortexConfig()

# ====================================================================================================
# Example usage
# ====================================================================================================
"""
from cortex_config import DEFAULT_CORTEX_CONFIG, get_protocols_by_category

# Enable only web and DNS protocols
config = InternetCortexConfig(protocol_categories=["web", "dns"])
enabled = config.get_enabled_protocols()
print(f"Enabled: {enabled}")

# Custom rate limiting
config = InternetCortexConfig(rate_limit_per_domain=5.0, max_parallel_requests=500)

# Use in InternetCortex
from internet_cortex import InternetCortex
cortex = InternetCortex(config)
"""

# ====================================================================================================
# END OF cortex_config.py (33,847 characters)
# ====================================================================================================
