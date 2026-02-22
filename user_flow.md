
# Overview
The user by defaults installs with the active setup wizard, and after going through it (if they enable shims, which are listed as the default), can immediately start using their agent in lux.

## setup

### how i want it to look

```
Lux Setup
Welcome to Lux! The blackbox for your ai agents. 

<What it is>

<What you need to remember>

```

### explicit

```
Lux Setup
Welcome to Lux! The blackbox for your ai agents. 

When something goes wrong, and you don't know what your agent did.
Without you changing your workflow at all, Lux automatically records
everything your agent does in each session. 

- point your agent to the logs to help it fix it
- find that old conversation you forgot about 
- figure out what your agent has done when you weren't watching

But before we start, we just have to answer four questions:

--- <user selects yes>

Lux Setup (1/5) Paths
We need to decide what folder your logs will be stored in, and what folders you want your agents to have access to

--- <user selects yes>

Lux Setup (2/5) Provider Auth

Do you use an API key or not?


--- <user selects yes>

Lux Setup (3/5) Secrets

...

Lux Setup (4/5) Shims



Lux Setup (5/5) Review

...

Announces that lux has been kicked off, so should be running.

<What you need to remember>

```




## user flow

### core
lux help
lux shim enable/disable
lux down (?)
### core in help
lux down - shuts down everything
lux up - starts everything 
lux tui - run the agent 
lux agent - info dump for agents
### power user
lux up --collector-only
lux logs


- install lasso
```
✅ Lux installed.

Next steps:
1) Run setup wizard: lux setup
   - workspace default: \$HOME (must stay under \$HOME)
   - log root default: OS-specific outside \$HOME
2) Start stack:
   - lux up --collector-only --wait
   - lux up --provider codex --wait
   - lux tui --provider codex
```