# Carousel OS

An open, brand-neutral Codex skill for creating polished, posting-ready Instagram and LinkedIn carousels. It works from a topic, brief, source material, copy, or visual direction supplied by the user. If no topic is given, it can propose an original one.

The included default style is intentionally generic: midnight navy, cloud white, coral, and sky blue. Replace `config/tokens.json` and the guidance in `references/design-system.md` to match a brand.

## Install in Codex

### Codex desktop or CLI

Copy the `carousel-os` folder into your Codex skills directory:

```bash
git clone https://github.com/YOUR-USERNAME/carousel-os.git
mkdir -p ~/.codex/skills
cp -R carousel-os ~/.codex/skills/
```

Restart Codex or start a new task. Then use prompts such as:

```text
Use $carousel-os to create a 7-slide Instagram carousel from this article: [link]
Use $carousel-os to turn this outline into a LinkedIn carousel. Audience: freelance designers.
Use $carousel-os to propose and create a carousel for my small-business finance audience.
```

If you clone this repository directly into `~/.codex/skills`, ensure the final path is `~/.codex/skills/carousel-os/SKILL.md`.

## Install in other agents

This is an open Agent Skills folder: keep the entire `carousel-os` directory intact, including `SKILL.md`, scripts, references, schemas, templates, and configuration. The agents below can use the same folder without a conversion step.

| Agent | Project-specific installation | Global installation |
| --- | --- | --- |
| Claude Code | `<project>/.claude/skills/carousel-os/` | `~/.claude/skills/carousel-os/` |
| Antigravity | `<project>/.agents/skills/carousel-os/` | `~/.gemini/config/skills/carousel-os/` |
| Codex | `<project>/.agents/skills/carousel-os/` | `~/.agents/skills/carousel-os/` |

Example for a project-local installation:

```bash
git clone https://github.com/YOUR-USERNAME/carousel-os.git
mkdir -p .agents/skills
cp -R carousel-os .agents/skills/
```

For Claude Code, replace `.agents/skills` in that command with `.claude/skills`. Start a new session after installing, then invoke it explicitly with `$carousel-os` when the agent supports explicit skill mentions, or ask it to create a carousel.

### Image generation outside Codex

Codex uses its native image-generation capability and needs no API key setup. In another agent, image creation or editing requires an OpenAI API key exposed to that agent as `OPENAI_API_KEY`; the skill uses **GPT Image 2** (`gpt-image-2`). Never paste an API key into a chat or commit it to a repository.

macOS/Linux shell:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_api_key_here"
```

After setting it, start the agent from the same terminal or configure the key in that agent's secure environment-variable settings. Without the key, the skill can still produce the carousel copy, layout plan, slide spec, and render non-image slides; it must pause before AI image generation.

## Requirements

- Python 3.10+
- Pillow, JSON Schema, and PyYAML (`python3 -m pip install -r requirements.txt`)
- Optional for Arabic text rendering: `arabic-reshaper` and `python-bidi`
- Codex image generation for AI-created or edited images

The renderer uses common system fonts by default. Add font paths in `config/tokens.json` if your brand requires specific typography.

## Customize

- Update `config/tokens.json` for the palette, handle, canvas tokens, and custom font paths.
- Update `references/design-system.md` for brand visual rules.
- Start from `templates/carousel.json` when using the renderer.

## What gets delivered

The workflow produces final PNG slides, a contact sheet, caption, package note, QA report, source list when applicable, and a ZIP archive.
