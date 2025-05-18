# ClipboardDigest (Developing...)

**ClipboardDigest** is a Python tool that runs in the background, monitors your clipboard, and creates a daily summary report. It tracks everything you copy, logs it to a local database, and summarizes your copy activity at the end of each day.

## Features

- **Smart Clipboard Monitoring**: Continuously tracks what you copy with efficient change detection
- **AI-Powered Summaries**: Automatically generates concise summaries of lengthy clipboard content
- **Intelligent Content Grouping**: Groups similar content to avoid duplicate summarization and save API costs
- **Daily Insights**: Creates comprehensive daily reports of your clipboard activity
- **Flexible Configuration**: Easily configurable through `.env` file with sensible defaults
- **Privacy-Focused**: All data remains local in a SQLite database. Supports local LLM (See [`.env.local_llm`](/.env.local_llm))

## Example Daily Insights

> **Note:** The insights schema is fully customizable to track different metrics or activity patterns based on your needs. In future versions, this structured JSON output will be used to generate an interactive frontend dashboard for better visualization and analysis of your clipboard activity.

```json
{
  "tasks": [
    {
      "name": "Python Project Structure Setup",
      "description": "Setting up a new Python project with proper folder structure, configuration files, and dependency management using Poetry.",
      "ids": [124, 126, 127, 129, 130]
    },
    {
      "name": "API Documentation Research",
      "description": "Researching and collecting documentation examples for RESTful API design patterns and OpenAPI specifications.",
      "ids": [132, 134, 136, 138, 140]
    },
    {
      "name": "Japan Travel Planning",
      "description": "Researching accommodations in Tokyo and Kyoto, checking flight prices, and saving information about popular tourist destinations and transportation options.",
      "ids": [142, 143, 147, 149, 153, 159]
    },
    {
      "name": "Docker Compose Configuration",
      "description": "Creating and troubleshooting Docker Compose configuration for a multi-container development environment.",
      "ids": [144, 145, 146, 151, 162]
    }
  ],
  "timeline": [
    {
      "period": "09:15 - 09:47",
      "description": "Started the day with Python project setup, creating folder structure and configuring Poetry dependencies."
    },
    {
      "period": "09:47 - 10:12",
      "description": "Briefly switched to checking flight prices to Japan and saving accommodation links for Tokyo."
    },
    {
      "period": "10:23 - 10:58",
      "description": "Returned to development work, researching API documentation standards and OpenAPI examples."
    },
    {
      "period": "11:27 - 12:41",
      "description": "Docker Compose configuration work, focusing on networking and volume mounting issues."
    },
    {
      "period": "14:03 - 14:29",
      "description": "Final review of travel options and saving booking links for later reference."
    },
    {
      "period": "14:29 - 16:12",
      "description": "Continued Docker configuration and testing container interactions."
    }
  ],
  "keywords": [
    "🐍 Python Development",
    "✈️ Japan Travel Planning",
    "🐳 Docker Configuration"
  ],
  "pattern": "Today exhibited a dynamic workflow with multiple task switches. The day began with Python project setup, followed by intermittent travel research for an upcoming trip to Japan. API documentation research and Docker Compose configuration were the primary development activities, with a focus on resolving technical issues and enhancing project setup. The timeline indicates a well-distributed attention across different tasks, with productive blocks of development work interspersed with research activities.",
  "recommendation": "Maintain the current workflow flexibility, allowing for task switching as needed. Consider allocating specific time blocks for focused development and research to enhance productivity further. It may be beneficial to document the travel research process and findings in a separate note for easy reference and planning."
}
```

## TODO

- [x] Summary worker (LLM)
- [x] Group entries with time proximity
- [x] Insights worker (LLM)
- [ ] Include cool statistics for daily insights
- [ ] Table for daily report
- [ ] Build frontend
