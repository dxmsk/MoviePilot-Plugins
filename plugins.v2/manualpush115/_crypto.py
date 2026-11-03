"""
115 网页版接口所需的纯 Python 加解密工具。

依赖：仅标准库 + 同目录的 aes.py（纯 Python AES 实现）。
参考实现：https://github.com/ChenyangGao/p115client (p115cipher)
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from binascii import b2a_hex, crc32
from hashlib import md5, sha1
from time import time
from urllib.parse import urlencode
from typing import Any, Dict, Tuple

try:  # 包内使用（MoviePilot 插件目录）
    from ._vendor.aes import AES
except ImportError:  # 独立运行/测试
    from _vendor.aes import AES  # type: ignore

# ---- 常量（来自 p115cipher） ----
CRC_SALT = b"^j>WD3Kr?J2gLFjD4W2y@"
MD5_SALT = b"Qclm8MGWUv59TnrR0XPg"
G_key_l = b"x\x06\xadL3\x86]\x18L\x01?F"
G_key_s = b")#!^"

AES_PUBKEY = bytes(b"\x1d\x03\x0e\x80\xa1x\xdc\xee\xce\xcd\xa3w\xde\x12\x8d\x8e"
                   b"\xd9\xdd\xcfU\xaea\xedF\xea\x12\x1a\x1c\xfc\x81")
AES_KEY = b"\xfb\x1a\x19\xd6R\xf5\xaa\xf7\xbce\x1d\x0fi\xbfB/"
AES_IV = b"i\xbfB/I\x96\x05P\xa0\xadD\xec4F\xcbL"
RSA_RAND_KEY = b"\x00" * 16
RSA_KEY = b"\x8d\xa5\xa5\x8d"

# 上传接口固定公钥对（RSA 加密用）
RSA_PUBKEY_PAIR = (
    0x8686980c0f5a24c4b9d43020cd2c22703ff3f450756529058b1cf88f09b8602136477198a6e2683149659bd122c33592fdb5ad47944ad1ea4d36c6b172aad6338c3bb6ac6227502d010993ac967d1aef00f0c8e038de2e4d3bc2ec368af2e9f10a6f1eda4f7262f136420c07c331b871bf139f74f3010e3c4fe57df3afb71683,
    0x10001,
)

G_kts = bytes((
    0xf0, 0xe5, 0x69, 0xae, 0xbf, 0xdc, 0xbf, 0x8a, 0x1a, 0x45, 0xe8, 0xbe, 0x7d, 0xa6, 0x73, 0xb8,
    0xde, 0x8f, 0xe7, 0xc4, 0x45, 0xda, 0x86, 0xc4, 0x9b, 0x64, 0x8b, 0x14, 0x6a, 0xb4, 0xf1, 0xaa,
    0x38, 0x01, 0x35, 0x9e, 0x26, 0x69, 0x2c, 0x86, 0x00, 0x6b, 0x4f, 0xa5, 0x36, 0x34, 0x62, 0xa6,
    0x2a, 0x96, 0x68, 0x18, 0xf2, 0x4a, 0xfd, 0xbd, 0x6b, 0x97, 0x8f, 0x4d, 0x8f, 0x89, 0x13, 0xb7,
    0x6c, 0x8e, 0x93, 0xed, 0x0e, 0x0d, 0x48, 0x3e, 0xd7, 0x2f, 0x88, 0xd8, 0xfe, 0xfe, 0x7e, 0x86,
    0x50, 0x95, 0x4f, 0xd1, 0xeb, 0x83, 0x26, 0x34, 0xdb, 0x66, 0x7b, 0x9c, 0x7e, 0x9d, 0x7a, 0x81,
    0x32, 0xea, 0xb6, 0x33, 0xde, 0x3a, 0xa9, 0x59, 0x34, 0x66, 0x3b, 0xaa, 0xba, 0x81, 0x60, 0x48,
    0xb9, 0xd5, 0x81, 0x9c, 0xf8, 0x6c, 0x84, 0x77, 0xff, 0x54, 0x78, 0x26, 0x5f, 0xbe, 0xe8, 0x1e,
    0x36, 0x9f, 0x34, 0x80, 0x5c, 0x45, 0x2c, 0x9b, 0x76, 0xd5, 0x1b, 0x8f, 0xcc, 0xc3, 0xb8, 0xf5,
))


def _pad(data: bytes) -> bytes:
    pad_size = -len(data) & 15
    if pad_size:
        return data + bytes((pad_size,) * pad_size)
    return data


def _unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad_size = data[-1]
    if 0 < pad_size < 16 and all(c == pad_size for c in data[-pad_size:]):
        return data[:-pad_size]
    return data


def aes_cbc_encrypt(data: bytes, key: bytes = AES_KEY, iv: bytes = AES_IV) -> bytes:
    encrypt = AES(key).encrypt
    view = _pad(data)
    out = bytearray()
    last = iv
    for i in range(0, len(view), 16):
        block = bytes(p ^ l for p, l in zip(view[i:i + 16], last))
        last = bytes(encrypt(block))
        out += last
    return bytes(out)


def aes_cbc_decrypt(cipher: bytes, key: bytes = AES_KEY, iv: bytes = AES_IV) -> bytes:
    decrypt = AES(key).decrypt
    out = bytearray()
    last = iv
    for i in range(0, len(cipher), 16):
        block = bytes(decrypt(cipher[i:i + 16]))
        out += bytes(p ^ l for p, l in zip(block, last))
        last = cipher[i:i + 16]
    return _unpad(bytes(out))


def lz4_block_decompress(source: bytes, uncompressed_size: int = -1) -> bytes:
    """纯 Python 的 LZ4 block 解压。"""
    src = source
    src_len = len(src)
    src_ptr = 0
    dest = bytearray()
    while src_ptr < src_len:
        token = src[src_ptr]
        src_ptr += 1
        lit_len = token >> 4
        if lit_len == 15:
            start = src_ptr
            try:
                while src[src_ptr] == 255:
                    src_ptr += 1
                lit_len += (src_ptr - start) * 255 + src[src_ptr]
                src_ptr += 1
            except IndexError:
                pass
        if lit_len:
            dest += src[src_ptr:src_ptr + lit_len]
            src_ptr += lit_len
        if src_ptr >= src_len:
            break
        offset = src[src_ptr] | (src[src_ptr + 1] << 8)
        src_ptr += 2
        match_len = token & 0x0F
        if match_len == 15:
            start = src_ptr
            try:
                while src[src_ptr] == 255:
                    src_ptr += 1
                match_len += (src_ptr - start) * 255 + src[src_ptr]
                src_ptr += 1
            except IndexError:
                pass
        match_len += 4
        dest_ptr = len(dest)
        match_pos = dest_ptr - offset
        if offset >= match_len:
            dest += dest[match_pos:match_pos + match_len]
        else:
            if offset == 1:
                dest += bytes((dest[match_pos],)) * match_len
            else:
                end_ptr = dest_ptr + match_len
                while dest_ptr < end_ptr:
                    copy_size = offset if offset < (end_ptr - dest_ptr) else (end_ptr - dest_ptr)
                    dest += dest[match_pos:match_pos + copy_size]
                    dest_ptr += copy_size
                    offset += offset
    return bytes(dest)


def lz4_decompress(source: bytes) -> bytes:
    src = source
    data = b""
    while src and len(src) > 2 and (src_len := (src[0] + (src[1] << 8))):
        data += lz4_block_decompress(src[2:src_len + 2])
        src = src[src_len + 2:]
    return data


def ecdh_aes_encrypt(data: bytes) -> bytes:
    return aes_cbc_encrypt(data)


def ecdh_aes_decrypt(cipher: bytes) -> bytes:
    return lz4_decompress(aes_cbc_decrypt(cipher))


def content_maybe_decrypt(content: bytes) -> bytes:
    """115 部分接口返回明文 JSON，部分返回加密内容，这里统一处理。"""
    if content[:1] + content[-1:] in (b"{}", b"[]", b'""'):
        return content
    return ecdh_aes_decrypt(content)


def ecdh_encode_token(timestamp: int, pubkey: bytes = AES_PUBKEY) -> bytes:
    token = bytearray()
    token += pubkey[:15]
    token += b"\x00s\x00\x00\x00"
    token += timestamp.to_bytes(4, "little")
    token += pubkey[15:]
    token += b"\x00\x01\x00\x00\x00"
    token += crc32(CRC_SALT + token).to_bytes(4, "little")
    return b64encode(bytes(token))


def _bytes_xor(v1: bytes, v2: bytes) -> bytes:
    size = len(v1)
    return (int.from_bytes(v1) ^ int.from_bytes(v2)).to_bytes(size, "big")


def xor(src: bytes, key: bytes) -> bytes:
    secret = bytearray()
    i = len(src) & 0b11
    if i:
        secret += _bytes_xor(src[:i], key[:i])
    while i != len(src):
        j = min(i + len(key), len(src))
        secret += _bytes_xor(src[i:j], key[:j - i])
        i = j
    return bytes(secret)


def rsa_gen_key(rand_key: bytes, sk_len: int = 4) -> bytes:
    xor_key = bytearray(sk_len)
    length = sk_len * (sk_len - 1)
    index = 0
    for i in range(sk_len):
        x = (rand_key[i] + G_kts[index]) & 0xFF
        xor_key[i] = G_kts[length] ^ x
        length -= sk_len
        index += sk_len
    return bytes(xor_key)


def _rsa_pub_encrypt(data: bytes, block_size: int = 128) -> bytes:
    n, e = RSA_PUBKEY_PAIR
    out = bytearray()
    step = block_size - 11
    for l in range(0, len(data), step):
        chunk = data[l:l + step]
        padded = bytearray(b"\x00")
        padded += b"\x02" * (block_size - 2 - len(chunk))
        padded += b"\x00"
        padded += chunk
        out += pow(int.from_bytes(padded), e, n).to_bytes(block_size, "big")
    return bytes(out)


def make_upload_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """为网页版上传初始化接口（4.0/initupload.php）构建加密请求参数。"""
    t = int(time())
    payload["t"] = t

    sig = sha1(str(payload["userkey"]).encode("ascii"))
    sig.update(b2a_hex(sha1(
        "{userid}{fileid}{target}0".format_map(payload).encode("ascii")).digest()))
    sig.update(b"000000")
    payload["sig"] = sig.hexdigest().upper()

    token = md5(MD5_SALT)
    token.update("{fileid}{filesize}{sign_key}{sign_val}{userid}{t}".format_map(payload).encode("ascii"))
    token.update(b2a_hex(md5(b"%d" % int(payload["userid"])).digest()))
    token.update(str(payload["appversion"]).encode("ascii"))
    payload["token"] = token.hexdigest()

    body = urlencode(sorted(
        (k, v) for k, v in payload.items() if v not in (None, "")
    )).encode("latin-1")
    return {
        "params": {"k_ec": ecdh_encode_token(t).decode("ascii")},
        "data": ecdh_aes_encrypt(body),
    }
