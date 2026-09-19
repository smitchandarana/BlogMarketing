# BlogMarketing

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)

Generate blog posts with an LLM, publish them to your website, and create +
schedule matching LinkedIn posts — all from a CLI or desktop GUI. Powered by
Groq, it turns one topic into a published article and a ready-to-post LinkedIn
update in a single command.

> Originally built to run content marketing for [phoenixsolution.in](https://www.phoenixsolution.in),
> now open-sourced so you can point it at your own site and LinkedIn account.

## Technology Stack

- **Python 3.11+**: Core application language
- **Groq API**: AI content generation (llama-3.3-70b-versatile model)
- **Tkinter**: Desktop GUI framework
- **SQLite**: Local database for post management
- **Requests**: HTTP client for APIs
- **APScheduler**: Background job scheduling
- **python-dotenv**: Environment variable management

## External APIs

- **Groq**: AI content generation
- **Unsplash**: Image fetching (optional)
- **LinkedIn UGC API**: Social media publishing
- **Git**: Version control for website deployment

## Features

- **AI-Powered Content Generation**: Uses Groq LLM to create blog posts and LinkedIn captions
- **Automated Publishing**: Publishes to website (Git-based) and LinkedIn UGC API
- **Image Integration**: Fetches relevant images from Unsplash API
- **Content Calendar**: 30-day pre-planned content calendar
- **Smart Scheduling**: Intelligent LinkedIn auto-posting based on content quality scoring
- **Dual Interfaces**: Tkinter GUI for ease of use + CLI for automation
- **Research Integration**: Pulls trending topics from Reddit and LinkedIn

## Quick Start

### Prerequisites

- Python 3.8+
- Git (for website publishing)
- Internet connection (for APIs)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/smitchandarana/BlogMarketing.git
   cd BlogMarketing
   ```

2. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate     # Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env          # Windows: copy .env.example .env
   # Edit .env with your own API keys
   ```

5. Run the GUI:
   ```bash
   python gui.py
   ```

## Configuration

### Required Environment Variables

| Variable | Description | Where to Get |
|---|---|---|
| `GROQ_API_KEY` | Groq API key for content generation | https://console.groq.com |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn OAuth token for posting | https://www.linkedin.com/developers |
| `UNSPLASH_ACCESS_KEY` | Unsplash API key for images | https://unsplash.com/developers |

### Optional Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GROQ_MODEL` | Groq model to use | `llama-3.3-70b-versatile` |
| `WEBSITE_REPO_PATH` | Path to phoenixsolution website repo | `C:\Projects\phoenixsolution` |

## Usage

### GUI Mode (Recommended)

Run `python gui.py` to launch the Tkinter interface with three main tabs:

- **Generate**: Create new blog posts and LinkedIn content
- **Tracker**: Manage existing content and change statuses
- **Publish**: Post previously generated content to LinkedIn

### CLI Mode

```bash
# Generate a blog post
python main.py generate --topic "Your Topic Here"

# Generate a standalone LinkedIn post
python main.py linkedin --topic "Your Topic Here"

# Publish a specific post by ID
python main.py publish --id 123

# Schedule management
python main.py schedule --list
```

## Architecture

The system follows clean architecture principles with single-responsibility modules:

- `blog_generator.py` - AI content generation
- `html_renderer.py` - Template rendering
- `website_publisher.py` - Git-based website publishing
- `linkedin_publisher.py` - LinkedIn API integration
- `smart_scheduler.py` - Intelligent auto-posting
- `tracker.py` - CSV-based content tracking
- `database.py` - SQLite for scheduling

## Content Pipeline

1. **Topic Selection** → Calendar-based or custom topics
2. **Blog Generation** → Groq LLM creates structured content
3. **LinkedIn Post Creation** → AI generates captions and hashtags
4. **Image Fetching** → Unsplash API provides relevant visuals
5. **HTML Rendering** → Template-based blog post creation
6. **Website Publishing** → Git push to live site
7. **LinkedIn Publishing** → UGC API posts with optional images

## Smart Scheduling

The intelligent scheduler automatically selects and posts the highest-quality content based on:

- Sentiment analysis (25 points)
- Engagement hooks (20 points)
- Keyword relevance (15 points)
- Content freshness (15 points)
- Optimal length (15 points)
- Image presence (10 points)

Configure scheduling slots and behavior in `scheduler_config.json`.

## File Structure

```
BlogMarketing/
├── Blogs/                 # Generated blog posts
├── LinkedIn Posts/        # Generated social content
├── MarketingSchedule/     # Content calendar and research
├── Prompts/              # AI prompt templates
├── tracker.csv           # Content tracking
├── scheduler_config.json # Auto-posting configuration
└── *.py                  # Application modules
```

## Documentation

For detailed documentation, see [DOCUMENTATION.md](DOCUMENTATION.md).

## Disclaimer

This tool publishes to LinkedIn through LinkedIn's **official UGC API** using
your own OAuth token, and to your own website via Git. You are responsible for:

- Using it in line with the [LinkedIn API Terms of Service](https://legal.linkedin.com/api-terms-of-use)
  and any platform whose API you connect.
- The content it generates — AI output should be reviewed before publishing.
- Keeping your API keys private (they live in `.env`, which is gitignored).

Provided "as is", without warranty of any kind (see [LICENSE](LICENSE)). Not
affiliated with or endorsed by LinkedIn, Groq, or Unsplash.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
conventions, and the PR checklist. Good first issues are labeled
[`good first issue`](https://github.com/smitchandarana/BlogMarketing/labels/good%20first%20issue).

## License

Released under the [MIT License](LICENSE). © 2026 Smit Chandarana.
