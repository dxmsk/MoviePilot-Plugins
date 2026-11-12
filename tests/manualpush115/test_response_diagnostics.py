import importlib
import json
import pytest


def module(env):
    return importlib.import_module(env.package.__name__ + '.response')


def pack(env, payload):
    crypto = importlib.import_module(env.package.__name__ + '._crypto')
    n = len(payload)
    block = bytearray([min(n, 15) << 4])
    if n >= 15:
        rest = n - 15
        while rest >= 255:
            block.append(255)
            rest -= 255
        block.append(rest)
    block.extend(payload)
    return crypto.aes_cbc_encrypt(len(block).to_bytes(2, 'little') + block)


@pytest.mark.parametrize('encoding', ['utf-8', 'gb18030'])
@pytest.mark.parametrize('status', [1, 2, 7])
def test_valid_response_keeps_original_fields(env, encoding, status):
    obj = {'status': status, 'message': '中文电影', 'pickcode': 'abc'}
    payload = json.dumps(obj, ensure_ascii=False).encode(encoding)
    assert module(env).decode_upload_response(payload) == obj
    assert module(env).decode_upload_response(pack(env, payload)) == obj


@pytest.mark.parametrize('payload', [b'{"status":2}\0', b'{"status":2}junk',
    b'{"status":', b'{"status":2,"secret":"COOKIE_SECRET" "broken":1}',
    b'{"status":2,"message":"\xff"}', b'[]'])
def test_malformed_never_returns_success_and_diagnostics_are_redacted(env, payload):
    with pytest.raises(module(env).UploadResponseError) as error:
        module(env).decode_upload_response(pack(env, payload))
    msg = str(error.value)
    assert 'parser=2' in msg
    assert 'wire=' in msg and 'id=' in msg
    assert 'COOKIE_SECRET' not in msg and '"status"' not in msg
    assert len(msg) < 700


def test_parser_error_reaches_history_without_deleting_source(env, monkeypatch):
    path = env.root / 'fixture.mkv'
    path.write_bytes(b'movie')
    env.plugin.init_plugin({**env.plugin._config, 'delete_on_success': True})
    def fail(path):
        raise env.client_module.P115ResponseError('parser=2 malformed JSON')
    env.client.answer = fail
    assert env.plugin.api_push({'paths': [str(path)]})['success']
    status = env.finish()
    assert status['job']['success'] == 0
    assert status['history'][0]['remote_result'] == 'unconfirmed'
    assert path.exists()


def test_upload_init_uses_typed_parse_error(env, monkeypatch):
    client = env.client_module.P115WebClient('UID=fixture')
    monkeypatch.setattr(client, 'upload_info', lambda: {'user_id':'1','userkey':'fixture'})
    monkeypatch.setattr(client, '_request', lambda *a, **kw: pack(env, b'{"status":2}junk'))
    with pytest.raises(env.client_module.P115ResponseError, match='parser=2'):
        client.upload_init({'filename':'fixture.mkv', 'fileid':'A'*40,'filesize':12})


@pytest.mark.parametrize('block', [b'\x30{}', b'\xf0', b'\x10\x01\x04\x00\x00', b'\x00\x00\x00', b'\xd0{"status":2}'])
def test_invalid_lz4_blocks_are_rejected(env, block):
    crypto = importlib.import_module(env.package.__name__ + '._crypto')
    with pytest.raises(ValueError):
        crypto.lz4_block_decompress(block)


@pytest.mark.parametrize('payload', [b'{"status":1,"status":2}', b'{"status":2,"x":NaN}'])
def test_ambiguous_json_cannot_confirm_success(env, payload):
    with pytest.raises(module(env).UploadResponseError):
        module(env).decode_upload_response(pack(env, payload))


def test_reference_compression_and_aes_cross_check(env):
    lz4 = pytest.importorskip('lz4.block')
    aes = pytest.importorskip('Crypto.Cipher.AES')
    crypto = importlib.import_module(env.package.__name__ + '._crypto')
    for count in range(1, 80):
        obj = {'status': 2, 'message': '中文 response ' * count, 'pickcode': 'fixture'}
        raw = json.dumps(obj, ensure_ascii=False).encode()
        block = lz4.compress(raw, store_size=False)
        frame = len(block).to_bytes(2, 'little') + block
        n = -len(frame) % 16
        cipher = aes.new(crypto.AES_KEY, aes.MODE_CBC, crypto.AES_IV).encrypt(frame + bytes([n]) * n)
        assert module(env).decode_upload_response(cipher) == obj
