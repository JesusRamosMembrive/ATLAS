# Feature Documentation Directory

This directory stores documentation for features developed using the **3-Phase Development Workflow**.

## Purpose

The `.claude/doc/` directory maintains a structured record of:
- **Phase 1**: Architectural plans and design decisions
- **Phase 2**: Implementation progress and deviations
- **Phase 3**: Quality assurance reports and validation results

## Directory Structure

```
.claude/doc/
├── README.md (this file)
├── {feature-name-1}/
│   ├── architecture.md      # Phase 1: Architectural plan
│   ├── implementation.md    # Phase 2: Progress tracking
│   ├── qa-report.md        # Phase 3: QA validation
│   └── blockers.md         # Issues preventing progress (optional)
├── {feature-name-2}/
│   └── ...
└── {feature-name-3}/
    └── ...
```

## The 3-Phase Workflow

### Phase 1: Planning
**Agents**: @architect, @stage-keeper
**Output**: `{feature}/architecture.md`

The architect agent:
1. Analyzes requirements and constraints
2. Designs stage-appropriate architecture
3. Selects technology stack with rationale
4. Creates detailed implementation roadmap
5. Documents in `architecture.md`

**Key sections in architecture.md**:
- Context & Requirements
- Stage Assessment
- Component Structure
- Technology Stack
- Implementation Guidance (for implementer)
- Evolution Triggers

### Phase 2: Implementation
**Agent**: @implementer
**Output**: Code files + `{feature}/implementation.md`

The implementer agent:
1. Reads `architecture.md` FIRST (mandatory)
2. Executes plan component by component
3. Follows build order from plan
4. Tracks progress in `implementation.md`
5. Documents blockers immediately
6. Escalates when plan is unclear

**Key sections in implementation.md**:
- Build Order (checklist from architecture)
- Progress Log (what's done, what's in progress)
- Deviations from Plan (documented changes)
- Blockers (issues preventing completion)

### Phase 3: Validation
**Agents**: @code-reviewer, @stage-keeper
**Output**: `{feature}/qa-report.md`

The code reviewer agent:
1. Reads `architecture.md` and `implementation.md`
2. Validates implementation matches plan
3. Checks security, correctness, performance
4. Verifies stage-appropriate complexity
5. Documents in `qa-report.md`
6. Approves, requests fixes, or rejects

**Key sections in qa-report.md**:
- Plan Adherence Validation
- Security Review
- Correctness Review
- Stage Compliance
- Recommendation (Approved / Minor Fixes / Request Changes)

## Document Templates

### architecture.md Template

```markdown
# Architecture: {Feature Name}

**Date**: {YYYY-MM-DD}
**Stage**: {1-4}
**Complexity Level**: {Low/Medium/High}

## Context & Requirements
[Problem statement, user needs, constraints]

## Stage Assessment
**Current Project Stage**: {1-4}
**Allowed Patterns**: [List]

## Component Structure
[Diagram or description]

## Technology Stack
- **{Component}**: {Technology}
  - Rationale: [Why]
  - Trade-offs: [Pros/Cons]

## Implementation Guidance
### Build Order
1. **{Component A}** - Files to create, dependencies, success criteria
2. **{Component B}** - [Same]

### Code Patterns to Follow
[Examples]

## Evolution Triggers
[When to add complexity]

## Handoff Checklist
- [ ] Components defined
- [ ] Build order specified
- [ ] Technology justified
```

### implementation.md Template

```markdown
# Implementation: {Feature Name}

**Date Started**: {YYYY-MM-DD}
**Architecture Plan**: `.claude/doc/{feature}/architecture.md`

## Build Order
- [ ] Component A (file: path/to/file.py)
- [ ] Component B - depends on A
- [ ] Tests (if Stage 3+)

## Progress Log
### {Date} - Component A
- Status: ✅ Complete / 🔄 In Progress / ⏳ Pending

## Deviations from Plan
[Any changes to original architecture]

## Blockers
[Issues preventing completion]
```

### qa-report.md Template

```markdown
# QA Report: {Feature Name}

**Date**: {YYYY-MM-DD}

## 1. Plan Adherence
- [ ] All components implemented
- [ ] Technology stack matches
- **Score**: ✅ PASS / ⚠️ MINOR / ❌ MAJOR

## 2. Security Review
[Critical/High/Medium issues]
**Status**: ✅ SECURE / ⚠️ ISSUES / 🔴 CRITICAL

## 3. Correctness Review
[Bugs found, logic issues]
**Status**: ✅ CORRECT / ⚠️ ISSUES / ❌ BUGS

## 4. Stage Compliance
[Over/under-engineering check]
**Status**: ✅ APPROPRIATE / ⚠️ ISSUES / ❌ VIOLATIONS

## 5. Recommendation
**Status**: ✅ APPROVED | ⚠️ MINOR FIXES | ❌ REQUEST CHANGES

[Specific actions if not approved]
```

### blockers.md Template (Optional)

```markdown
# Blockers: {Feature Name}

## [BLOCKER-001] {Issue Title}
- **Discovered**: {Date}
- **Phase**: {1/2/3}
- **Component**: {Affected component}
- **Issue**: {Description}
- **Impact**: {What's blocked}
- **Escalation**: {Who needs to resolve}
- **Status**: ⏳ Waiting / 🔄 In Progress / ✅ Resolved

## Resolution Actions
1. [Action 1]
2. [Action 2]
```

## Usage Guidelines

### Creating a New Feature

When starting a new feature:

```bash
# 1. Create feature directory
mkdir -p .claude/doc/{feature-name}/

# 2. Initialize with architecture.md
# (Architect agent will populate this in Phase 1)
```

### Updating Progress

During implementation:

```bash
# Update implementation.md after each component
# Document deviations and blockers immediately
# Keep progress log current
```

### Completing a Feature

After QA approval:

```bash
# Archive or keep documentation for reference
# Update .claude/01-current-phase.md with completion
# Feature is ready for merge/deployment
```

## Best Practices

### Do:
- ✅ Keep documentation up to date
- ✅ Document all deviations from plan with rationale
- ✅ Create blockers immediately when discovered
- ✅ Use consistent naming for feature directories
- ✅ Reference plan documents in all phases

### Don't:
- ❌ Skip reading architecture.md before implementing
- ❌ Make undocumented deviations from the plan
- ❌ Proceed with unclear or incomplete plans
- ❌ Delete documentation after feature completion (keep for reference)
- ❌ Mix multiple features in one directory

## Integration with Agents

### @orchestrator
- Creates feature directories
- Manages phase transitions
- Ensures documentation completeness

### @architect
- Creates `architecture.md`
- Updates plan when blockers require changes

### @implementer
- Reads `architecture.md` FIRST
- Updates `implementation.md` with progress
- Creates `blockers.md` when stuck

### @code-reviewer
- Reads all feature docs for context
- Creates `qa-report.md`
- Validates against original plan

### @stage-keeper
- Validates stage-appropriateness across all phases
- Reviews documentation for over/under-engineering

## Naming Conventions

Feature directory names should be:
- **Lowercase with hyphens**: `user-authentication`, `payment-processing`
- **Descriptive**: Clearly indicate what the feature does
- **Concise**: Avoid overly long names
- **Consistent**: Match naming used in code/commits

## Maintenance

### Cleanup Policy
- Keep documentation for **active features** (in development)
- Keep documentation for **recent features** (last 3 months)
- **Archive** old documentation to `docs/archived/` if needed
- **Never delete** without team consensus

### Review Cycle
- Review `.claude/doc/` structure monthly
- Ensure all active features have complete documentation
- Archive completed features from 3+ months ago

---

**This directory is maintained by the 3-Phase Development Workflow.**
For more information, see `.claude/CUSTOM_INSTRUCTIONS.md` and `CLAUDE.md`
