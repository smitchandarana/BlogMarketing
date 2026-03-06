# CLAUDE.md

Purpose

This repository builds a local automation system that generates blogs and publishes LinkedIn posts automatically.

Claude must prioritize:

• clean Python architecture
• minimal token usage
• modular code
• working code over explanations

---

Core Responsibilities

Claude is responsible for generating and maintaining:

1. blog generation logic
2. HTML rendering
3. LinkedIn content generation
4. LinkedIn publishing
5. local scheduling
6. database storage

---

Technology Stack

Python 3.11+

Libraries:

requests
sqlite3
apscheduler
python-dotenv
openai

---

Architecture Principles

Use modular Python files.

Each module must have a single responsibility.

Avoid large monolithic scripts.

---

Token Efficiency Rules

Claude must:

avoid long explanations
only output necessary code
reuse existing modules where possible

---

Model Usage

ChatGPT API should be used for:

blog generation
LinkedIn caption generation
hashtags

Claude should only generate and maintain the automation system.

---

Validation Process

After generating code Claude must:

1. verify imports
2. verify module integration
3. confirm environment variables exist
4. confirm database schema works

If issues are found Claude must fix them before returning output.

---

Output Format

Return:

project structure
all code files
setup instructions

Do not return partial implementations.
