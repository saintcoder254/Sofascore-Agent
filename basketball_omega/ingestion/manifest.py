from dataclasses import dataclass, asdict
import hashlib, json, time

@dataclass(frozen=True)
class CorpusManifest:
    source:str
    dataset:str
    seasons:tuple
    records:int
    started_at:float
    completed_at:float|None
    checksum:str
    status:str
    errors:tuple=()

class ManifestStore:
    def digest(self, payload):
        return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    def create(self,source,dataset,seasons,records,payload,status="complete"):
        return CorpusManifest(source,dataset,tuple(seasons),int(records),time.time(),None,self.digest(payload),status,())
    def to_json(self,m): return json.dumps(asdict(m),sort_keys=True,indent=2)
