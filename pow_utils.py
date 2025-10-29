# pow_utils.py
import hashlib

def dsha256(b: bytes) -> bytes:
    """
    Double SHA-256 hash
    """
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def bits_to_target(bits: int) -> int:
    """
    Convierte 'bits' (formato compacto) en el valor real del target.
    Ejemplo: 0x1f0fffff -> entero grande usado para comparar con el hash.
    """
    exponent = bits >> 24
    mantissa = bits & 0x007fffff
    if bits & 0x00800000:  # si el bit de signo está puesto
        mantissa = -mantissa
    target = mantissa * (1 << (8 * (exponent - 3)))
    return target

def target_to_bits(target: int) -> int:
    """
    Convierte un target entero al formato compacto (bits).
    Inverso de bits_to_target.
    """
    exponent = (target.bit_length() + 7) // 8
    if exponent <= 3:
        mantissa = target << (8 * (3 - exponent))
    else:
        mantissa = target >> (8 * (exponent - 3))

    if mantissa & 0x00800000:
        mantissa >>= 8
        exponent += 1

    return (exponent << 24) | mantissa

def hex_le(b: bytes) -> str:
    """
    Convierte un hash a formato hexadecimal little-endian.
    """
    return b[::-1].hex()

# --- Prueba rápida ---
if __name__ == "__main__":
    print("Hash doble SHA-256 de 'hola':")
    print(hex_le(dsha256(b"hola")))
