# Changelog

All notable changes to Reddit Moderator Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.7] - 2025-08-31

### Fixed
- **Comment Counting Bug**: Fixed issue where comments were being counted twice instead of once. The counter was incrementing both in the LLM token usage logging and in the GUI log message processing, causing the "Comments Analyzed" statistic to show double the actual number. Now each comment is counted exactly once regardless of the analysis outcome (REMOVE, KEEP, or SKIPPED).

## [1.8.6] - 2025-01-21

### Changed
- **Expanded Context Recognition**: Broadened content analysis to include technology and community-relevant contexts throughout the moderation prompt
- **Flexible Evidence Assessment**: Softened rigid "REQUIRE EXPLICIT EVIDENCE" requirements to allow contextual inference for community-relevant content
- **Gentler Language**: Replaced absolute terms (NEVER, MUST, MANDATORY) with softer alternatives (generally, typically, prefer) for more nuanced decision-making
- **Reduced Repetition**: Consolidated repetitive warnings and reminders, keeping only essential instances instead of multiple repetitions
- **Less Rigid Critical Reminders**: Updated critical reminder sections to be less strict about explicit mentions while maintaining core moderation principles

### Improved
- Enhanced flexibility in content moderation decisions
- Better contextual understanding for technology-related discussions
- More balanced approach to evidence requirements
- Cleaner, more readable prompt structure
- Maintained effectiveness while reducing over-restrictive language

---

## Previous Versions

For versions prior to 1.8.6, please refer to the git commit history or contact the maintainers.
