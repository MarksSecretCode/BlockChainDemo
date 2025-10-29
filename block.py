# block.py
from dataclasses import dataclass
import struct
import time
from pow_utils import dsha256, bits_to_target

@dataclass
class BlockHeader:
    version: int
    prev_block: bytes      # 32 bytes (store as big-endian hash)
    merkle_root: bytes     # 32 bytes (store as big-endian hash)
    time: int              # unix timestamp
    bits: int              # compact difficulty
    nonce: int             # 32-bit

    def serialize(self) -> bytes:
        """
        Bitcoin-style header serialization:
        version (LE4), prev_block (LE32), merkle_root (LE32), time (LE4), bits (LE4), nonce (LE4)
        Note: hashes are displayed little-endian, but serialized as little-endian bytes of the big-endian value,
        which effectively means reversing for display; here we store BE internally and reverse on serialize.
        """
        return (
            struct.pack("<L", self.version) +
            self.prev_block[::-1] +
            self.merkle_root[::-1] +
            struct.pack("<L", self.time) +
            struct.pack("<L", self.bits) +
            struct.pack("<L", self.nonce)
        )

    def hash(self) -> bytes:
        """
        Double SHA-256 of the serialized header. Returns raw 32 bytes (big-endian).
        Display with hex_le() when needed.
        """
        return dsha256(self.serialize())


def mine_block(header: BlockHeader, max_nonce_loops: int | None = None) -> tuple[bool, BlockHeader, bytes]:
    """
    Increment nonce until header.hash() <= target derived from header.bits.
    If max_nonce_loops is provided, stop after that many attempts (useful for tests/UI).
    Returns (found, header, hash_bytes).
    If nonce wraps, return (False, header, last_hash) so caller can bump time or coinbase extranonce.
    """
    target = bits_to_target(header.bits)
    attempts = 0

    while True:
        h = header.hash()
        if int.from_bytes(h, "big") <= target:
            return True, header, h

        # Step nonce
        header.nonce = (header.nonce + 1) & 0xffffffff
        attempts += 1

        # Optional limiter for UI/testing
        if max_nonce_loops is not None and attempts >= max_nonce_loops:
            return False, header, h

        # If we wrapped, likely need to tweak coinbase extranonce or timestamp
        if header.nonce == 0:
            return False, header, h
