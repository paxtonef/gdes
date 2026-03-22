"""Strict relationship typing pre-V1.8"""
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

RELATIONSHIP_SCHEMA: Dict[Tuple[str, str], List[str]] = {
    ('finance', 'security'): ['compliance', 'audit', 'depends_on'],
    ('security', 'finance'): ['funds', 'budget_for'],
    ('doc_guide', 'my_tool'): ['implements', 'documents', 'tests'],
    ('my_tool', 'test'): ['tested_by', 'validates'],
    ('test', 'config'): ['configures', 'requires'],
    ('config', 'finance'): ['costs', 'budget_category'],
    ('doc_guide', 'doc_guide'): ['supersedes', 'version_of'],
    ('my_tool', 'my_tool'): ['depends_on', 'extends'],
    ('test', 'test'): ['depends_on', 'blocks'],
    ('security', 'security'): ['supersedes', 'policy_for'],
}

@dataclass
class RelationViolation:
    source: str
    target: str
    relation: str
    allowed: List[str]

class RelationshipValidator:
    def __init__(self, strict: bool = True):
        self.strict = strict
        self.schema = RELATIONSHIP_SCHEMA
        
    def validate(self, source_concept: str, target_concept: str, relation: str) -> None:
        key = (source_concept, target_concept)
        allowed = self.schema.get(key, [])
        
        if not allowed:
            if self.strict:
                raise ValueError(
                    f"Links between '{source_concept}' and '{target_concept}' forbidden. "
                    f"No schema defined."
                )
            return
            
        if relation not in allowed:
            raise ValueError(
                f"Relation '{relation}' not allowed between {source_concept}->{target_concept}. "
                f"Allowed: {allowed}"
            )
    
    def get_valid_targets(self, source_concept: str) -> Dict[str, List[str]]:
        return {
            target: relations 
            for (src, target), relations in self.schema.items() 
            if src == source_concept
        }
