# mine_demo.py
import time
from pow_utils import bits_to_target, hex_le, dsha256
from merkle import merkle_root
from block import BlockHeader, mine_block

def main():
    # Demo params
    version = 1
    prev_block_be = bytes.fromhex("00" * 32)  # genesis prev hash = 32 zero bytes (big-endian)
    # Fake coinbase txid (for demo, we hash a label; in real code, use a serialized tx and dsha256)
    coinbase_txid = dsha256(b"coinbase to treasury addr")
    txids = [coinbase_txid]

    root = merkle_root(txids)  # returns raw bytes (big-endian)
    bits = 0x1f0fffff          # easy target for laptop demo
    hdr = BlockHeader(
        version=version,
        prev_block=prev_block_be,
        merkle_root=root,
        time=int(time.time()),
        bits=bits,
        nonce=0
    )

    target = bits_to_target(bits)
    print("Mining block…")
    print("Target (hex, BE):", hex(target)[2:])
    t0 = time.time()

    found, mined_hdr, h = mine_block(hdr)
    dt = time.time() - t0

    if found:
        print("✅ Block found!")
    else:
        print("⏭️  Stopped without finding (nonce wrapped or limit reached). Tweak time or coinbase extranonce and retry.")

    print("Nonce:", mined_hdr.nonce)
    print("Time :", mined_hdr.time, f"({dt:.3f}s elapsed)")
    print("Merkle root (LE):", hex_le(mined_hdr.merkle_root))
    print("Block hash   (LE):", hex_le(h))

    # Quick validity check
    ok_pow = int.from_bytes(h, "big") <= target
    print("Valid under target?:", ok_pow)

if __name__ == "__main__":
    main()
