# Spec Matrix (Normative Checklist)

Purpose: mission-cited checklist used to drive tests-first implementation.
Scope: implementation-neutral acceptance conditions.

## Sources

- `spec/Mission-EC-2.0.txt` (normative content labeled 2.1)
- `spec/Mission-Mapping-2.0.txt` (normative content labeled 2.1)
- `spec/Mission-Execution-Protocol-2.0.txt` (normative content labeled 2.1)

## A. Repository and input guardrails

1. Mission files must exist and be non-empty.
2. Placeholder banner text must not appear in mission files.
3. Engine must validate full EC input bundle before Steps 1–4.
Reference:
- EC §0, §1

## B. EC Mission (Step 1–4) requirements

1. Step 1 policy filtering must be whole-tuple on policy keys and multi-witness deterministic.
Reference:
- EC §3, §3.2, §3.4

2. Defaults must be applied before Step 1 and logged; not re-applied later.
Reference:
- EC §3.1, §9

3. Step 2 OC must run bottom-up with acyclic reverse-topo path or bounded fixpoint on cycles.
Reference:
- EC §4, §1.3, §9

4. Step 2 non-convergence must return only uniform error envelope (no partial OC artifact).
Reference:
- EC §4, §7

5. Step 3 EC must be IUC-seeded, propagated by mission gates, and bounded by max fixpoint rounds.
Reference:
- EC §5, §5.1, §5.2

6. Step 3 non-convergence must return only uniform error envelope.
Reference:
- EC §5.2, §7

7. Step 3 emission collapse must apply ancestor-preferred rule deterministically.
Reference:
- EC §5.3, §8

8. Step 4 Profile Schema must include only components with EC != empty and enforce closure constraints.
Reference:
- EC §6

9. Step 4 root ABIE inclusion is iff EC(rootABIE) != empty.
Reference:
- EC §6

10. Normative EC artifact filenames must match exactly.
Reference:
- EC §0
- `step1-prefiltered.json`
- `step2-oc.json`
- `step3-ec.<profileId>.json`
- `step4-profile.<profileId>.json`

11. Error envelope shape is uniform and mandatory for required error classes.
Reference:
- EC §7

12. Determinism constraints must hold (stable ordering, canonical behavior, no hidden non-determinism).
Reference:
- EC §8, §9

## C. Mapping Mission requirements

1. Mapping must run strictly after EC and use EC/Profile artifacts as semantic input.
Reference:
- Mapping §0, §1.1, §1.2

2. Mapping must treat EC/ProfileSchema as read-only.
Reference:
- Mapping §1.2

3. Tuple semantics in mapping must be exactly Mission-EC semantics (no alternatives introduced).
Reference:
- Mapping §1.3

4. Profile pairs must be processed in configured order; outputs follow same order.
Reference:
- Mapping §2

5. KCD(X) = bie_catalog[X].relevantAxes; if missing relevantAxes then [].
Reference:
- Mapping §3.1, §3.2

6. Presence overlap is based on EC(X) != empty on both source and target.
Reference:
- Mapping §5.1

7. Context compatibility uses projection to KCD and tuple intersection on projected sets.
Reference:
- Mapping §5.2

8. Classification rules:
- `NO_MAPPING` when either projected side is empty.
- `SEAMLESS` when intersection on KCD is non-empty.
- `CONTEXTUAL_TRANSFORM` when both projected sides non-empty and intersection empty.
Reference:
- Mapping §6

9. MRA structure must include required fields and consistency constraints (componentId, relevantAxes, full EC source/target, EC_common_on_KCD).
Reference:
- Mapping §7.1

10. Mapping outputs must include:
- `mapping.mra.<S>.<T>.json`
- `mapping.explanations.<S>.<T>.json`
Reference:
- Mapping §0, §7, §7.3

## D. Execution Protocol requirements

1. Mission-EC and Mission-Mapping are normative; protocol is structural index.
Reference:
- Protocol §0.1

2. For every numbered protocol step, engine must re-read/apply referenced mission sections.
Reference:
- Protocol §0.1

3. Engine must not execute from protocol-only summary text.
Reference:
- Protocol §0.1

4. On conflict/ambiguity conditions, engine must stop and report/ask clarification per protocol.
Reference:
- Protocol §0.1

5. Engine must not add steps/rules/artifacts/tuple semantics not defined by missions or explicit references.
Reference:
- Protocol §0.1

6. Protocol order must cover EC phase (validation, Step 1..4) then mapping phase.
Reference:
- Protocol §1, §2

## E. Test design roadmap

1. Keep smoke tests for file presence and normative markers.
2. Add validator tests first by section (happy path + negative path + determinism where applicable).
3. Add step-level artifact tests with exact filename and shape checks.
4. Add end-to-end deterministic golden tests after Step 1–4 + mapping are implemented.
