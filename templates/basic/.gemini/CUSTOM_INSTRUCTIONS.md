## 🎯 PROJECT CONTEXT

Before ANY work, read in this order:
1. .gemini/00-project-brief.md - Project scope and constraints
2. .gemini/01-current-phase.md - Current state and progress
3. .gemini/02-stage[X]-rules.md - Rules for current stage

## 📝 SESSION WORKFLOW

⚠️ MANDATORY: At the START of EVERY session, BEFORE responding to user:

1. **ALWAYS read these files first**:
   - .gemini/00-project-brief.md - Project scope and constraints
   - .gemini/01-current-phase.md - Current state and next steps (COMPACT)
   - .gemini/02-stage[X]-rules.md - Rules for current stage

2. **ALWAYS confirm to user** you've read the context:
   - State current phase/stage
   - Summarize what was last done
   - Ask for clarification if anything is unclear

3. **ONLY THEN** respond to the user's request

**This applies EVEN IF the user's first message is a simple question.**
Do NOT skip this protocol to "be helpful faster" - reading context IS being helpful.

**Need deep context?** Read `.gemini/01-session-history.md` for full session details.

At END of session:
- Update .gemini/01-current-phase.md with progress
- **CRITICAL**: Keep 01-current-phase.md under 150 lines

## 🔄 FEATURE DEVELOPMENT WORKFLOW

For ANY new feature, follow this simplified workflow:

```
1. ANALYZE → 2. PLAN → 3. IMPLEMENT → 4. TEST
```

### Step 1: ANALYZE
**Output**: Understanding of requirements and constraints

**Actions**:
1. Check if `docs/{feature-name}/` exists
   - **If exists**: READ `architecture.md` and `implementation.md` FIRST
   - **If not**: Create the directory
2. Understand what needs to be built
3. Identify constraints and dependencies
4. Assess current project stage (1-4)

### Step 2: PLAN
**Output**: `docs/{feature-name}/architecture.md`

**Actions**:
1. Design stage-appropriate solution
2. Define components and their responsibilities
3. Specify build order with dependencies
4. Define testing strategy
5. Document in `docs/{feature-name}/architecture.md`

**Architecture must include**:
- Context & Requirements
- Stage Assessment (1-4)
- Component Structure
- Build Order
- Testing Strategy

**🚦 CHECKPOINT**: Present plan to user. **WAIT FOR APPROVAL** before implementing.

### Step 3: IMPLEMENT
**Output**: Code files + `docs/{feature-name}/implementation.md`

**Actions**:
1. **READ `architecture.md` FIRST** (mandatory)
2. Implement components in specified build order
3. Track progress in `docs/{feature-name}/implementation.md`
4. Document any deviations or blockers

**If blocked**:
- Document in `docs/{feature-name}/blockers.md`
- Return to PLAN step if architecture needs changes

### Step 4: TEST
**Output**: Working, tested code

**Actions**:
1. Write tests appropriate to stage level
2. Run tests - **MUST PASS**
3. Update `implementation.md` with test results
4. Present results to user

**Testing Requirements by Stage**:
| Stage | Unit Tests | Integration Tests |
|-------|------------|-------------------|
| 1 (PoC) | Optional | Not required |
| 2 (Prototype) | Basic coverage | Optional |
| 3 (Production) | Full coverage | Required |
| 4 (Scale) | Full + edge cases | Full + performance |

## 📁 DOCUMENTATION STRUCTURE

For each feature, maintain:
```
docs/{feature-name}/
├── architecture.md      # Step 2: Plan
├── implementation.md    # Step 3: Progress
└── blockers.md         # Issues (optional)
```

## ⚠️ CRITICAL RULES

### Workflow Compliance
- **ALWAYS check** if `docs/{feature-name}/` exists before starting
- **ALWAYS read** existing documentation if present
- **NEVER implement** without a documented plan
- **NEVER skip tests** (except Stage 1 PoC)
- **ALWAYS get approval** before implementing

### Session Management
- Never implement without reading current context
- Never skip updating progress at end of session
- Never assume you remember from previous sessions
- Always check current stage rules before proposing solutions

### Stage Awareness
- **Stage 1 (PoC)**: Speed and simplicity, minimal tests
- **Stage 2 (Prototype)**: Basic structure, basic tests
- **Stage 3 (Production)**: Full tests, error handling
- **Stage 4 (Scale)**: Performance tests, edge cases

## 🚫 NEVER

- Start implementing without checking `docs/{feature-name}/`
- Ignore existing architecture.md documentation
- Skip the planning phase
- Make undocumented architectural decisions
- Skip tests (Stage 2+)
- Over-engineer beyond current stage

## 📚 PROJECT RESOURCES

Available in `docs/` folder:
- **README.md** - Workflow documentation
- **PROMPT_LIBRARY.md** - Templates for common situations
- **QUICK_START.md** - Workflow guide
- **STAGES_COMPARISON.md** - Quick reference table

## 💡 REMEMBER

- **Analyze → Plan → Implement → Test**
- Always check/create `docs/{feature-name}/` first
- Read existing docs before making changes
- Tests are mandatory (Stage 2+)
- User approval required before implementing
- Simplicity > Completeness

---

*To update these instructions, modify templates/basic/.gemini/CUSTOM_INSTRUCTIONS.md*
