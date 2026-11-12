"""Strict upload JSON parsing with content-free failure diagnostics.

Never discard bytes, trim an invalid suffix, or infer remote success from a
partially parsed response. Diagnostics contain structure/offsets, not values.
"""
import hashlib
import json
from ._crypto import ecdh_aes_decrypt


class UploadResponseError(ValueError):
    """A remote result could not be determined from the response."""


def _shape(text, position):
    # Preserve only JSON punctuation/whitespace; redact names, credentials,
    # filenames and numbers even inside malformed JSON strings.
    safe = '{}[],:"\\'
    value = text[max(0, position - 12):position + 13]
    return ''.join(c if c in safe else ' ' if c.isspace() else '*' for c in value)


def _kind(payload):
    plain = payload.lstrip()
    if plain.startswith((b'{', b'[', b'\xef\xbb\xbf')):
        return 'json-like'
    if plain.startswith(b'<'):
        return 'markup'
    if plain.startswith(b'\x1f\x8b'):
        return 'gzip'
    if plain.startswith((b'\xff\xfe', b'\xfe\xff')):
        return 'utf16-bom'
    return 'other'


def _object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate-key')
        obj[key] = value
    return obj


def _constant(_value):
    raise ValueError('nonfinite-number')


def decode_upload_response(raw):
    if not isinstance(raw, bytes) or not raw:
        raise UploadResponseError('响应为空或非二进制数据')
    rid = hashlib.sha256(raw).hexdigest()[:12]
    common = 'parser=2 wire=%d id=%s' % (len(raw), rid)
    plain = raw.lstrip()
    if plain.startswith((b'{', b'[', b'\xef\xbb\xbf')):
        stage, payload = '明文', plain
    else:
        stage = 'AES/LZ4'
        try:
            payload = ecdh_aes_decrypt(raw)
        except Exception as exc:
            raise UploadResponseError('AES/LZ4解码失败（%s error=%s）' %
                                      (common, type(exc).__name__)) from exc
    common += ' payload=%d kind=%s nul=%d tail_nul=%d' % (
        len(payload), _kind(payload), payload.count(b'\0'),
        len(payload) - len(payload.rstrip(b'\0')))
    encoding_errors = []
    text = None
    encoding = ''
    for candidate in ('utf-8-sig', 'gb18030'):
        try:
            text, encoding = payload.decode(candidate), candidate
            break
        except UnicodeDecodeError as exc:
            encoding_errors.append('%s@%d' % (candidate, exc.start))
    if text is None:
        raise UploadResponseError('%s响应字符编码无效（%s %s）；远端结果未确认' %
                                  (stage, common, ','.join(encoding_errors)))
    try:
        result = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    except json.JSONDecodeError as exc:
        # JSONDecodeError.msg is fixed parser text; .doc contains secrets.
        raise UploadResponseError('%s响应不是有效JSON（%s enc=%s pos=%d line=%d col=%d error=%s shape=%s）；远端结果未确认' %
                                  (stage, common, encoding, exc.pos, exc.lineno,
                                   exc.colno, exc.msg, _shape(text, exc.pos))) from exc
    except ValueError as exc:
        raise UploadResponseError('%s响应JSON校验失败（%s error=%s）；远端结果未确认' %
                                  (stage, common, str(exc))) from exc
    if not isinstance(result, dict):
        raise UploadResponseError('上传响应JSON必须为对象（%s）' % common)
    return result
