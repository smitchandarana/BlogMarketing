# BlogMarketing

Automate Blog post and LinkedIn post generation and publishing for Phoenix Solutions.

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
   git clone <repository-url>
   cd BlogMarketing
   ```

2. Create virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   copy .env.example .env
   # Edit .env with your API keys
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

## Contributing

1. Follow the established module architecture
2. Add type hints and docstrings
3. Update tests for new functionality
4. Update documentation

## License

[Add license information here]
