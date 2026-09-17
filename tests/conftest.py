from pathlib import Path
import os, sys
ROOT = Path(__file__).resolve().parents[1] / 'plugins/cow/runtime'
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'third_party/cityqa-deterministic/src')]
os.environ['ONT20_METAMODEL'] = str(ROOT/'ontology/metamodel.json')
sys.dont_write_bytecode = True
