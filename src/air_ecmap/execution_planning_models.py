from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Union, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CodeListEntry(StrictBaseModel):
    source: str
    target: Any


class CodeListEntries(StrictBaseModel):
    description: Optional[str] = None
    entries: List[CodeListEntry]


class CodeListMapping(StrictBaseModel):
    description: Optional[str] = None
    mapping: Dict[str, Any]


CodeList = Union[CodeListEntries, CodeListMapping]


class TransformTableMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    description: Optional[str] = None
    createdAt: Optional[str] = None
    author: Optional[str] = None


class ContextCondition(StrictBaseModel):
    model_config = ConfigDict(extra="allow")


class MatchSource(StrictBaseModel):
    path: str
    op: str
    value: Optional[Any] = None


class LiteralValue(StrictBaseModel):
    kind: Literal["literal"]
    value: Any


class SourceValue(StrictBaseModel):
    kind: Literal["source_value"]
    sourcePath: str
    coerce: Optional[Literal["string", "number", "boolean", "date", "datetime"]] = None


class OnMissing(StrictBaseModel):
    action: Literal["error", "default"]
    default: Optional[Any] = None


class LookupValue(StrictBaseModel):
    kind: Literal["lookup"]
    tableId: str
    input: "ValueExpr"
    onMissing: Optional[OnMissing] = None
    default: Optional[Any] = None


ValueExpr = Annotated[Union[LiteralValue, SourceValue, LookupValue], Field(discriminator="kind")]


class Write(StrictBaseModel):
    targetPath: str
    value: ValueExpr


class ThenClause(StrictBaseModel):
    writes: List[Write]


class ReferenceSpec(StrictBaseModel):
    standard: str
    id: str
    url: Optional[str] = None


class ReferenceNote(StrictBaseModel):
    standard: str
    note: str


Reference = Union[ReferenceSpec, ReferenceNote]


class Constraint(StrictBaseModel):
    standard: str
    rule: str
    note: Optional[str] = None


class RuleTestSpec(StrictBaseModel):
    id: str
    type: Literal["schematron", "assert", "unit"]
    expr: Optional[str] = None
    message: Optional[str] = None


class RuleTestFixture(StrictBaseModel):
    type: Literal["formula", "context", "structural"]
    description: str
    input: Optional[Any] = None
    expect: Optional[Any] = None


RuleTest = Union[RuleTestSpec, RuleTestFixture]


class WhenClause(StrictBaseModel):
    source: Dict[str, str]
    target: Dict[str, str]


class TransformRule(StrictBaseModel):
    ruleId: str
    componentId: str
    relevantAxes: Optional[List[str]] = None
    priority: Optional[int] = None
    when: WhenClause
    matchSource: Optional[MatchSource] = None
    then: ThenClause
    references: Optional[List[Reference]] = None
    constraints: Optional[List[Constraint]] = None
    tests: Optional[List[RuleTest]] = None
    notes: Optional[str] = None


class TransformTable(StrictBaseModel):
    version: Literal["TransformTable-1.0"]
    meta: Optional[TransformTableMeta] = None
    codeLists: Optional[Dict[str, CodeList]] = None
    rules: List[TransformRule]

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "TransformTable":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for rule in self.rules:
            if rule.ruleId in seen:
                duplicates.add(rule.ruleId)
            seen.add(rule.ruleId)
        if duplicates:
            raise ValueError(f"duplicate ruleId: {sorted(duplicates)}")
        return self


class RuntimeContext(StrictBaseModel):
    source: Dict[str, str]
    target: Dict[str, str]
    values: Optional[Dict[str, Any]] = None


class MissingInfo(StrictBaseModel):
    resolved: bool
    reason: str
    sourcePath: Optional[str] = None


class PlanWrite(StrictBaseModel):
    targetPath: str
    valueExpr: ValueExpr
    status: Literal["resolved", "symbolic"]
    value: Optional[Any] = None
    missing: Optional[MissingInfo] = None


class Guards(StrictBaseModel):
    source: Dict[str, str]
    target: Dict[str, str]


class PlanProvenance(StrictBaseModel):
    mappingId: str
    relevantAxes: List[str]


class PlanEntry(StrictBaseModel):
    componentId: str
    decision: Literal["CONTEXTUAL_TRANSFORM"]
    selectedRuleId: str
    candidateRuleIds: List[str]
    applicableRuleIds: List[str]
    guards: Guards
    constraints: Optional[List[Constraint]] = None
    tests: Optional[List[RuleTest]] = None
    references: Optional[List[Reference]] = None
    provenance: PlanProvenance
    writes: List[PlanWrite]


class ProvenanceRef(StrictBaseModel):
    componentId: str
    ruleId: str


class WriteOperation(StrictBaseModel):
    targetPath: str
    valueExpr: ValueExpr
    status: Literal["resolved", "symbolic"]
    value: Optional[Any] = None
    missing: Optional[MissingInfo] = None
    provenance: List[ProvenanceRef]
    dedupeCount: int


class Summary(StrictBaseModel):
    contextualMraCount: int
    resolvedPlanCount: int
    unresolvedCount: int
    uniqueWriteOperationCount: int
    symbolicWriteCount: int
    conflictCount: int


class UnresolvedEntry(StrictBaseModel):
    componentId: str
    reason: str


class ExecutionPlanning(StrictBaseModel):
    version: Literal["ExecutionPlanning-1.1"]
    sourceProfileId: str
    targetProfileId: str
    runtimeContext: RuntimeContext
    plans: List[PlanEntry]
    writeOperations: List[WriteOperation]
    unresolved: List[UnresolvedEntry]
    conflicts: List[Dict[str, Any]]
    summary: Summary


class ExecutionPlanningValidation(StrictBaseModel):
    version: Literal["ExecutionPlanningValidation-1.1"]
    sourceProfileId: str
    targetProfileId: str
    checks: Dict[str, bool]
    notes: Optional[List[str]] = None
