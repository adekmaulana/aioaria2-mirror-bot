import base64
import codecs
import json
import struct
from typing import MutableMapping
from Crypto.Cipher import AES


def makebyte(x: str) -> bytes:
    return codecs.encode(x, "latin-1")


def makestring(x: bytes) -> str:
    return codecs.decode(x, "latin-1")


def aes_cbc_encrypt(data, key):
    aes_cipher = AES.new(key, AES.MODE_CBC, makebyte('\0' * 16))
    return aes_cipher.encrypt(data)


def aes_cbc_decrypt(data, key):
    aes_cipher = AES.new(key, AES.MODE_CBC, makebyte('\0' * 16))
    return aes_cipher.decrypt(data)


def aes_cbc_encrypt_a32(data, key):
    return str_to_a32(aes_cbc_encrypt(a32_to_str(data), a32_to_str(key)))


def aes_cbc_decrypt_a32(data, key):
    return str_to_a32(aes_cbc_decrypt(a32_to_str(data), a32_to_str(key)))


def stringhash(str, aeskey):
    s32 = str_to_a32(str)
    h32 = [0, 0, 0, 0]
    for i in range(len(s32)):
        h32[i % 4] ^= s32[i]
    for r in range(0x4000):
        h32 = aes_cbc_encrypt_a32(h32, aeskey)
    return a32_to_base64((h32[0], h32[2]))


def prepare_key(arr):
    pkey = [0x93C467E3, 0x7DB0C7A4, 0xD1BE3F81, 0x0152CB56]
    for r in range(0x10000):
        for j in range(0, len(arr), 4):
            key = [0, 0, 0, 0]
            for i in range(4):
                if i + j < len(arr):
                    key[i] = arr[i + j]
            pkey = aes_cbc_encrypt_a32(pkey, key)
    return pkey


def encrypt_key(a, key):
    return sum((aes_cbc_encrypt_a32(a[i:i + 4], key)
                for i in range(0, len(a), 4)), ())


def decrypt_key(a, key):
    return sum((aes_cbc_decrypt_a32(a[i:i + 4], key)
                for i in range(0, len(a), 4)), ())


def encrypt_attr(attr, key):
    attr = makebyte('MEGA' + json.dumps(attr))
    if len(attr) % 16:
        attr += b'\0' * (16 - len(attr) % 16)
    return aes_cbc_encrypt(attr, a32_to_str(key))


def decrypt_attr(attr, key) -> MutableMapping:
    attr = aes_cbc_decrypt(attr, a32_to_str(key))
    attr = makestring(attr)
    attr = attr.rstrip('\0')
    return json.loads(attr[4:]) if attr[:6] == 'MEGA{"' else {}


def a32_to_str(a):
    return struct.pack('>%dI' % len(a), *a)


def str_to_a32(b):
    if isinstance(b, str):
        b = makebyte(b)
    if len(b) % 4:
        # pad to multiple of 4
        b += b'\0' * (4 - len(b) % 4)
    return struct.unpack('>%dI' % (len(b) / 4), b)


def base64_url_decode(data: str) -> bytes:
    data += '=='[(2 - len(data) * 3) % 4:]
    for search, replace in (('-', '+'), ('_', '/'), (',', '')):
        data = data.replace(search, replace)
    return base64.b64decode(data)


def base64_to_a32(s):
    return str_to_a32(base64_url_decode(s))


def base64_url_encode(data):
    data = base64.b64encode(data)
    data = makestring(data)
    for search, replace in (('+', '-'), ('/', '_'), ('=', '')):
        data = data.replace(search, replace)
    return data


def a32_to_base64(a):
    return base64_url_encode(a32_to_str(a))
