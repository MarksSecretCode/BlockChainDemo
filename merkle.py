# merkle.py
from typing import List, Union
from pow_utils import dsha256

HashLike = Union[bytes, str]

def _to_bytes(h: HashLike) -> bytes:
    """
    Accepts either raw bytes or a hex string (no spaces).
    Returns raw bytes. Does not reverse endianness.
    """
    if isinstance(h, bytes):
        return h
    if isinstance(h, str):
        return bytes.fromhex(h)
    raise TypeError("txid must be bytes or hex string")

def merkle_root(txids: List[HashLike]) -> bytes:
    """
    Compute a Bitcoin-style Merkle root using double SHA-256 on pair concatenations.
    If the number of hashes at a level is odd, duplicate the last one.
    Returns raw bytes (32 bytes).
    """
    if not txids:
        # Convention: double-hash of empty string if there are no txs.
        return dsha256(b"")

    level = [_to_bytes(t) for t in txids]

    # Defensive: ensure every element is 32 bytes if you feed txids (optional for demo).
    # for h in level:
    #     if len(h) != 32:
    #         raise ValueError("Each txid should be 32 bytes")

    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i+1] if i + 1 < len(level) else level[i]  # duplicate last if odd
            nxt.append(dsha256(left + right))
        level = nxt

    return level[0]

# --- Quick self-test ---
if __name__ == "__main__":
    # Example with three fake txids (here we just hash labels to get 32-byte values)
    a = dsha256(b"txA")
    b = dsha256(b"txB")
    c = dsha256(b"txC")
    root = merkle_root([a, b, c])

    from pow_utils import hex_le
    print("Merkle root (LE hex for display):", hex_le(root))
