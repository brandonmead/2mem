# Conventions (test fixture)

A minimal conventions file for the linter tests. Only the value-set fences matter here.

```valueset name=type
concept          what is this, and why does it matter
procedure        how do I do this, step by step
reference        what is the value, spec, or fact
specification    what should be built, and to what design
decision         what was chosen, why, and what was rejected
profile          who or what is this named entity
analysis         what did we find when we looked
narrative        what am I saying publicly
record           what happened, and when
original         frozen source text - _originals/ only
```

```valueset name=status
draft            not yet trustworthy
stable           trustworthy as written
deprecated       kept for history
```

```valueset name=area
home             the household
family           family life
health           body and mind
work             paid work
learning         study and skills
community        neighbours and groups
```

```valueset name=rel
part_of          this document is an enumerated member of the target (max 1)
```

```valueset name=relates_to_key
path             repo-absolute path to another document
rel              what the link is for; omit for "see also"
note             why the link is there - required when there is no rel
```
