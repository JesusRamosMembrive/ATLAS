## 🎯 PROJECT CONTEXT

Before ANY work, read in this order:
1. .claude/00-project-brief.md - Project scope and constraints
2. .claude/01-current-phase.md - Current state and progress
3. .claude/02-stage[X]-rules.md - Rules for current stage

## 📝 SESSION WORKFLOW

⚠️ MANDATORY: At the START of EVERY session, BEFORE responding to user:

1. **ALWAYS read these files first** (use Read tool in parallel):
   - .claude/00-project-brief.md - Project scope and constraints
   - .claude/01-current-phase.md - Current state and next steps (COMPACT)
   - .claude/02-stage[X]-rules.md - Rules for current stage

2. **ALWAYS confirm to user** you've read the context:
   - State current phase/stage
   - Summarize what was last done
   - Ask for clarification if anything is unclear

3. **ONLY THEN** respond to the user's request

**This applies EVEN IF the user's first message is a simple question.**
Do NOT skip this protocol to "be helpful faster" - reading context IS being helpful.

**Need deep context?** Read `.claude/01-session-history.md` for full session details.

During WORK:
- Follow stage-specific rules strictly
- Propose plans before implementing
- Get approval for architectural decisions

At END of session:
- Update .claude/01-current-phase.md with:
  * Brief summary of what was implemented
  * Key decisions (1-2 sentences each)
  * Next immediate steps
- Move detailed session notes to .claude/01-session-history.md
- **CRITICAL**: Keep 01-current-phase.md under 150 lines (compact for context efficiency)

## 🔄 3-PHASE DEVELOPMENT WORKFLOW

This project follows a structured 3-phase workflow where specialized agents handle planning, implementation, and validation separately.

### Phase 1: PLANNING (Research & Design)
**Agents**: @architect, @stage-keeper
**Output**: `.claude/doc/{feature}/architecture.md`

**Responsibilities**:
- Analyze requirements and constraints
- Design stage-appropriate architecture
- Select technology stack with rationale
- Create detailed implementation roadmap
- **NO code writing** - planning only

**Workflow**:
1. User requests feature or architectural guidance
2. @orchestrator detects planning phase needed
3. @architect creates architectural plan
4. @stage-keeper validates stage-appropriateness
5. Architecture documented in `.claude/doc/{feature}/architecture.md`
6. User approves plan before Phase 2 starts

**Output must include**:
- Context & requirements
- Stage assessment
- Component structure diagram
- Technology stack with trade-offs
- Implementation guidance for Phase 2
- Build order with dependencies
- Evolution triggers

### Phase 2: IMPLEMENTATION (Building)
**Agent**: @implementer
**Output**: Code files + `.claude/doc/{feature}/implementation.md`

**Responsibilities**:
- Read architecture plan FIRST (mandatory)
- Execute plan component by component
- Follow build order from plan
- Track progress in implementation.md
- Document blockers and deviations
- **NO architectural decisions** - follow the plan

**Workflow**:
1. @implementer reads `.claude/doc/{feature}/architecture.md` (MANDATORY)
2. Validates plan is complete and clear
3. Implements components in specified order
4. Updates `.claude/doc/{feature}/implementation.md` with progress
5. Escalates blockers to @architect via @orchestrator
6. Completes implementation and notifies @orchestrator

**Blockers trigger**:
- Plan is unclear or incomplete
- Technical constraints make plan infeasible
- Need to deviate significantly from plan
→ **STOP**, document in `blockers.md`, request architect clarification

### Phase 3: VALIDATION (Quality Assurance)
**Agents**: @code-reviewer, @stage-keeper
**Output**: `.claude/doc/{feature}/qa-report.md`

**Responsibilities**:
- Read plan and implementation docs
- Validate implementation matches plan
- Check security, correctness, performance
- Verify stage-appropriate complexity
- **NO redesign** - validate against plan

**Workflow**:
1. @code-reviewer reads architecture.md and implementation.md
2. Validates plan adherence
3. Performs security, correctness, stage compliance checks
4. Documents findings in `.claude/doc/{feature}/qa-report.md`
5. @stage-keeper performs final stage compliance check
6. Recommendation: Approve / Minor Fixes / Request Changes

**Outcomes**:
- ✅ **Approved**: Feature ready for merge
- ⚠️ **Minor Fixes**: Small improvements needed, can proceed
- ❌ **Request Changes**: Return to Phase 2, critical issues found

### Agent Roles Summary

| Agent | Phase | Role | Can Write Code? |
|-------|-------|------|-----------------|
| @architect | 1 | Design architecture, create plan | ❌ No |
| @stage-keeper | 1, 2, 3 | Validate stage-appropriateness | ❌ No |
| @implementer | 2 | Execute plan, write code | ✅ Yes |
| @code-reviewer | 3 | Validate quality, plan adherence | ❌ No |
| @orchestrator | All | Coordinate phases, manage transitions | ✅ Limited (docs only) |

### Document Structure

```
.claude/doc/{feature-name}/
├── architecture.md      # Phase 1: Architectural plan
├── implementation.md    # Phase 2: Progress tracking
├── qa-report.md        # Phase 3: QA validation
└── blockers.md         # Issues preventing progress (optional)
```

### Session Context (Optional)

For complex features requiring shared context across multiple agents:

```
.claude/sessions/
└── context_session_{feature-name}.md  # Shared agent context
```

### Phase Transitions

**Phase 1 → 2 (Planning → Implementation)**:
- [ ] Architecture plan complete
- [ ] Stage-keeper validated
- [ ] User approved plan
- [ ] Implementation roadmap clear

**Phase 2 → 3 (Implementation → Validation)**:
- [ ] All planned components implemented
- [ ] Progress documented in implementation.md
- [ ] No critical blockers
- [ ] Basic manual testing passed

**Phase 3 → Complete (Validation → Done)**:
- [ ] QA report shows approval
- [ ] All critical issues resolved
- [ ] Stage compliance confirmed
- [ ] Documentation updated

### Workflow Examples

**Example 1: New Feature Request**
```
User: "Add user authentication"
→ @orchestrator: Detects Phase 1 needed
→ @architect: Creates auth architecture plan
→ @stage-keeper: Validates (Stage 2, keep simple)
→ User approves plan
→ @implementer: Executes plan, writes code
→ @code-reviewer: Validates, finds minor issues
→ @implementer: Fixes issues
→ @code-reviewer: Approves
→ Feature complete ✅
```

**Example 2: Implementation with Blocker**
```
User: "Implement OAuth2 login"
→ @implementer: Reads plan, finds DB schema missing
→ **BLOCKER**: Documents in blockers.md
→ @orchestrator: Escalates to @architect
→ @architect: Updates plan with DB schema
→ @implementer: Resumes implementation
→ Continues to Phase 3...
```

## ⚠️ CRITICAL RULES

### Session Management
- Never implement without reading current context
- Never skip updating progress at end of session
- Never assume you remember from previous sessions
- Always check current stage rules before proposing solutions

### 3-Phase Workflow Compliance
- **Planning agents (@architect, @stage-keeper)**: NEVER write implementation code
- **Implementation agent (@implementer)**: ALWAYS read architecture plan FIRST
- **Validation agents (@code-reviewer)**: NEVER redesign architecture
- **All agents**: Output documentation to correct `.claude/doc/{feature}/` locations

### Phase Transitions
- Never skip phases (must go 1 → 2 → 3)
- Never implement without approved architecture plan
- Never approve without validating against plan
- Always document blockers immediately when discovered

## 🚫 NEVER

### General
- Over-engineer beyond current stage
- Implement features not in project brief
- Forget to update tracking

### Phase 1 (Planning) - NEVER:
- Write implementation code
- Skip stage-keeper validation
- Create incomplete architecture plans
- Proceed to Phase 2 without user approval

### Phase 2 (Implementation) - NEVER:
- Start coding without reading architecture.md
- Make architectural decisions not in the plan
- Ignore blockers (document and escalate)
- Skip updating implementation.md progress

### Phase 3 (Validation) - NEVER:
- Redesign the architecture
- Approve code that deviates from plan without documented reason
- Skip reading architecture.md before review
- Ignore stage compliance violations

## 📚 PROJECT RESOURCES

Available in `docs/` folder:
- **PROMPT_LIBRARY.md** - Templates for common situations (debugging, refactoring, etc.)
- **QUICK_START.md** - Workflow guide
- **STAGES_COMPARISON.md** - Quick reference table
- **CLAUDE_CODE_REFERENCE.md** - Claude Code tips, slash commands, MCP, subagents

Use these resources when stuck or making decisions.

## 💡 REMEMBER

- Simplicity > Completeness
- Solve today's problems, not tomorrow's
- The methodology matters more than the code
- When in doubt, check the stage rules

---

*Generated by [Claude Prompt Library](https://github.com/your-repo/claude-prompt-library)*
*To update these instructions, modify templates/basic/.claude/CUSTOM_INSTRUCTIONS.md*