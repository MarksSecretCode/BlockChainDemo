# wallet_demo.py
# Generates a secp256k1 keypair, derives hash160(pubkey) and a Base58Check (P2PKH-like) address.

import os
import sys
import hashlib
from ecdsa import SigningKey, SECP256k1

B58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def ripemd160(b: bytes) -> bytes:
    """
    Try RIPEMD-160 from hashlib (OpenSSL-backed).
    If not available, suggest installing pycryptodome.
    """
    try:
        h = hashlib.new('ripemd160')
    except ValueError:
        sys.stderr.write(
            "[!] RIPEMD-160 not available in hashlib. Install pycryptodome:\n"
            "    pip install pycryptodome\n"
        )
        raise
    h.update(b)
    return h.digest()

def hash160(b: bytes) -> bytes:
    """RIPEMD160(SHA256(b))"""
    return ripemd160(sha256(b))

def b58encode(b: bytes) -> str:
    """Encode bytes into Base58 (no checksum)."""
    # Count leading zeros for '1' prefix
    n_pad = len(b) - len(b.lstrip(b'\x00'))
    num = int.from_bytes(b, 'big')

    enc = bytearray()
    while num > 0:
        num, rem = divmod(num, 58)
        enc.append(B58_ALPHABET[rem])
    enc.extend(b'1' * n_pad)
    enc.reverse()
    return enc.decode('ascii')

def base58check_encode(version: int, payload: bytes) -> str:
    """Base58Check: version(1) + payload + checksum(4) where checksum = SHA256^2(prefix)[:4]."""
    prefix = bytes([version]) + payload
    checksum = sha256(sha256(prefix))[:4]
    return b58encode(prefix + checksum)

def to_uncompressed_pubkey(vk) -> bytes:
    """
    Uncompressed SEC format: 0x04 || X(32) || Y(32)
    """
    px = vk.pubkey.point.x()
    py = vk.pubkey.point.y()
    return b'\x04' + px.to_bytes(32, 'big') + py.to_bytes(32, 'big')

def to_compressed_pubkey(vk) -> bytes:
    """
    Compressed SEC format: 0x02/0x03 || X(32), depending on Y parity.
    """
    px = vk.pubkey.point.x()
    py = vk.pubkey.point.y()
    prefix = b'\x02' if (py % 2 == 0) else b'\x03'
    return prefix + px.to_bytes(32, 'big')

def main():
    # 1) Generate secp256k1 private key (32 random bytes in [1, n-1])
    sk = SigningKey.generate(curve=SECP256k1)  # ecdsa library handles valid range
    vk = sk.get_verifying_key()

    privkey_bytes = sk.to_string()  # 32 bytes
    pubkey_uncompressed = to_uncompressed_pubkey(vk)
    pubkey_compressed = to_compressed_pubkey(vk)

    # 2) Hash160 of the *compressed* public key (Bitcoin practice)
    h160 = hash160(pubkey_compressed)  # 20 bytes

    # 3) P2PKH-like Base58Check address on mainnet version 0x00
    address_b58 = base58check_encode(0x00, h160)

    # 4) Print results
    print("=== secp256k1 Keypair & Address (BTC-like) ===")
    print(f"Private key (hex, 32B): {privkey_bytes.hex()}")
    print(f"Public key (uncompressed, hex): {pubkey_uncompressed.hex()}")
    print(f"Public key (compressed,  hex): {pubkey_compressed.hex()}")
    print(f"hash160(pubkey_compressed):   {h160.hex()}")
    print(f"Base58Check P2PKH address:    {address_b58}")

    # Optional: show WIF for the private key (mainnet, uncompressed)
    # WIF = Base58Check(0x80 || priv || (0x01 if compressed) || checksum)
    wif_payload = b'\x80' + privkey_bytes + b'\x01'  # add 0x01 to signal compressed pubkey usage
    wif = b58encode(wif_payload + sha256(sha256(wif_payload))[:4])
    print(f"WIF (compressed):             {wif}")

if __name__ == "__main__":
    main()
