# Agent Merge Plan - Latency Optimization

## Current Architecture Analysis

### Current Agent Flow (5 LLM Calls)
1. **Intent Classifier** (~2-3s) - Extracts intent, entities, time range
2. **Schema Analyzer** (~3-4s) - Determines tables, columns, joins (with reasoning)
3. **SQL Generator** (~3-4s) - Generates PostgreSQL query (with reasoning)
4. **Answer Generator** (~2-3s) - Generates natural language answer
5. **Visualization Planner** (~2-3s) - Plans chart type and config

**Total LLM Latency: ~12-17 seconds**

### Non-LLM Agents
- **SQL Validator** - Rules-based validation (fast, ~50ms)
- **Result Validator** - Pass-through (no processing)

---

## Merge Strategy

### Merge 1: Intent Classifier + Schema Analyzer ✅ **HIGH IMPACT**

**Rationale:**
- Sequential execution (schema analyzer depends on intent/entities)
- Tightly coupled (schema analysis needs intent context)
- Both use similar LLM parameters
- Schema analyzer already receives intent/entities as input

**Implementation:**
- Create new `intent_and_schema_agent` that does both in one LLM call
- Single prompt that extracts intent, entities, AND determines schema
- Returns combined output: `{intent, entities, time_range, tables, columns, joins}`

**Expected Savings:** ~3-4 seconds (1 LLM call eliminated)

**Quality Impact:** ✅ **NONE** - Same information, just combined in one call

**Risk Level:** 🟢 **LOW** - Both tasks are well-defined and complementary

---

### Merge 2: Answer Generator + Visualization Planner ✅ **MEDIUM IMPACT**

**Rationale:**
- Both work on same query results
- Currently run in parallel (no dependency)
- Both analyze the same data structure
- Can be combined into one comprehensive response

**Implementation:**
- Create new `answer_and_viz_agent` that generates both in one LLM call
- Single prompt that generates answer AND visualization plan
- Returns: `{answer, key_insights, visualization_type, visualization_config}`

**Expected Savings:** ~2-3 seconds (1 LLM call eliminated)

**Quality Impact:** ✅ **NONE** - Same outputs, just combined

**Risk Level:** 🟢 **LOW** - Independent tasks that can be done together

---

## Updated Architecture

### New Agent Flow (3 LLM Calls)
1. **Intent & Schema Agent** (~4-5s) - Combined intent classification + schema analysis
2. **SQL Generator** (~3-4s) - Generates PostgreSQL query (with reasoning)
3. **Answer & Viz Agent** (~3-4s) - Combined answer generation + visualization planning

**New Total LLM Latency: ~10-13 seconds**
**Latency Reduction: ~30-40% (2-4 seconds saved)**

---

## Implementation Plan

### Phase 1: Merge Intent + Schema (Priority 1)

**Files to Modify:**
1. `agents/intent_classifier.py` → Rename/refactor to `agents/intent_and_schema_agent.py`
2. `agent_framework.py` → Update workflow to use merged agent
3. `agents/__init__.py` → Update imports

**Changes:**
- Combine `INTENT_CLASSIFIER_PROMPT` and `SCHEMA_ANALYZER_PROMPT` into one
- Single LLM call that returns both intent/schema data
- Update state structure to handle combined output
- Remove separate schema_analyzer node from workflow

**Testing:**
- Verify intent extraction still works correctly
- Verify schema analysis quality maintained
- Check that all existing queries still work

---

### Phase 2: Merge Answer + Viz (Priority 2)

**Files to Modify:**
1. `agents/answer_generator.py` → Refactor to `agents/answer_and_viz_agent.py`
2. `main.py` → Update to use merged agent instead of parallel calls
3. `agents/viz_planner.py` → Can be deprecated or kept as fallback

**Changes:**
- Combine `ANSWER_GENERATOR_PROMPT` and `VIZ_PLANNER_PROMPT` into one
- Single LLM call that returns both answer and visualization plan
- Update main.py to call single agent instead of parallel execution
- Remove ThreadPoolExecutor for answer/viz (no longer needed)

**Testing:**
- Verify answer quality maintained
- Verify visualization planning still accurate
- Check that chart configs are still correct

---

## Quality Assurance

### Validation Strategy

1. **Regression Testing:**
   - Run all example queries through new merged agents
   - Compare outputs with previous version
   - Verify SQL correctness maintained
   - Check visualization types are still appropriate

2. **Latency Measurement:**
   - Measure before/after latency for same queries
   - Track LLM call counts
   - Monitor total processing time

3. **Quality Metrics:**
   - SQL accuracy (same or better)
   - Intent classification accuracy
   - Schema selection correctness
   - Answer quality (readability, accuracy)
   - Visualization appropriateness

---

## Rollback Plan

If quality degrades:
1. Keep old agent files as backup (`_backup.py`)
2. Feature flag to switch between merged/separate agents
3. Can revert workflow changes quickly

---

## Expected Outcomes

### Latency Improvements
- **Before:** ~12-17s LLM calls + ~1-2s other = **~13-19s total**
- **After:** ~10-13s LLM calls + ~1-2s other = **~11-15s total**
- **Improvement:** **~2-4 seconds (15-25% reduction)**

### Cost Savings
- **Before:** 5 LLM calls per query
- **After:** 3 LLM calls per query
- **Reduction:** 40% fewer LLM calls

### Quality
- ✅ **Maintained** - Same information, just combined
- ✅ **No accuracy loss expected**
- ✅ **Same outputs, fewer calls**

---

## Implementation Order

1. ✅ **Phase 1: Intent + Schema Merge** (Highest impact, lowest risk) - **COMPLETE**
2. ✅ **Phase 2: Answer + Viz Merge** (Good impact, low risk) - **COMPLETE**
3. ⏸️ **Future: Consider SQL Generator optimizations** (Lower priority)

---

## Notes

- SQL Validator remains separate (rules-based, fast)
- Result Validator remains as pass-through
- SQL Generator kept separate (complex, needs reasoning)
- All merges maintain same output structure
- No breaking changes to API or state structure

