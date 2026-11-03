"""Strict JSON decoding: never discard bytes or infer transfer success."""
import json
from ._crypto import ecdh_aes_decrypt


def decode_upload_response(raw):
    if not isinstance(raw, bytes) or not raw:
        raise ValueError('响应为空或非二进制数据')
    # Plain error responses are possible; encrypted success uses AES + LZ4.
    plain = raw.lstrip()
    if plain.startswith((b'{', b'[', b'\xef\xbb\xbf')):
        stage = '明文'
        payload = plain
    else:
        stage = 'AES/LZ4'
        try:
            payload = ecdh_aes_decrypt(raw)
        except Exception as exc:
            raise ValueError('AES/LZ4解码失败（响应长度%d，%s）' % (len(raw), type(exc).__name__)) from exc
    try:
        text = payload.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            text = payload.decode('gb18030')
        except UnicodeDecodeError:
            # Last resort: latin-1 never fails and preserves all bytes. The JSON
            # structure and ASCII keys (status, sha1, pickcode) remain intact;
            # only Chinese message fields may show garbled characters.
            text = payload.decode('latin-1')
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError('%s响应不是有效JSON（长度%d）' % (stage, len(payload))) from exc
    if not isinstance(result, dict):
        raise ValueError('上传响应JSON必须为对象')
    return result
