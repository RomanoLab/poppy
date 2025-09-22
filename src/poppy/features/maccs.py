from typing import Optional

try:
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys
except Exception:
    Chem = None
    MACCSkeys = None


def maccs_bits_from_smiles(smiles: str) -> Optional[str]:
    if Chem is None or MACCSkeys is None:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    maccs = MACCSkeys.GenMACCSKeys(mol)
    return maccs.ToBitString()
