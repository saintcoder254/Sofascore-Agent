"""Content-addressed raw evidence archive contract.

The implementation is filesystem/object-store agnostic: callers provide a put
function. This prevents raw evidence from being silently overwritten.
"""
import hashlib, json

class RawEvidenceArchive:
    def __init__(self, put):
        self.put=put

    def archive(self, source, endpoint, payload, captured_at):
        body=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()
        digest=hashlib.sha256(body).hexdigest()
        key=f"basketball/raw/{source}/{int(captured_at)}/{digest}.json"
        self.put(key,body,{"source":source,"endpoint":endpoint,"sha256":digest,"captured_at":captured_at})
        return key,digest
