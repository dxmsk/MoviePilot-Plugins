import importlib,sys,types,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]/'plugins.v2/cloudpush115'
p=types.ModuleType('response_test_cp');p.__path__=[str(ROOT)];sys.modules[p.__name__]=p
crypto=importlib.import_module(p.__name__+'._crypto')
response=importlib.import_module(p.__name__+'.response')

def pack(raw):
 n=len(raw); out=bytearray([min(n,15)<<4])
 if n>=15:
  rest=n-15
  while rest>=255:out.append(255);rest-=255
  out.append(rest)
 out.extend(raw)
 return crypto.aes_cbc_encrypt(len(out).to_bytes(2,'little')+out)

@pytest.mark.parametrize('encoding',['utf-8','gb18030'])
@pytest.mark.parametrize('status',[1,2,7])
def test_response(encoding,status):
 data={'status':status,'message':'目录上传响应成功','name':'电影.mkv'}
 raw=json.dumps(data,ensure_ascii=False).encode(encoding)
 assert response.decode_upload_response(pack(raw))==data
 assert response.decode_upload_response(raw)==data

@pytest.mark.parametrize('raw',[b'',b'[]',b'{"x":}',pack(b'\xff\xff\xff'),pack(b'not json')])
def test_reject(raw):
 with pytest.raises(ValueError):response.decode_upload_response(raw)

def test_lz4_reference():
 lz4=pytest.importorskip('lz4.block')
 import random
 rng=random.Random(115)
 for _ in range(250):
  raw=bytes(rng.randrange(256) for i in range(rng.randrange(1,100)))*rng.randrange(1,50)
  assert crypto.lz4_block_decompress(lz4.compress(raw,store_size=False))==raw
